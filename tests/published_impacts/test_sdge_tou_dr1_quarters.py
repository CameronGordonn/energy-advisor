"""TIER 2 — SDG&E's published bill-impact figures against the TOU-DR1 specs, every quarter.

Read `tests/published_impacts/README.md` first. These are **not golden bills**. There is no
meter, no billing period and no interval data behind the published figures, so nothing here
counts toward the +/-$2 reconciliation pass rate or may be quoted in a reconciliation claim.

Three SDG&E rate-change alerts (1/1, 4/1 and 6/1 2026) against three rate vintages. Each is an
independently filed document, so each is an independent regression point on the same spec
family — which is the reason to run all three rather than the one session 25 started with.

**Two parameters the alert never states, and the same honest treatment for both.** SDG&E
publishes "$X/month for 400 kWh on schedule TOU-DR1" and states neither the baseline territory
nor how the 400 kWh spreads across TOU periods. An unstated parameter admits a feasibility
question, not a point test:

- **TOU allocation** — generation spans ~11x between super-off-peak and on-peak, so the
  generation figure cannot be reproduced at all; only the existence of *some* non-negative
  allocation pricing to it can be checked. Deliberately weak, and
  `test_the_generation_envelope_is_too_wide_to_be_evidence` measures how weak in CI.
- **Baseline territory** — the delivery energy rate is period-flat, so the TOU allocation does
  not matter here at all, but the territory does. Session 25 tested April against
  `coastal_basic` as a point test. That does not generalise: across the three quarters **no
  single territory** reproduces every published figure inside the publisher's own rounding
  band, and `test_no_single_territory_fits_every_quarter` pins that. The nearest territory is
  always one of the two coastal rows and always within $0.55, so the claim this tier can
  actually make is "some territory in the table prices to the published figure", plus the
  much sharper territory-free claim below.

**The sharp test is the vintage-over-vintage delta.** Differencing two quarters cancels the
unstated territory (the engine's change agrees across territories to a few cents while the
levels span $4) and cancels any constant methodology residual. That is what tests the rate
change itself, which is what these documents are actually about.

The degenerate interval series built here is a probe of a spec's arithmetic, not a customer
computation, so CLAUDE.md invariant 6 (real interval data, never modeled load profiles) is not
in play; see the README's note. `test_no_src_module_references_this_tier` keeps the other half
of that boundary honest.
"""

from __future__ import annotations

import itertools
import re
from datetime import date

import pytest

from tariffs.schema import Service
from tests.published_impacts import tier2
from tests.published_impacts.tier2 import (
    BY_HOUR_COUNT,
    CENT_ROUNDING_BOUND,
    DELTA_BAND,
    DERIVED_BAND,
    PUBLISHED_BAND,
    QUARTERS,
    REPO,
    SHAPES,
    TERRITORY_BAND,
    Quarter,
    annual_average_month,
    delivery_by_territory,
    envelope,
    implied_generation,
    territory_residuals,
)

CARE = [False, True]
PAIRS = list(itertools.pairwise(QUARTERS))


def ids(q: Quarter) -> str:
    return q.key


@pytest.fixture(params=QUARTERS, ids=ids)
def quarter(request) -> Quarter:
    return request.param


# --- the fixtures describe the specs actually under test ---------------------------------


def test_fixture_and_specs_agree_on_the_vintage(quarter):
    """A tier-2 figure is evidence about one rate vintage and nothing else."""
    assert quarter.delivery.effective_date == quarter.vintage
    assert quarter.generation.effective_date == quarter.vintage
    stated = quarter.fixture["assumptions_stated_by_source"]
    assert stated["schedule_id"] == quarter.delivery.schedule_id
    assert stated["rounding"] == "whole_dollars"
    # The whole reason the generation half is a feasibility test and not a reproduction.
    assert stated["tou_allocation"] == "UNSTATED"


def test_all_three_2026_quarters_are_under_test():
    """The fixtures are globbed, so this is what stops one being added without a test.

    Session 25 stream B added the January and June fixtures and left them untested while
    HANDOFF described generalising the April test as cheap. It was not: two of the three
    quarters fail the April test's territory point assertion. Pin the corpus so the next
    fixture cannot repeat that quietly.
    """
    assert [q.key for q in QUARTERS] == ["2026-01", "2026-04", "2026-06"]


