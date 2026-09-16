"""TIER 2 — SDG&E's April 2026 published bill-impact figures against the 4/1/2026 specs.

Read `tests/published_impacts/README.md` first. These are **not golden bills**. There is no
meter, no billing period and no interval data behind the published figures, so nothing here
counts toward the +/-$2 reconciliation pass rate or may be quoted in a reconciliation claim.

Two assertions of two different strengths, and the difference is the whole point:

**DELIVERY is a point test.** SDG&E TOU-DR1's delivery energy rate is flat across all six
season x period keys, so the unbundled figure does not depend on how the 400 kWh is spread
across TOU periods at all. `test_delivery_is_shape_independent...` establishes that through
the engine rather than reading it off the YAML, and the remaining delivery tests then price
one shape against the published dollar. This is the first outside corroboration of any kind
to touch TOU-DR1, the schedule most SDG&E households are actually on.

**GENERATION is a feasibility test**, and a weak one — `test_the_generation_envelope_is_too
_wide_to_be_evidence` measures how weak, in CI, so the weakness cannot be forgotten. The
generation rate spans ~11x between super-off-peak and on-peak and the published figure never
states the allocation, so the figure cannot be reproduced; only the existence of *some*
non-negative allocation of 400 kWh/month that prices to it can be checked. Infeasible would
prove the spec wrong; feasible merely fails to contradict it.

The degenerate interval series built here is a probe of a spec's arithmetic, not a customer
computation, so CLAUDE.md invariant 6 (real interval data, never modeled load profiles) is
not in play; see the README's note. `test_no_src_module_references_this_tier` keeps the other
half of that boundary honest.
"""

from __future__ import annotations

import calendar
import re
import statistics
from datetime import date
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from greenbutton.models import COL_ESTIMATED, COL_KWH, LOCAL_TZ, IntervalSeries, MeterMeta, Utility
from tariffs.bill import compute_bill, period_codes
from tariffs.loader import SPECS_DIR, load_spec_file
from tariffs.schema import Service

HERE = Path(__file__).parent
FIXTURE = HERE / "sdge_2026-04_tou_dr1.yaml"
REPO = HERE.parents[1]

DELIVERY_SPEC = SPECS_DIR / "sdge_tou_dr1_delivery_2026-04-01.yaml"
GENERATION_SPEC = SPECS_DIR / "sdge_tou_dr1_generation_2026-04-01.yaml"

# SDG&E prints these alerts to the whole dollar ("May not sum due to rounding"), so a
# published $123 admits anything in [122.50, 123.50). A DERIVED figure (bundled minus
# unbundled) inherits that band from EACH operand, hence +/-$2 on the implied generation
# cost. Asserting on the derived figures without the wider band would fail on correct specs.
PUBLISHED_BAND = 0.5
DERIVED_BAND = 2.0

# The published figure is "an annual average bill", so the unit under test is the mean of
# twelve monthly bills. The window is the twelve calendar months from the specs' own
# effective date, which keeps every day inside the vintage: no `allow_before_effective`, and
# therefore no chance of pricing a day on rates that did not exist yet.
MONTHS = [(2026, m) for m in range(4, 13)] + [(2027, m) for m in range(1, 4)]
KWH_PER_MONTH = 400.0

# Every energy line is rounded to cents before the bill is summed, so two allocations of the
# same kWh over the same flat rate can differ by a cent or two. Three energy lines per month,
# each at most half a cent off, bounds the annual-average jitter at 3 x 0.005 = $0.015.
CENT_ROUNDING_BOUND = 0.015

PUBLISHED_TERRITORY = "coastal_basic"

