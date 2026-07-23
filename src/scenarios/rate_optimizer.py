"""M2 rate optimizer: re-simulate a year of real intervals under every eligible schedule.

Ranks candidate (delivery schedule x generation provider) pairs by annual cost, using the
customer's own interval data — never a modeled load profile (CLAUDE.md invariant 6). All
candidates are billed at the rates **currently in effect** rather than at the historical
rate versions each month actually saw, because the question is "what should I be on going
forward", and mixing rate vintages across candidates would make the comparison meaningless.

Honest-broker notes that the report must carry (invariant 2):
- Eligibility is not cost. EV2-A is only available to households with a plug-in EV, so it
  is ranked but flagged conditional.
- A ranking is only as good as its assumptions. The Santa Cruz UUT Adjustment mechanism is
  unverified, so every ranking is recomputed under each plausible alternative and the
  report states whether the order changes (see :class:`UutPolicy`).
- The winner is reported with the usage shift that would overturn it, not just the delta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, ConfigDict

from greenbutton.models import COL_KWH, IntervalSeries
from tariffs.bill import compute_bill
from tariffs.loader import load_specs
from tariffs.schema import Layer

UUT_LINE = "City of Santa Cruz Utility Users' Tax"

# --- the Santa Cruz UUT Adjustment assumption (HANDOFF open decision 4) -----------------
#
# Every statement carries a negative "Utility Users' Tax Adjustment" that cancels most of
# the 8.5% gross UUT. Its mechanism is not derivable from the bills and no municipal
# source has been found, but M2 cannot read it off a bill that does not exist, so it needs
# an explicit modeling assumption rather than a silent default.
#
# Fitted across all 11 statements (delivery + generation adjustment combined), coefficient
# of variation of the residual under each candidate mechanism:
#     fixed $ per bill      mean -6.43909   CV 0.0839
#     fixed $ per day       mean -0.21649   CV 0.0802   <- adopted
#     fixed $ per kWh       mean -0.01706   CV 0.2066
#     fraction of gross UUT mean -0.7890    CV 0.1940
#     fraction of net bill  mean -0.0724    CV 0.3300
#
# ADOPTED: a fixed credit of $0.21649 per billing day. It is both the tightest fit and the
# only near-constant form that handles the 24-32 day spread in billing-period lengths.
# The mechanism remains UNVERIFIED.
#
# WHY THIS MATTERS LESS THAN IT LOOKS: a per-day credit is schedule-INDEPENDENT — it adds
# the same constant to every candidate, so it cannot reorder the ranking, only shift every
# total equally. The two rival mechanisms that ARE schedule-dependent (no adjustment at
# all; a proportional rebate of gross UUT) are modeled below so the report can show
# whether the ranking survives them.
UUT_ADJ_PER_DAY = -0.21649
UUT_ADJ_FRACTION_OF_GROSS = -0.7890


class UutPolicy(StrEnum):
    PER_DAY = "per_day"  # adopted assumption; schedule-independent
    NONE = "none"  # no adjustment: the full 8.5% gross UUT stands
    PROPORTIONAL = "proportional"  # rebate a fixed fraction of each bill's gross UUT

    @property
    def description(self) -> str:
        return {
            UutPolicy.PER_DAY: f"fixed ${-UUT_ADJ_PER_DAY:.5f}/day credit (adopted; best fit)",
            UutPolicy.NONE: "no adjustment — full 8.5% UUT stands",
            UutPolicy.PROPORTIONAL: (
                f"rebate {-UUT_ADJ_FRACTION_OF_GROSS:.1%} of gross UUT (mean observed)"
            ),
        }[self]


@dataclass(frozen=True)
class Candidate:
    """One shoppable plan: a PG&E delivery schedule plus its generation supplier."""

    name: str
    delivery: str
    generation: str
    eligibility: str | None = None  # non-None => conditional, must be flagged in the report


# Cameron's household: PG&E delivery + 3CE (CCA) generation, Santa Cruz, CARE, Territory T.
# Each PG&E schedule is paired with 3CE's *matched* generation schedule — switching the
# delivery schedule switches the CCA schedule too, and 3CE prices each one's own TOU
# windows separately, so holding generation fixed would be wrong.
PGE_3CE_CANDIDATES: tuple[Candidate, ...] = (
    Candidate("E-TOU-C + 3CE", "E-TOU-C", "MBRETCH1"),
    Candidate("E-TOU-D + 3CE", "E-TOU-D", "3CE-E-TOU-D"),
    Candidate("E-1 (tiered) + 3CE", "E-1", "3CE-E-1"),
    Candidate(
        "EV2-A + 3CE",
        "EV2-A",
        "3CE-EV2-A",
        eligibility="requires a plug-in electric vehicle (PG&E Schedule EV2 applicability)",
    ),
)


class PeriodCost(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_start: date
    period_end: date
    days: int
    kwh: float
    delivery: float
    generation: float
    gross_uut: float
    uut_adjustment: float
    total: float


class PlanCost(BaseModel):
    """A candidate's simulated cost over the whole modeled year."""

    model_config = ConfigDict(frozen=True)

    name: str
    delivery: str
    generation: str
    eligibility: str | None
    periods: list[PeriodCost]
    components: dict[str, float] = {}
    """Annual $ per bill line, summed over every period and both layers.

    This is what turns a ranking into an explanation: the reason one schedule beats
    another is almost never "its peak rate is lower", it is one or two components (here,
    E-TOU-C's baseline credit, which E-TOU-D and EV2-A do not have at all).
    """

    @property
    def total(self) -> float:
        return round(sum(p.total for p in self.periods), 2)

    @property
    def kwh(self) -> float:
        return round(sum(p.kwh for p in self.periods), 1)

    @property
    def days(self) -> int:
        return sum(p.days for p in self.periods)