def test_the_june_alert_restates_the_april_figures_as_its_previous_column():
    """A cross-document anchor: two independently filed alerts agreeing on one vintage.

    June's "previous" column is April's "current" one, which is a consistency check on the
    transcription of both fixtures that needs no engine at all.
    """
    april, june = (q for q in QUARTERS if q.key in {"2026-04", "2026-06"})
    for section in ("bundled", "delivery_only"):
        for cls in ("non_care", "care"):
            figures = june.fixture["figures_usd_per_month"][section][cls]
            assert (
                figures["previous_2026_04"]
                == (april.fixture["figures_usd_per_month"][section][cls]["current_2026_04"])
            )


def test_every_shape_meters_exactly_the_published_monthly_kwh(quarter):
    """If the probe series did not deliver 400 kWh/month the dollar tests mean nothing."""
    for name, by_month in SHAPES.items():
        for year, month in quarter.months():
            bill = tier2.compute_bill(
                tier2._series(quarter, by_month),
                [quarter.delivery],
                date(year, month, 1),
                date(year, month, tier2.calendar.monthrange(year, month)[1]),
                territory="coastal_basic",
                service=tier2.PCIA_EXCLUDED_BY_INFERENCE,
            )
            assert bill.total_kwh == pytest.approx(quarter.monthly_kwh, abs=1e-6), (
                f"{name} {year}-{month:02d}"
            )


# --- DELIVERY: period-flat, so the TOU allocation drops out entirely ----------------------


def test_delivery_is_shape_independent_because_its_energy_rate_is_period_flat(quarter):
    """The claim that removes the TOU allocation from the delivery half, in every quarter.

    Priced through the engine over five allocations spanning everything-on-peak to
    everything-super-off-peak. Agreement is to cent-rounding, not to the penny: each month's
    three energy lines round independently, so splitting the same kWh across more periods can
    move the annual average by up to $0.015. That residue is rounding, not shape sensitivity.

    ⭐ This is the SDG&E fact that costs real money elsewhere — TOU-DR1's UDC total is period-
    and season-flat, so 100% of the schedule's TOU price signal lives in the generation layer.
    Here it is what makes the delivery figure testable at all.
    """
    values = {
        name: annual_average_month(quarter, by_month, "delivery", territory="coastal_basic")
        for name, by_month in SHAPES.items()
    }
    assert max(values.values()) - min(values.values()) <= CENT_ROUNDING_BOUND, values


@pytest.mark.parametrize("care", CARE)
def test_some_baseline_territory_prices_to_the_published_delivery_figure(quarter, care):
    """The delivery claim this tier can actually make, in every quarter.

    The alert states no territory, so the honest form is feasibility over the eight rows of
    the spec's allowance table. Measured worst case across all six cells (3 quarters x
    CARE/non-CARE) is $0.55; TERRITORY_BAND is $1.00, leaving ~$0.45 of headroom — about
    0.11 c/kWh at 400 kWh/month, or 0.3% of the delivery energy rate.

    **This is a sharper test than the wide range of territory prices suggests**, because every
    territory shares one energy rate and one fixed charge and differs only in its baseline
    allowance. An error in the rate or the charge moves all eight rows together and cannot be
    absorbed by re-picking the territory; only an error inside the allowance table itself is
    partly hidden, and `test_the_two_coastal_territories_are_always_the_nearest` covers that.
    """
    nearest, territory, priced = territory_residuals(quarter, care)[0]
    assert nearest < TERRITORY_BAND, (
        f"{quarter.key} {'CARE' if care else 'non-CARE'}: nearest territory {territory} prices "
        f"to {priced:.2f} against published {quarter.published('delivery_only', care)}"
    )


@pytest.mark.parametrize("care", CARE)
def test_the_two_coastal_territories_are_always_the_nearest(quarter, care):
    """Which territory fits flips between the coastal pair by quarter — but never past it.

    The two nearest rows are the coastal pair in all six cells, and the third-nearest
    (`inland_basic` every time) is a further $0.98-$1.77 out. So the published figure does
    identify the CLIMATE ZONE as coastal even though it does not identify the row, and a
    decimal error in any non-coastal allowance would have to be large to hide here.

    Which of the two coastal rows wins is decided by rounding, not evidence: they sit a stable
    ~$1.05-1.13 apart while the published figure is a whole dollar carrying a ~$0.5-0.9 band.
    `coastal_basic` remains the better choice on a DOMAIN PRIOR — SDG&E Sheet 29294-E makes
    All-Electric available only on application — and on nothing else.
    """
    ranked = territory_residuals(quarter, care)
    assert {t for _, t, _ in ranked[:2]} == {"coastal_basic", "coastal_all_electric"}, ranked
    assert ranked[2][0] - ranked[1][0] > 0.9, ranked