# **The PCIA inference, named so a failure points at the assumption and not at the spec.**
# SDG&E's "unbundled" customer takes generation from a CCA, and a CCA customer pays the
# vintaged PCIA — which our delivery spec carries as an `applies_to: cca` adder. But the
# published $123 only reconciles with the PCIA excluded (footnote 3 of the alert says actual
# bills vary by "PCIA rate which will vary based on when you became a CCA customer", which is
# consistent with omitting an indeterminate component from an illustration, but does not say
# so outright). So we ask the engine for the CCA line set MINUS the PCIA, which is exactly
# what Service.BUNDLED selects on the delivery layer. Recorded in the fixture as
# `pcia_treatment: EXCLUDED_BY_INFERENCE`; `test_the_pcia_exclusion_is_load_bearing` pins how
# much rides on it.
PCIA_EXCLUDED_BY_INFERENCE = Service.BUNDLED


@cache
def _specs():
    delivery, generation = load_spec_file(DELIVERY_SPEC), load_spec_file(GENERATION_SPEC)
    # The series below is allocated using the delivery spec's period definitions and then
    # priced on both layers. That is only meaningful if the two layers classify hours
    # identically — on this vintage they must, since the generation layer carries the whole
    # TOU price signal and the delivery layer defines the windows it is measured against.
    assert delivery.tou == generation.tou
    return delivery, generation


@pytest.fixture(scope="module")
def published() -> dict:
    return yaml.safe_load(FIXTURE.read_text())


# --- the probe series -----------------------------------------------------------------------

Shares = tuple[tuple[str, float], ...]
"""One month's allocation: (TOU period, fraction of that month's kWh)."""


def every_month(shares: Shares) -> tuple[Shares, ...]:
    return tuple([shares] * len(MONTHS))


def _series(by_month: tuple[Shares, ...]) -> IntervalSeries:
    """400 kWh/month spread over the TOU periods in the proportions given, month by month.

    Within one period the kWh is spread evenly over that period's hours in that month; the
    monthly total is exactly 400 kWh whatever the split. Per-month allocations (rather than
    one shape for the year) are what let the generation envelope below pick each month's own
    cheapest and dearest period instead of assuming the ordering is the same all year.

    The shape is degenerate on purpose — it exists to interrogate a spec's arithmetic, and
    never stands in for a household.
    """
    delivery, _ = _specs()
    first, last = MONTHS[0], MONTHS[-1]
    idx = pd.date_range(
        pd.Timestamp(f"{first[0]}-{first[1]:02d}-01", tz=LOCAL_TZ),
        pd.Timestamp(f"{last[0]}-{last[1]:02d}-{calendar.monthrange(*last)[1]}", tz=LOCAL_TZ)
        + pd.Timedelta(days=1),
        freq="h",
        inclusive="left",
    )
    codes = period_codes(delivery.tou, idx)
    stamp = idx.year.values * 100 + idx.month.values
    kwh = np.zeros(len(idx))
    for (year, month), shares in zip(MONTHS, by_month, strict=True):
        in_month = stamp == year * 100 + month
        assert sum(share for _, share in shares) == pytest.approx(1.0)
        for period, share in shares:
            if share == 0.0:
                continue
            sel = in_month & (codes == period)
            n = int(sel.sum())
            assert n, f"{period} has no hours in {year}-{month:02d}"
            kwh[sel] = KWH_PER_MONTH * share / n
    frame = pd.DataFrame({COL_KWH: kwh, COL_ESTIMATED: False}, index=idx)
    return IntervalSeries(
        utility=Utility.SDGE,
        interval=pd.Timedelta(hours=1).to_pytimedelta(),
        meta=MeterMeta(utility=Utility.SDGE),
        frame=frame,
    )


@cache
def monthly_totals(
    by_month: tuple[Shares, ...],
    layer: str,
    *,
    care: bool = False,
    territory: str | None = None,
    service: Service = Service.BUNDLED,
    vintage: str | None = None,
) -> tuple[float, ...]:
    """The twelve monthly bills the engine computes for this allocation."""
    delivery, generation = _specs()
    specs = [delivery] if layer == "delivery" else [generation]
    series = _series(by_month)
    return tuple(
        compute_bill(
            series,
            specs,
            date(year, month, 1),
            date(year, month, calendar.monthrange(year, month)[1]),
            care=care,
            service=service,
            territory=territory,
            vintage=vintage,
        ).total
        for year, month in MONTHS
    )


