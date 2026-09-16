"""Shared probe machinery for TIER 2 — see README.md. Imported only by tests in this package.

One SDG&E rate-change alert is one `Quarter`: a published figure set, the rate vintage it
describes, and the two committed spec layers for that vintage. Everything here prices a
degenerate interval series through `compute_bill` rather than repeating arithmetic off the
spec YAML, which is the point of the tier — a test that restates the spec cannot catch the
engine misreading it.
"""

from __future__ import annotations

import calendar
import statistics
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from greenbutton.models import COL_ESTIMATED, COL_KWH, LOCAL_TZ, IntervalSeries, MeterMeta, Utility
from tariffs.bill import compute_bill, period_codes
from tariffs.loader import SPECS_DIR, load_spec_file
from tariffs.schema import Service, TariffSpec

HERE = Path(__file__).parent
REPO = HERE.parents[1]

PERIODS = ("on_peak", "off_peak", "super_off_peak")

# SDG&E prints these alerts to the whole dollar ("May not sum due to rounding"), so a
# published $123 admits anything in [122.50, 123.50).
PUBLISHED_BAND = 0.5
# A figure DERIVED by subtracting two published figures inherits the band from each operand.
DERIVED_BAND = 2.0

# **A MEASURED band, not the publisher's.** The alert never states a baseline territory, and
# across the three 2026 quarters NO single territory reproduces every published figure within
# PUBLISHED_BAND -- the nearest territory is always one of the two coastal rows and is always
# within $0.55, but which of the two wins flips by quarter. So the delivery claim is "some
# territory in the table prices to the published figure", with a tolerance set from the
# measured worst case plus headroom, and `test_no_single_territory_fits_every_quarter` pins
# the fact that a tighter per-territory form is not available. See README.md design rule 3.
TERRITORY_BAND = 1.0

# Two published whole-dollar figures differenced: +/-0.5 from each.
DELTA_BAND = 1.0

# Every energy line is rounded to cents before the bill is summed, so two allocations of the
# same kWh over the same flat rate can differ by a cent or two. Three energy lines per month,
# each at most half a cent off, bounds the annual-average jitter at 3 x 0.005 = $0.015.
CENT_ROUNDING_BOUND = 0.015

# **The PCIA inference, named so a failure points at the assumption and not at the spec.**
# SDG&E's "unbundled" customer takes generation from a CCA, and a CCA customer pays the
# vintaged PCIA -- which our delivery spec carries as an `applies_to: cca` adder. But the
# published figures only reconcile with the PCIA excluded, in all three quarters. So we ask
# the engine for the CCA line set MINUS the PCIA, which is exactly what Service.BUNDLED
# selects on the delivery layer. `test_the_pcia_exclusion_is_load_bearing` pins how much
# rides on it; notes/published_impacts_corpus.md has the cross-quarter evidence.
PCIA_EXCLUDED_BY_INFERENCE = Service.BUNDLED


@dataclass(frozen=True, eq=False)
class Quarter:
    """One published alert, its rate vintage, and that vintage's two spec layers.

    `eq=False` on a frozen dataclass leaves the default identity hash, which is what lets
    these be `@cache` keys. Quarters are built once, at import, by `load_quarters()`.
    """

    key: str
    """The vintage as `YYYY-MM`, used as the pytest id."""
    path: Path
    vintage: date
    column: str
    """The `current_*` key inside the fixture's figure tables."""
    fixture: dict = field(repr=False)
    delivery: TariffSpec = field(repr=False)
    generation: TariffSpec = field(repr=False)

    def months(self) -> list[tuple[int, int]]:
        """The twelve calendar months from the vintage's own effective date.

        The published figure is "an annual average bill", so the unit under test is the mean
        of twelve monthly bills. Starting at the effective date keeps every day inside the
        vintage: no `allow_before_effective`, and no chance of pricing a day on rates that
        did not exist yet.
        """
        out, year, month = [], self.vintage.year, self.vintage.month
        for _ in range(12):
            out.append((year, month))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return out

    def published(self, section: str, care: bool) -> float:
        """The published dollar figure for this quarter's own `current_*` column."""
        cls = "care" if care else "non_care"
        return float(self.fixture["figures_usd_per_month"][section][cls][self.column])

    @property
    def monthly_kwh(self) -> float:
        return float(self.fixture["assumptions_stated_by_source"]["monthly_kwh"])

    @property
    def territories(self) -> list[str]:
        return sorted(self.delivery.baseline.allowances)