def test_no_single_territory_fits_every_quarter():
    """⚠ The finding that retired session 25's territory point test. Pinned so it cannot rot.

    April's test asserted that exactly one territory (`coastal_basic`) lands inside the
    publisher's own +/-$0.50 rounding band, and read that as identifying the climate zone.
    Checked against the other two quarters it does not hold: in January NO territory lands
    inside the band for the non-CARE figure, and in June the nearest is
    `coastal_all_electric`. Worst residual across the six cells is $0.86 for `coastal_basic`
    and $0.96 for `coastal_all_electric`.

    So the residual beyond SDG&E's own rounding never exceeds $0.36 — below the resolution of
    a whole-dollar figure whose averaging method the alert does not disclose. It is not
    evidence of a spec defect, and it is not evidence of a territory. Recorded as a test so
    that a future spec edit which made one territory fit every quarter surfaces as a failure
    to be understood rather than as a silent improvement.

    See notes/published_impacts_corpus.md for the cross-quarter measurement.
    """
    fits = [
        territory
        for territory in QUARTERS[0].territories
        if all(
            abs(delivery_by_territory(q, care)[territory] - q.published("delivery_only", care))
            < PUBLISHED_BAND
            for q in QUARTERS
            for care in CARE
        )
    ]
    assert fits == [], fits


@pytest.mark.parametrize("care", CARE)
def test_which_territory_lands_inside_the_rounding_band_flips_by_quarter(quarter, care):
    """⚠ The measurement that retired the point test, pinned cell by cell.

    Session 25 measured April and read "exactly one territory lands inside the rounding band"
    as identifying the climate zone. The full corpus says the set is different in every
    quarter — empty in one of them — which is what a $1-wide structural gap between the two
    coastal rows does when it is straddled by a whole-dollar published figure:

        non-CARE   2026-01  (none)          2026-04  coastal_basic
                   2026-06  coastal_all_electric
        CARE       2026-01  coastal_basic   2026-04  coastal_basic
                   2026-06  both

    Written out rather than summarised because the pattern is the evidence. Any spec edit that
    moves a cell in or out of the band changes this table, and that should be a conversation,
    not a silent diff.
    """
    expected = {
        ("2026-01", False): [],
        ("2026-04", False): ["coastal_basic"],
        ("2026-06", False): ["coastal_all_electric"],
        ("2026-01", True): ["coastal_basic"],
        ("2026-04", True): ["coastal_basic"],
        ("2026-06", True): ["coastal_all_electric", "coastal_basic"],
    }
    inside = [
        territory
        for territory, priced in delivery_by_territory(quarter, care).items()
        if abs(priced - quarter.published("delivery_only", care)) < PUBLISHED_BAND
    ]
    assert inside == expected[(quarter.key, care)], inside


def test_the_april_delivery_figure_still_agrees_with_the_closed_form():
    """Cross-check on one quarter, so the engine path is anchored to arithmetic somewhere.

    Closed form at coastal_basic, non-CARE, over the 365 days from 2026-04-01:
        fixed    365 x 0.79343                                     =  289.60195
        energy   4800 x 0.34652                                    = 1663.29600
        credit   (153 summer x 9.0 + 212 winter x 9.2) x 1.30
                 = 4325.62 kWh credited x (0.10892)                = -471.14653
        annual average month                                       =  123.4793

    Note the 2-cent headroom against the $123.50 at which it would round to $124: cent
    rounding can move the engine figure at most $0.015, so it cannot cross.
    """
    (april,) = [q for q in QUARTERS if q.key == "2026-04"]
    for name, by_month in SHAPES.items():
        got = annual_average_month(april, by_month, "delivery", territory="coastal_basic")
        assert got == pytest.approx(123.4793, abs=CENT_ROUNDING_BOUND), name