def annual_average_month(by_month: tuple[Shares, ...], layer: str, **kw) -> float:
    """SDG&E's own unit: "Represents an annual average bill"."""
    return statistics.fmean(monthly_totals(by_month, layer, **kw))


PERIODS = ("on_peak", "off_peak", "super_off_peak")
PURE = {p: every_month(((p, 1.0),)) for p in PERIODS}

# Five allocations of the same 400 kWh/month, from "everything in the most expensive hours"
# to "everything in the cheapest" — the widest spread of load shapes the schedule admits.
SHAPES = {
    "all_on_peak": PURE["on_peak"],
    "all_off_peak": PURE["off_peak"],
    "all_super_off_peak": PURE["super_off_peak"],
    "by_hour_count": every_month(
        (("on_peak", 5 / 24), ("off_peak", 1 / 3), ("super_off_peak", 1 - 5 / 24 - 1 / 3))
    ),
    "evening_heavy": every_month((("on_peak", 0.5), ("off_peak", 0.3), ("super_off_peak", 0.2))),
}
BY_HOUR_COUNT = SHAPES["by_hour_count"]


# --- the fixture describes the specs actually under test -------------------------------------


def test_fixture_and_specs_share_the_alert_s_effective_date(published):
    """A tier-2 figure is evidence about one rate vintage and nothing else."""
    delivery, generation = _specs()
    assert delivery.effective_date == generation.effective_date == date(2026, 4, 1)
    stated = published["assumptions_stated_by_source"]
    assert stated["schedule_id"] == delivery.schedule_id
    assert stated["monthly_kwh"] == KWH_PER_MONTH
    assert stated["rounding"] == "whole_dollars"
    # The whole reason these are feasibility tests and not reproductions.
    assert stated["tou_allocation"] == "UNSTATED"


def test_every_shape_meters_exactly_the_published_monthly_kwh():
    """If the probe series did not deliver 400 kWh/month the dollar tests mean nothing."""
    delivery, _ = _specs()
    for name, by_month in SHAPES.items():
        series = _series(by_month)
        for year, month in MONTHS:
            bill = compute_bill(
                series,
                [delivery],
                date(year, month, 1),
                date(year, month, calendar.monthrange(year, month)[1]),
                territory=PUBLISHED_TERRITORY,
                service=PCIA_EXCLUDED_BY_INFERENCE,
            )
            assert bill.total_kwh == pytest.approx(KWH_PER_MONTH, abs=1e-6), (
                f"{name} {year}-{month:02d}"
            )


# --- DELIVERY: a point test, because the rate is period-flat ---------------------------------


def test_delivery_is_shape_independent_because_its_energy_rate_is_period_flat():
    """The claim that makes the delivery figure a point test rather than an envelope.

    Priced through the engine over five allocations spanning everything-on-peak to
    everything-super-off-peak. Agreement is to cent-rounding, not to the penny: each month's
    three energy lines round independently, so splitting the same kWh across more periods can
    move the annual average by up to $0.015. That residue is rounding, not shape sensitivity.
    """
    values = {
        name: annual_average_month(by_month, "delivery", territory=PUBLISHED_TERRITORY)
        for name, by_month in SHAPES.items()
    }
    assert max(values.values()) - min(values.values()) <= CENT_ROUNDING_BOUND, values