def load_quarters() -> list[Quarter]:
    """Every testable SDG&E fixture in this directory, oldest vintage first.

    Discovered by glob rather than by a hand-maintained list, so a fixture added without a
    test fails loudly here instead of sitting untested -- the gap this harness was written to
    close. `pge_2026-03_class_average.yaml` is excluded by the `sdge_` prefix: it states no
    schedule and no territory and is marked non-testable in its own header.
    """
    quarters = []
    for path in sorted(HERE.glob("sdge_*_tou_dr1.yaml")):
        fixture = yaml.safe_load(path.read_text())
        vintage = fixture["vintage"]
        key = f"{vintage:%Y-%m}"
        quarters.append(
            Quarter(
                key=key,
                path=path,
                vintage=vintage,
                column=f"current_{vintage:%Y_%m}",
                fixture=fixture,
                delivery=load_spec_file(
                    SPECS_DIR / f"sdge_tou_dr1_delivery_{vintage:%Y-%m-%d}.yaml"
                ),
                generation=load_spec_file(
                    SPECS_DIR / f"sdge_tou_dr1_generation_{vintage:%Y-%m-%d}.yaml"
                ),
            )
        )
    assert quarters, f"no sdge_*_tou_dr1.yaml fixtures found in {HERE}"
    return quarters


QUARTERS = load_quarters()


# --- the probe series -------------------------------------------------------------------

Shares = tuple[tuple[str, float], ...]
"""One month's allocation: (TOU period, fraction of that month's kWh)."""


def every_month(shares: Shares) -> tuple[Shares, ...]:
    return (shares,) * 12


@cache
def _series(quarter: Quarter, by_month: tuple[Shares, ...]) -> IntervalSeries:
    """N kWh/month spread over the TOU periods in the proportions given, month by month.

    Within one period the kWh is spread evenly over that period's hours in that month; the
    monthly total is exactly the published N whatever the split. Per-month allocations
    (rather than one shape for the year) are what let the generation envelope pick each
    month's own cheapest and dearest period instead of assuming the ordering is the same all
    year.

    The shape is degenerate on purpose -- it exists to interrogate a spec's arithmetic, and
    never stands in for a household.
    """
    months = quarter.months()
    first, last = months[0], months[-1]
    idx = pd.date_range(
        pd.Timestamp(f"{first[0]}-{first[1]:02d}-01", tz=LOCAL_TZ),
        pd.Timestamp(f"{last[0]}-{last[1]:02d}-{calendar.monthrange(*last)[1]}", tz=LOCAL_TZ)
        + pd.Timedelta(days=1),
        freq="h",
        inclusive="left",
    )
    codes = period_codes(quarter.delivery.tou, idx)
    stamp = idx.year.values * 100 + idx.month.values
    kwh = np.zeros(len(idx))
    for (year, month), shares in zip(months, by_month, strict=True):
        in_month = stamp == year * 100 + month
        assert abs(sum(share for _, share in shares) - 1.0) < 1e-9, shares
        for period, share in shares:
            if share == 0.0:
                continue
            sel = in_month & (codes == period)
            n = int(sel.sum())
            assert n, f"{period} has no hours in {year}-{month:02d}"
            kwh[sel] = quarter.monthly_kwh * share / n
    frame = pd.DataFrame({COL_KWH: kwh, COL_ESTIMATED: False}, index=idx)
    return IntervalSeries(
        utility=Utility.SDGE,
        interval=pd.Timedelta(hours=1).to_pytimedelta(),
        meta=MeterMeta(utility=Utility.SDGE),
        frame=frame,
    )


