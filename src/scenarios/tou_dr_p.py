"""TOU-DR-P: report the break-even event count, never a forecast of event days.

**The decision this module encodes (session 27).** Reporting a saving for TOU-DR-P requires
knowing how many Reduce-Your-Use events SDG&E will call, and nothing can know that. Three
forecasting rules were considered and all three were rejected:

- *hottest N days* — needs a temperature feed, and conflates "hot" with "an event was
  called": 2021-23 and 2025-26 all had hot days and zero events, so it over-predicts;
- *last year's actual dates* — the answer flips on which year you land on (2025 gives zero
  and the schedule looks free; 2024 gives three);
- *Monte Carlo over count and timing* — right in spirit, but six complete years is a thin
  base and a Poisson fit misrepresents it badly (Poisson(2.0) puts ~14% on zero; the
  observed years are zero two thirds of the time).

Each commits to a number the evidence cannot support. So this module selects **no days at
all**. It reports what is actually knowable — the saving if no event is called, the cost of
each event, the count at which those cancel, and how often SDG&E has historically exceeded
that count — and lets the reader carry the risk explicitly.

That is CLAUDE.md invariant 2 applied literally: surface the break-even condition, not the
best case, and never a recommendation without its failure condition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from greenbutton.models import COL_KWH, IntervalSeries
from tariffs.bill import compute_bill
from tariffs.schema import Service, TariffSpec

#: RYU events SDG&E actually called, from its own year-end CPUC demand-response filings.
#: Sourced in `sdge_tou_dr_p_generation_2026-06-01.yaml`'s header; 2026 is partial.
#:
#: ⭐ The shape of this is the whole modeling problem. FOUR of the six complete years are
#: zero (and 2026 is zero through July), so zero is both the single most likely outcome AND
#: the assumption that makes the schedule look free. The mean of 2.0 is carried almost
#: entirely by 2020. Against a tariff cap of 18, which no observed year approaches.
EVENTS_CALLED: dict[int, int] = {2020: 9, 2021: 0, 2022: 0, 2023: 0, 2024: 3, 2025: 0}
PARTIAL_YEARS: dict[int, int] = {2026: 0}  # through July 2026; not a complete year
TARIFF_CAP = 18


@dataclass(frozen=True)
class BreakEven:
    """What TOU-DR-P costs and saves, with no assumption about which days are called."""

    zero_event_saving: float
    """$/period cheaper than TOU-DR1 if SDG&E calls no events. Negative means dearer."""

    cost_per_event_day: float
    """$ added by one event day, at this household's mean weekday 16:00-21:00 load."""

    break_even_events: float | None
    """Events at which the saving is exactly cancelled. None when there is no saving to
    cancel (the schedule already loses at zero events) or no event cost to cancel it."""

    events_called: dict[int, int]
    """The cited history, for the reader to judge the risk against."""

    @property
    def loses_at_zero_events(self) -> bool:
        return self.zero_event_saving <= 0

    @property
    def break_even_exceeds_the_cap(self) -> bool:
        """True when even a maximum-event year cannot cancel the saving — the only case in
        which TOU-DR-P is unconditionally better, and therefore worth naming."""
        return self.break_even_events is not None and self.break_even_events > TARIFF_CAP

    def years_that_would_have_lost(self) -> list[int]:
        """Complete years in which SDG&E called more events than this household could absorb."""
        if self.break_even_events is None:
            return sorted(self.events_called) if self.loses_at_zero_events else []
        return sorted(y for y, n in self.events_called.items() if n > self.break_even_events)

    def verdict(self) -> str:
        """One line, and it must be capable of saying no."""
        if self.loses_at_zero_events:
            return (
                f"TOU-DR-P costs ${-self.zero_event_saving:,.2f} MORE than TOU-DR1 even if no "
                "event is ever called. Do not switch; events can only widen the gap."
            )
        if self.break_even_exceeds_the_cap:
            return (
                f"TOU-DR-P saves ${self.zero_event_saving:,.2f} and breaks even only at "
                f"{self.break_even_events:.1f} events — beyond the tariff's cap of "
                f"{TARIFF_CAP}, so no lawful event year can cancel it."
            )
        lost = self.years_that_would_have_lost()
        history = (
            f"SDG&E exceeded that in {len(lost)} of the last {len(self.events_called)} years "
            f"({', '.join(str(y) for y in lost)})"
            if lost
            else f"SDG&E has not exceeded that in any of the last {len(self.events_called)} years"
        )
        return (
            f"TOU-DR-P saves ${self.zero_event_saving:,.2f} if no event is called, and each "
            f"event day costs ${self.cost_per_event_day:,.2f}. It breaks even at "
            f"{self.break_even_events:.1f} events. {history}."
        )