# --- simulation ------------------------------------------------------------------------


def simulate(
    series: IntervalSeries,
    candidate: Candidate,
    periods: list[tuple[date, date]],
    *,
    care: bool,
    as_of: date,
    policy: UutPolicy = UutPolicy.PER_DAY,
    specs_dir: str = "src/tariffs/specs",
) -> PlanCost:
    """Bill ``periods`` of real interval data under one candidate at ``as_of`` rates."""
    deliv = load_specs(candidate.delivery, Layer.DELIVERY, on=as_of, specs_dir=specs_dir)
    gen = load_specs(candidate.generation, Layer.GENERATION, on=as_of, specs_dir=specs_dir)

    out: list[PeriodCost] = []
    components: dict[str, float] = {}
    for ps, pe in periods:
        days = (pe - ps).days + 1
        # Bill once with no adjustment so the gross UUT is readable, then apply the policy.
        bill = compute_bill(series, [deliv, gen], ps, pe, care=care, allow_before_effective=True)
        gross_uut = sum(layer.bucket().get(UUT_LINE, 0.0) for layer in bill.layers)
        adj = _uut_adjustment(policy, days=days, gross_uut=gross_uut)
        for layer in bill.layers:
            tag = "delivery" if layer.layer is Layer.DELIVERY else "generation"
            for line, amt in layer.bucket().items():
                components[f"{tag}: {line}"] = components.get(f"{tag}: {line}", 0.0) + amt
        components["UUT Adjustment (modeled)"] = (
            components.get("UUT Adjustment (modeled)", 0.0) + adj
        )
        out.append(
            PeriodCost(
                period_start=ps,
                period_end=pe,
                days=days,
                kwh=bill.total_kwh,
                delivery=bill.layers[0].total,
                generation=bill.layers[1].total,
                gross_uut=round(gross_uut, 2),
                uut_adjustment=round(adj, 2),
                total=round(bill.total + adj, 2),
            )
        )
    return PlanCost(
        name=candidate.name,
        delivery=candidate.delivery,
        generation=candidate.generation,
        eligibility=candidate.eligibility,
        periods=out,
        components={k: round(v, 2) for k, v in components.items()},
    )


def explain(winner: PlanCost, other: PlanCost, *, top: int = 6) -> list[tuple[str, float]]:
    """The largest per-component contributions to ``other.total - winner.total``.

    Positive means the component costs more under ``other``. Components absent from one
    plan (E-TOU-D has no baseline credit at all) count at their full value, which is
    usually the whole story.
    """
    keys = set(winner.components) | set(other.components)
    diffs = [
        (k, round(other.components.get(k, 0.0) - winner.components.get(k, 0.0), 2)) for k in keys
    ]
    diffs = [d for d in diffs if abs(d[1]) >= 0.5]
    return sorted(diffs, key=lambda kv: -abs(kv[1]))[:top]


def _uut_adjustment(policy: UutPolicy, *, days: int, gross_uut: float) -> float:
    if policy is UutPolicy.NONE:
        return 0.0
    if policy is UutPolicy.PER_DAY:
        return days * UUT_ADJ_PER_DAY
    return gross_uut * UUT_ADJ_FRACTION_OF_GROSS


def rank(
    series: IntervalSeries,
    periods: list[tuple[date, date]],
    *,
    care: bool,
    as_of: date,
    candidates: tuple[Candidate, ...] = PGE_3CE_CANDIDATES,
    policy: UutPolicy = UutPolicy.PER_DAY,
    specs_dir: str = "src/tariffs/specs",
) -> list[PlanCost]:
    """Cheapest first."""
    plans = [
        simulate(series, c, periods, care=care, as_of=as_of, policy=policy, specs_dir=specs_dir)
        for c in candidates
    ]
    return sorted(plans, key=lambda p: p.total)