@cache
def monthly_totals(
    quarter: Quarter,
    by_month: tuple[Shares, ...],
    layer: str,
    *,
    care: bool = False,
    territory: str | None = None,
    service: Service = PCIA_EXCLUDED_BY_INFERENCE,
    vintage: str | None = None,
) -> tuple[float, ...]:
    """The twelve monthly bills the engine computes for this allocation."""
    specs = [quarter.delivery if layer == "delivery" else quarter.generation]
    series = _series(quarter, by_month)
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
        for year, month in quarter.months()
    )


def annual_average_month(quarter: Quarter, by_month: tuple[Shares, ...], layer: str, **kw) -> float:
    """SDG&E's own unit: "Represents an annual average bill"."""
    return statistics.fmean(monthly_totals(quarter, by_month, layer, **kw))


PURE: dict[str, tuple[Shares, ...]] = {p: every_month(((p, 1.0),)) for p in PERIODS}

# Five allocations of the same kWh/month, from "everything in the most expensive hours" to
# "everything in the cheapest" -- the widest spread of load shapes the schedule admits.
SHAPES: dict[str, tuple[Shares, ...]] = {
    "all_on_peak": PURE["on_peak"],
    "all_off_peak": PURE["off_peak"],
    "all_super_off_peak": PURE["super_off_peak"],
    "by_hour_count": every_month(
        (("on_peak", 5 / 24), ("off_peak", 1 / 3), ("super_off_peak", 1 - 5 / 24 - 1 / 3))
    ),
    "evening_heavy": every_month((("on_peak", 0.5), ("off_peak", 0.3), ("super_off_peak", 0.2))),
}
BY_HOUR_COUNT = SHAPES["by_hour_count"]


# --- derived measurements ---------------------------------------------------------------


@cache
def delivery_by_territory(quarter: Quarter, care: bool) -> dict[str, float]:
    """Every baseline territory the spec publishes, priced on the delivery layer."""
    return {
        territory: annual_average_month(
            quarter, BY_HOUR_COUNT, "delivery", territory=territory, care=care
        )
        for territory in quarter.territories
    }


def territory_residuals(quarter: Quarter, care: bool) -> list[tuple[float, str, float]]:
    """(|residual|, territory, priced), nearest the published delivery figure first."""
    expected = quarter.published("delivery_only", care)
    priced = delivery_by_territory(quarter, care)
    return sorted((abs(v - expected), t, v) for t, v in priced.items())


@cache
def envelope(quarter: Quarter, care: bool) -> tuple[float, float, tuple[str, ...], tuple[str, ...]]:
    """(cheapest, dearest) annual-average generation cost achievable at the published kWh.

    Taken month by month over EVERY period rather than assuming super-off-peak is cheapest
    and on-peak dearest all year. That assumption is true of these specs and is pinned by a
    test of its own, but hard-coding it made session 25's first draft report "infeasible" for
    a spec whose on-peak and super-off-peak rates had merely been swapped -- an allocation
    permutation that leaves the achievable set identical. A feasibility test that fails for
    the wrong reason is worse than no test, because infeasibility is this tier's only strong
    verdict.

    Both endpoints are allocations the schedule actually admits, so they are attained rather
    than asymptotic. Everything between is attained too: generation on this schedule is purely
    volumetric -- no fixed charge, no baseline, no minimum bill -- so the cost of mixing two
    allocations is the mix of their costs.
    """
    by_period = {p: monthly_totals(quarter, PURE[p], "generation", care=care) for p in PERIODS}
    n = len(quarter.months())
    cheapest = tuple(min(PERIODS, key=lambda p: by_period[p][i]) for i in range(n))
    dearest = tuple(max(PERIODS, key=lambda p: by_period[p][i]) for i in range(n))
    low = statistics.fmean(by_period[p][i] for i, p in enumerate(cheapest))
    high = statistics.fmean(by_period[p][i] for i, p in enumerate(dearest))
    return low, high, cheapest, dearest


def implied_generation(quarter: Quarter, care: bool) -> float:
    """Published bundled minus published delivery-only. Carries DERIVED_BAND, not PUBLISHED_BAND."""
    return quarter.published("bundled", care) - quarter.published("delivery_only", care)