def test_engine_agrees_with_the_closed_form_to_within_cent_rounding():
    """Cross-check, not a substitute for the engine test: there is no gap to investigate.

    Closed form at coastal_basic, non-CARE, over the 365 days of the window:
        fixed    365 x 0.79343                                     =  289.60195
        energy   4800 x 0.34652                                    = 1663.29600
        credit   (153 summer x 9.0 + 212 winter x 9.2) x 1.30
                 = 4325.62 kWh credited x (0.10892)                = -471.14653
        annual average month                                       =  123.4793
    Session 25 measured $123.48 by hand off the spec YAML using 365/12-day months; the engine
    on real calendar months lands in the same place because the window is a whole year either
    way. (The two diverge by up to $0.11 on territories whose summer and winter allowances
    differ sharply — coastal_all_electric is 8.3 vs 13.5 — because the real Jun-Oct is 153
    days, not 5 x 30.4167. None of that touches the territory the published figure selects.)

    This is also where the 2-cent headroom on the published figure comes from: $123.4793 plus
    at most $0.015 of line rounding stays clear of the $123.50 at which it would round to $124.
    """
    closed_form = 123.4793
    for name, by_month in SHAPES.items():
        got = annual_average_month(by_month, "delivery", territory=PUBLISHED_TERRITORY)
        assert got == pytest.approx(closed_form, abs=CENT_ROUNDING_BOUND), name


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_delivery_reproduces_the_published_unbundled_figure(published, shape):
    """$123/month for 400 kWh on TOU-DR1, unbundled, non-CARE — SDG&E's own number.

    What one figure corroborates: the delivery energy rate, the Base Services Charge, the
    baseline allowance, the baseline credit, and (with the test below) the climate zone. The
    headroom is 2 cents, so this is a sharp test of the 4/1/2026 delivery spec — and it is
    the first outside evidence of any kind to touch TOU-DR1.
    """
    expected = published["figures_usd_per_month"]["delivery_only"]["non_care"]["current_2026_04"]
    got = annual_average_month(SHAPES[shape], "delivery", territory=PUBLISHED_TERRITORY)
    assert abs(got - expected) < PUBLISHED_BAND, f"{shape}: {got} vs published {expected}"


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_delivery_reproduces_the_published_unbundled_care_figure(published, shape):
    """$67/month CARE. Not a restatement of the above: it exercises the CARE-derived energy
    rate, the CARE fixed charge and the CARE baseline credit, none of which appear in the
    standard figure."""
    expected = published["figures_usd_per_month"]["delivery_only"]["care"]["current_2026_04"]
    got = annual_average_month(SHAPES[shape], "delivery", territory=PUBLISHED_TERRITORY, care=True)
    assert abs(got - expected) < PUBLISHED_BAND, f"{shape}: {got} vs published {expected}"


@pytest.mark.parametrize("care", [False, True])
def test_no_other_baseline_territory_reproduces_the_published_figure(published, care):
    """Only `coastal_basic` fits APRIL's printed dollar. Scope that claim to April.

    SDG&E's alert never states a territory. Eight are published in the spec's allowance
    table; for this quarter exactly one lands inside the rounding band, under CARE too.

    ⚠ This does NOT generalise, and an earlier version of this docstring said it did.
    Stream B checked Jan and Jun 2026 the same way: `coastal_all_electric` wins both. The
    two coastal territories sit a stable ~$1.05-1.13 apart while the published figure is a
    whole dollar with a ~$0.5-0.9 band, so which one "wins" a nearest-value test is decided
    by rounding, not by evidence. All six other territories stay >$2 off in every quarter —
    that part does hold. `coastal_basic` remains the better choice on a DOMAIN PRIOR (SDG&E
    Sheet 29294-E makes All-Electric an application-only special case), not on arithmetic.
    See notes/published_impacts_corpus.md. Do not copy this test to another quarter without
    reading that first — it would fail.
    """
    delivery, _ = _specs()
    key = "care" if care else "non_care"
    expected = published["figures_usd_per_month"]["delivery_only"][key]["current_2026_04"]
    priced = {
        territory: annual_average_month(BY_HOUR_COUNT, "delivery", territory=territory, care=care)
        for territory in sorted(delivery.baseline.allowances)
    }
    within = {t: v for t, v in priced.items() if abs(v - expected) < PUBLISHED_BAND}
    assert list(within) == [PUBLISHED_TERRITORY], priced