def _mean_weekday_event_window_kwh(series: IntervalSeries, start: date, end: date) -> float:
    """This household's average weekday 16:00-21:00 kWh, over the summer months in range.

    ⚠ **Deliberately an average, and that biases the answer in a known direction.** A real
    RYU event is called because the grid is stressed, i.e. on an unusually hot day, when an
    air-conditioned household draws MORE in those hours than its average. So the true cost
    of an event day is higher than this, the true break-even count is LOWER than reported,
    and every number here is therefore **optimistic for TOU-DR-P**. Stating the direction of
    a bias that cannot be quantified without a forecast is the honest form; silently using
    an average and calling it the answer is not.
    """
    frame = series.frame
    idx = frame.index
    mask = (
        (idx.date >= start)
        & (idx.date <= end)
        & (idx.hour >= 16)
        & (idx.hour < 21)
        & (idx.dayofweek < 5)
        & idx.month.isin([6, 7, 8, 9, 10])
    )
    window = frame.loc[mask, COL_KWH]
    if window.empty:
        raise ValueError(
            "no summer weekday 16:00-21:00 intervals in range; an RYU event can only be "
            "called in those hours, so a break-even cannot be computed from this period"
        )
    days = pd.Series(idx[mask].date).nunique()
    return float(window.sum()) / days


def break_even(
    series: IntervalSeries,
    *,
    dr1: list[TariffSpec],
    dr_p: list[TariffSpec],
    period_start: date,
    period_end: date,
    care: bool = False,
    territory: str,
) -> BreakEven:
    """Compare TOU-DR-P against TOU-DR1 over one period, selecting no event days.

    ``dr1`` and ``dr_p`` are each [delivery, generation]. Both are priced as BUNDLED:
    Schedule EECC-TOU-DR-P is closed to CCA and Direct Access customers, so a CCA household
    must be excluded from this comparison before it is run, not corrected afterwards.
    """
    kw = dict(care=care, service=Service.BUNDLED, territory=territory)
    cost_dr1 = compute_bill(series, dr1, period_start, period_end, event_days=[], **kw).total
    # event_days=[] is the explicit zero-event case, which the engine requires to be asked
    # for rather than defaulted to — the whole point being that "no events" is an assumption.
    cost_dr_p = compute_bill(series, dr_p, period_start, period_end, event_days=[], **kw).total

    adder = next(s.event_adder for s in dr_p if s.event_adder is not None)
    rate = adder.per_kwh.care if care else adder.per_kwh.standard
    per_event = _mean_weekday_event_window_kwh(series, period_start, period_end) * rate

    # Round first, then divide, so the three reported numbers are mutually consistent: a
    # reader checking saving / cost-per-event against the printed break-even gets the
    # printed answer. A break-even derived from unrounded inputs would not reproduce.
    saving = round(cost_dr1 - cost_dr_p, 2)
    per_event = round(per_event, 2)
    n = saving / per_event if saving > 0 and per_event > 0 else None
    return BreakEven(
        zero_event_saving=saving,
        cost_per_event_day=per_event,
        break_even_events=n,
        events_called=dict(EVENTS_CALLED),
    )