@pytest.mark.parametrize("care", CARE)
def test_the_pcia_exclusion_is_load_bearing(quarter, care):
    """Pins the one inference this corpus rests on, so it cannot rot quietly.

    An unbundled customer is a CCA customer and pays the vintaged PCIA. Bill the same load
    with it and no vintage in the table lands anywhere near the published figure: the nearest
    (the 2009 vintage) is $6.63-$7.01 out against a PCIA-excluded residual of at most $0.86 —
    an order of magnitude, in all three quarters. One quarter could have been an arithmetic
    coincidence; three independently filed documents agreeing by the same margin is a pattern.

    It is load-bearing twice over: it is also what makes `bundled - unbundled` a clean
    generation figure below, rather than generation-minus-PCIA.
    """
    expected = quarter.published("delivery_only", care)
    (pcia,) = [a for a in quarter.delivery.adders if a.per_kwh_by_vintage]
    with_pcia = {
        vintage: annual_average_month(
            quarter,
            BY_HOUR_COUNT,
            "delivery",
            territory="coastal_basic",
            care=care,
            service=Service.CCA,
            vintage=vintage,
        )
        for vintage in sorted(pcia.per_kwh_by_vintage)
    }
    nearest = min(abs(amt - expected) for amt in with_pcia.values())
    assert nearest > 5.0, with_pcia
    assert quarter.fixture["measured_2026_09_15"]["pcia_treatment"] == "EXCLUDED_BY_INFERENCE"


# --- THE TERRITORY-FREE TEST: what the rate change itself did ----------------------------


@pytest.mark.parametrize("care", CARE)
@pytest.mark.parametrize("earlier,later", PAIRS, ids=lambda q: q.key)
def test_the_vintage_over_vintage_change_matches_the_published_change(earlier, later, care):
    """⭐ The sharpest claim this tier supports, because it needs no territory at all.

    Each alert publishes the figure it replaces alongside the one it introduces, so the
    CHANGE is published too — and a change is what a rate-change notice is about. Differencing
    cancels the unstated territory (the test below measures that) and cancels any constant
    methodology residual, leaving the filing itself under test.

    Band: two whole-dollar figures differenced inherit +/-$0.50 from each. Measured residuals
    are $0.07-$0.11 across the 1/1 -> 4/1 filing (published no change; the engine sees the
    0.0004/kWh UDC trim) and $0.38 non-CARE / $0.65 CARE across 4/1 -> 6/1 (published -$4
    and -$3; the engine sees the 0.01113/kWh UDC cut).
    """
    published = later.published("delivery_only", care) - earlier.published("delivery_only", care)
    computed = annual_average_month(
        later, BY_HOUR_COUNT, "delivery", territory="coastal_basic", care=care
    ) - annual_average_month(
        earlier, BY_HOUR_COUNT, "delivery", territory="coastal_basic", care=care
    )
    assert abs(computed - published) < DELTA_BAND, (
        f"{earlier.key} -> {later.key} {'CARE' if care else 'non-CARE'}: engine "
        f"{computed:+.2f} vs published {published:+.0f}"
    )


@pytest.mark.parametrize("care", CARE)
@pytest.mark.parametrize("earlier,later", PAIRS, ids=lambda q: q.key)
def test_the_vintage_over_vintage_change_is_territory_independent(earlier, later, care):
    """Why the delta test above is allowed to pick a territory arbitrarily.

    The levels span $4.22-$4.31 across the eight territories, but the CHANGE between two
    vintages agrees across all of them to a few cents, because the baseline allowances are
    identical in both specs and only the rates moved. So the delta test is measuring the
    filing, not the climate zone — which is precisely what makes it immune to the territory
    ambiguity that retired the point test.
    """
    changes = {
        territory: delivery_by_territory(later, care)[territory]
        - delivery_by_territory(earlier, care)[territory]
        for territory in earlier.territories
    }
    spread = max(changes.values()) - min(changes.values())
    levels = delivery_by_territory(later, care)
    assert spread < 0.25, changes
    assert max(levels.values()) - min(levels.values()) > 2.0, levels


# --- GENERATION: a feasibility test, and a weak one on purpose ---------------------------


def test_the_generation_price_signal_points_the_same_way_in_every_month(quarter):
    """Not required by the envelope, but worth pinning: on TOU-DR1 super-off-peak is the
    cheapest and on-peak the dearest generation period in all twelve months, in both seasons
    and in all three quarters. Every load-shift and battery conclusion on this schedule rests
    on that ordering holding year-round."""
    for care in CARE:
        _, _, cheapest, dearest = envelope(quarter, care)
        assert set(cheapest) == {"super_off_peak"}, cheapest
        assert set(dearest) == {"on_peak"}, dearest