def test_the_pcia_exclusion_is_load_bearing(published):
    """Pins the one inference this fixture rests on, so it cannot rot quietly.

    An unbundled customer is a CCA customer and pays the vintaged PCIA. Bill the same load
    with it and no vintage in the table lands on the published figure — the closest, the 2009
    vintage, is $6.63 outside the band and the current vintages are ~$20 out. So SDG&E's
    illustration must be excluding it (see `PCIA_EXCLUDED_BY_INFERENCE`). If a future spec
    edit ever made a vintage match, this fails and the inference is revisited rather than
    silently inverted.

    It is load-bearing twice over: it is also what makes `bundled - unbundled` a clean
    generation figure below, rather than generation-minus-PCIA.
    """
    delivery, _ = _specs()
    expected = published["figures_usd_per_month"]["delivery_only"]["non_care"]["current_2026_04"]
    (pcia,) = [a for a in delivery.adders if a.per_kwh_by_vintage]
    with_pcia = {
        vintage: annual_average_month(
            BY_HOUR_COUNT,
            "delivery",
            territory=PUBLISHED_TERRITORY,
            service=Service.CCA,
            vintage=vintage,
        )
        for vintage in sorted(pcia.per_kwh_by_vintage)
    }
    assert not [v for v, amt in with_pcia.items() if abs(amt - expected) < PUBLISHED_BAND], (
        with_pcia
    )
    assert published["measured_2026_09_15"]["pcia_treatment"] == "EXCLUDED_BY_INFERENCE"


# --- GENERATION: a feasibility test, and a weak one on purpose --------------------------------


@cache
def _envelope(care: bool) -> tuple[float, float, tuple[str, ...], tuple[str, ...]]:
    """(cheapest, dearest) annual-average generation cost achievable at 400 kWh/month.

    Taken month by month over EVERY period rather than assuming super-off-peak is cheapest
    and on-peak dearest all year. That assumption is true of this spec and is pinned below,
    but hard-coding it made an earlier draft report "infeasible" for a spec whose on-peak and
    super-off-peak rates had merely been swapped — an allocation permutation that leaves the
    achievable set identical. A feasibility test that fails for the wrong reason is worse
    than no test.

    Both endpoints are allocations the schedule actually admits (super-off-peak covers
    weekday 00:00-06:00 and weekend mornings; on-peak covers 16:00-21:00 daily), so they are
    attained rather than asymptotic. Everything between is attained too: generation on this
    schedule is purely volumetric — no fixed charge, no baseline, no minimum bill — so the
    cost of mixing two allocations is the mix of their costs.
    """
    by_period = {p: monthly_totals(PURE[p], "generation", care=care) for p in PERIODS}
    cheapest = tuple(min(PERIODS, key=lambda p: by_period[p][i]) for i in range(len(MONTHS)))
    dearest = tuple(max(PERIODS, key=lambda p: by_period[p][i]) for i in range(len(MONTHS)))
    low = statistics.fmean(by_period[p][i] for i, p in enumerate(cheapest))
    high = statistics.fmean(by_period[p][i] for i, p in enumerate(dearest))
    return low, high, cheapest, dearest


def test_the_generation_price_signal_points_the_same_way_in_every_month():
    """Not required by the envelope above, but worth pinning: on TOU-DR1 super-off-peak is
    the cheapest and on-peak the dearest generation period in all twelve months, in both
    seasons. Every load-shift and battery conclusion on this schedule rests on that ordering
    holding year-round."""
    for care in (False, True):
        _, _, cheapest, dearest = _envelope(care)
        assert set(cheapest) == {"super_off_peak"}, cheapest
        assert set(dearest) == {"on_peak"}, dearest