# --- sensitivity -----------------------------------------------------------------------


def scale_hours(series: IntervalSeries, hours: range, factor: float) -> IntervalSeries:
    """A copy of ``series`` with usage in the given local clock hours scaled.

    Used to answer "how much would evening usage have to change to flip the ranking?".
    Only the kWh column moves; timestamps, gaps and estimated flags are untouched, so the
    counterfactual is still the customer's own shape rather than a synthetic profile.
    """
    frame = series.frame.copy()
    mask = frame.index.hour.isin(list(hours))
    frame.loc[mask, COL_KWH] = frame.loc[mask, COL_KWH] * factor
    return series.model_copy(update={"frame": frame})


def shift_hours(series: IntervalSeries, hours: range, factor: float) -> IntervalSeries:
    """Scale usage in ``hours`` by ``factor`` and remove the same kWh from the other hours.

    The load-neutral counterpart to :func:`scale_hours`: total annual kWh is preserved, so
    it isolates *when* energy is used from *how much*. If a plan only wins because the
    household uses less overall, that is not a rate-plan finding.
    """
    frame = series.frame.copy()
    mask = frame.index.hour.isin(list(hours))
    moved = float(frame.loc[mask, COL_KWH].sum()) * (factor - 1.0)
    other = float(frame.loc[~mask, COL_KWH].sum())
    if other <= 0:
        raise ValueError("no usage outside the shifted hours to draw from")
    frame.loc[mask, COL_KWH] = frame.loc[mask, COL_KWH] * factor
    frame.loc[~mask, COL_KWH] = frame.loc[~mask, COL_KWH] * (1.0 - moved / other)
    if (frame[COL_KWH] < 0).any():
        raise ValueError("shift factor too large: would drive non-evening usage negative")
    return series.model_copy(update={"frame": frame})


def max_shift_factor(series: IntervalSeries, hours: range) -> float:
    """Largest load-neutral multiplier on ``hours`` before all other usage reaches zero."""
    mask = series.frame.index.hour.isin(list(hours))
    inside = float(series.frame.loc[mask, COL_KWH].sum())
    outside = float(series.frame.loc[~mask, COL_KWH].sum())
    if inside <= 0:
        raise ValueError("no usage inside the shifted hours")
    return 1.0 + outside / inside


EVENING_HOURS = range(16, 21)  # 4-9 p.m., the window every CA residential peak sits inside


def flip_factor(
    series: IntervalSeries,
    periods: list[tuple[date, date]],
    winner: Candidate,
    challenger: Candidate,
    *,
    care: bool,
    as_of: date,
    hours: range = EVENING_HOURS,
    load_neutral: bool = False,
    lo: float = 0.05,
    hi: float = 6.0,  # clamped to what is physically reachable for a load-neutral shift
    tol: float = 0.005,
    specs_dir: str = "src/tariffs/specs",
) -> float | None:
    """Multiplier on ``hours`` usage at which ``challenger`` overtakes ``winner``.

    Returns ``None`` when no multiplier in ``[lo, hi]`` flips them — which is itself a
    result worth printing ("the ranking does not flip on evening usage alone").
    """
    reshape = shift_hours if load_neutral else scale_hours
    if load_neutral:
        # A load-neutral shift can only move as much energy into the window as exists
        # outside it; past that the counterfactual is physically impossible, not merely
        # unlikely. Clamp the search rather than extrapolating into negative usage.
        hi = min(hi, max_shift_factor(series, hours))

    def gap(f: float) -> float:
        s = reshape(series, hours, f)
        w = simulate(s, winner, periods, care=care, as_of=as_of, specs_dir=specs_dir).total
        c = simulate(s, challenger, periods, care=care, as_of=as_of, specs_dir=specs_dir).total
        return c - w  # > 0 while the winner still wins

    g_lo, g_hi = gap(lo), gap(hi)
    if g_lo * g_hi > 0:
        return None
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if gap(lo) * gap(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return round((lo + hi) / 2, 3)


# --- billing periods -------------------------------------------------------------------


def periods_from_series(series: IntervalSeries, *, days: int = 30) -> list[tuple[date, date]]:
    """Fixed-length billing periods covering the series — the fallback when no bills exist.

    Real statements are preferred (see ``scripts/rate_optimizer.py``, which reads the
    golden-bill fixtures) because actual meter-read dates set the per-day fixed charges.
    """
    start = series.frame.index[0].date()
    last = (series.frame.index[-1] + series.interval - pd.Timedelta(seconds=1)).date()
    out: list[tuple[date, date]] = []
    d = start
    while d <= last:
        end = min(d + timedelta(days=days - 1), last)
        out.append((d, end))
        d = end + timedelta(days=1)
    return out