@pytest.mark.parametrize("care", CARE)
def test_implied_generation_is_feasible_under_the_published_rounding(quarter, care):
    """The whole +/-$2 rounding band of the derived figure must be achievable, not just its
    midpoint.

    **What this is measured to catch, and measured to miss.** Mutating the committed
    generation spec: scaling every rate by 1/10 trips it; a 10x decimal shift on the single
    winter super-off-peak rate does NOT, and neither does inverting the season map. Both of
    those move the envelope while leaving the implied figure inside it. So this catches an
    error large enough to move the entire envelope off the figure and nothing finer. That is
    the honest ceiling of a feasibility test against a published number whose allocation is
    unstated, and it is why this tier may not be cited in a reconciliation claim.
    """
    cls = "care" if care else "non_care"
    implied = implied_generation(quarter, care)
    assert implied == quarter.fixture["derived"][f"generation_usd_{cls}"]

    low, high, _, _ = envelope(quarter, care)
    assert low < implied - DERIVED_BAND and implied + DERIVED_BAND < high, (
        f"{quarter.key}: implied {implied} +/- {DERIVED_BAND} is not inside the achievable "
        f"[{low:.2f}, {high:.2f}]"
    )


@pytest.mark.parametrize("care", CARE)
def test_the_generation_envelope_is_too_wide_to_be_evidence(quarter, care):
    """Measures the weakness in CI so the caveat cannot be quietly dropped.

    The achievable interval is ~$92 wide non-CARE against a $4 rounding band on the figure
    being tested, so the feasibility test accepts about 96% of the range it could have
    rejected (93% under CARE). A test this permissive is worth keeping — infeasibility would
    be proof of a broken spec — but it is not corroboration, and the delivery results above
    must never be described as if they carried this one along with them.
    """
    low, high, _, _ = envelope(quarter, care)
    accepted = (high - low - 2 * DERIVED_BAND) / (high - low)
    assert accepted > 0.9, (quarter.key, low, high, accepted)


def test_the_april_and_june_generation_envelopes_are_identical():
    """⚠ Three quarters of delivery evidence, but only TWO of generation. Say so in CI.

    ⭐ Delivery and generation change on DIFFERENT dates: the 6/1/2026 filing moved the UDC
    (0.34061 -> 0.32948) and left EECC untouched, so the April and June generation layers are
    the same numbers. The June generation assertions therefore re-test April's spec and are
    not an independent data point — exactly the kind of thing that turns "three quarters" into
    an overstatement if nobody writes it down.
    """
    april, june = (q for q in QUARTERS if q.key in {"2026-04", "2026-06"})
    for care in CARE:
        a_low, a_high, _, _ = envelope(april, care)
        j_low, j_high, _, _ = envelope(june, care)
        assert a_low == pytest.approx(j_low, abs=0.01)
        assert a_high == pytest.approx(j_high, abs=0.01)
    assert april.generation.energy == june.generation.energy


@pytest.mark.parametrize("care", CARE)
def test_a_witness_allocation_prices_to_the_implied_generation_figure(quarter, care):
    """Feasibility with a constructive witness, which is the honest form of the claim.

    Cost is linear in the mix between each month's cheapest and dearest period, so the mix
    that hits the implied figure is solved directly and then PRICED THROUGH compute_bill
    rather than asserted. The mix is also the sanity read the README asks for: a flat profile
    prices generation below the implied figure in every quarter, so SDG&E's number implies a
    load somewhat peakier than flat — which is what a residential shape is. That is an
    observation about the published number, assumed by nothing here, and it stays in this tier.
    """
    implied = implied_generation(quarter, care)
    low, high, cheapest, dearest = envelope(quarter, care)
    alpha = (implied - low) / (high - low)
    assert 0.0 < alpha < 1.0, alpha

    witness = tuple(
        ((dearest[i], alpha), (cheapest[i], 1.0 - alpha)) for i in range(len(quarter.months()))
    )
    priced = annual_average_month(quarter, witness, "generation", care=care)
    assert priced == pytest.approx(implied, abs=0.02), (alpha, priced, implied)

    # And the two layers on that same allocation rebuild the published BUNDLED bill — the
    # figure this tier can say least about, being the delivery result plus a free parameter
    # fitted to the difference.
    delivery = annual_average_month(
        quarter, witness, "delivery", territory="coastal_basic", care=care
    )
    bundled = quarter.published("bundled", care)
    assert abs(delivery + priced - bundled) < DERIVED_BAND + TERRITORY_BAND


# --- the tier boundary --------------------------------------------------------------------


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


def test_the_vintages_under_test_are_the_ones_the_alerts_describe():
    """Cheap guard on the glob: a fixture whose spec pair does not exist fails at import, and
    a fixture pointing at the wrong vintage fails here."""
    assert [q.vintage for q in QUARTERS] == [
        date(2026, 1, 1),
        date(2026, 4, 1),
        date(2026, 6, 1),
    ]