@pytest.mark.parametrize("care", [False, True])
def test_implied_generation_is_feasible_under_the_published_rounding(published, care):
    """The whole +/-$2 rounding band of the derived figure must be achievable, not just its
    midpoint.

    **What this test is measured to catch, and what it is measured to miss.** Mutating the
    committed generation spec: scaling every rate by 1/10 trips it; a 10x decimal shift on
    the single winter super-off-peak rate does NOT, and neither does inverting the season
    map. Both of those move the envelope while leaving the implied $71 inside it. So this
    catches an error large enough to move the entire envelope off the figure and nothing
    finer. That is the honest ceiling of a feasibility test against a published number whose
    allocation is unstated, and it is why this tier may not be cited in a reconciliation
    claim.
    """
    key = "care" if care else "non_care"
    figures = published["figures_usd_per_month"]
    implied = (
        figures["bundled"][key]["current_2026_04"]
        - figures["delivery_only"][key]["current_2026_04"]
    )
    assert implied == published["derived"][f"generation_usd_{key}"]

    low, high, _, _ = _envelope(care)
    assert low < implied - DERIVED_BAND and implied + DERIVED_BAND < high, (
        f"implied {implied} +/- {DERIVED_BAND} is not inside the achievable [{low:.2f}, {high:.2f}]"
    )


@pytest.mark.parametrize("care", [False, True])
def test_the_generation_envelope_is_too_wide_to_be_evidence(care):
    """Measures the weakness in CI so the caveat cannot be quietly dropped.

    The achievable interval is ~$92 wide non-CARE against a $4 rounding band on the figure
    being tested, so the feasibility test accepts about 96% of the range it could have
    rejected. A test this permissive is worth keeping — infeasibility would be proof of a
    broken spec — but it is not corroboration, and the delivery figure above must never be
    described as if it carried this one along with it.
    """
    low, high, _, _ = _envelope(care)
    accepted = (high - low - 2 * DERIVED_BAND) / (high - low)
    assert accepted > 0.9, (low, high, accepted)


@pytest.mark.parametrize("care", [False, True])
def test_a_witness_allocation_prices_to_the_implied_generation_figure(published, care):
    """Feasibility with a constructive witness, which is the honest form of the claim.

    Cost is linear in the mix between each month's cheapest and dearest period, so the mix
    that hits the implied figure is solved directly and then PRICED THROUGH compute_bill
    rather than asserted. The mix is also the sanity read the README asks for: is the implied
    shape plausible? A flat profile (every hour of every month equal) prices generation at
    $64.80 non-CARE against the implied $71, so SDG&E's figure implies a load somewhat
    peakier than flat — which is what a residential shape is. That is an observation about
    the published number, assumed by nothing here, and it stays inside this tier.
    """
    key = "care" if care else "non_care"
    implied = float(published["derived"][f"generation_usd_{key}"])
    low, high, cheapest, dearest = _envelope(care)
    alpha = (implied - low) / (high - low)
    assert 0.0 < alpha < 1.0, alpha

    witness = tuple(((dearest[i], alpha), (cheapest[i], 1.0 - alpha)) for i in range(len(MONTHS)))
    priced = annual_average_month(witness, "generation", care=care)
    assert priced == pytest.approx(implied, abs=0.02), (alpha, priced, implied)

    # And the two layers on that same allocation rebuild the published BUNDLED bill — the
    # figure this tier can say least about, being the delivery point test plus a free
    # parameter fitted to the difference.
    delivery = annual_average_month(witness, "delivery", territory=PUBLISHED_TERRITORY, care=care)
    bundled = published["figures_usd_per_month"]["bundled"][key]["current_2026_04"]
    assert abs(delivery + priced - bundled) < DERIVED_BAND


# --- the tier boundary ------------------------------------------------------------------------


def test_no_src_module_references_this_tier():
    """README.md's boundary, enforced instead of asserted in prose.

    The lesson session 24 wrote down: a claim with no invalidation goes stale without anyone
    noticing. "Nothing in this directory may be imported by src/" is such a claim, so it gets
    a test. The other half — no figure here reaches a user-facing output — follows from it,
    since a value cannot reach the report without something in src/ reading it.
    """
    offenders = [
        str(path.relative_to(REPO))
        for path in sorted((REPO / "src").rglob("*.py"))
        if re.search(r"published_impacts", path.read_text())
    ]
    assert not offenders, (
        f"{offenders} reference tests/published_impacts. These figures have no meter and no "
        "interval data; they may not reach a product computation (README.md, CLAUDE.md "
        "invariants 1 and 6)."
    )
