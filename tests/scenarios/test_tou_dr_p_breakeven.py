"""TOU-DR-P break-even reporting: the decision not to forecast event days.

Session 27 settled the open decision HANDOFF carried since session 21. The engine half of
TOU-DR-P has been done for a while; what was missing was the reporting band, and it was
blocked on a modeling choice: WHICH days a forecast should assume. The answer chosen is
none. See `src/scenarios/tou_dr_p.py` for why each of the three forecasting rules was
rejected.

These tests use a degenerate probe series — a test probe of the engine's arithmetic, not a
customer computation, so CLAUDE.md invariant 6 is not in play (same boundary as
`tests/published_impacts`). No real SDG&E household exists yet.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from greenbutton.models import COL_ESTIMATED, COL_KWH, LOCAL_TZ, IntervalSeries, MeterMeta, Utility
from scenarios.tou_dr_p import EVENTS_CALLED, TARIFF_CAP, BreakEven, break_even
from tariffs.loader import SPECS_DIR, load_spec_file

TERRITORY = "coastal_basic"
START, END = date(2026, 6, 1), date(2027, 5, 31)


@pytest.fixture(scope="module")
def specs():
    dr1 = [
        load_spec_file(SPECS_DIR / "sdge_tou_dr1_delivery_2026-06-01.yaml"),
        load_spec_file(SPECS_DIR / "sdge_tou_dr1_generation_2026-06-01.yaml"),
    ]
    dr_p = [
        load_spec_file(SPECS_DIR / "sdge_tou_dr_p_delivery_2026-06-01.yaml"),
        load_spec_file(SPECS_DIR / "sdge_tou_dr_p_generation_2026-06-01.yaml"),
    ]
    return dr1, dr_p


def probe(evening_share: float, annual_kwh: float = 6000.0) -> IntervalSeries:
    """A year of hourly load with `evening_share` of it inside 16:00-21:00."""
    idx = pd.date_range(
        pd.Timestamp("2026-06-01", tz=LOCAL_TZ),
        pd.Timestamp("2027-06-01", tz=LOCAL_TZ),
        freq="h",
        inclusive="left",
    )
    evening = (idx.hour >= 16) & (idx.hour < 21)
    kwh = np.zeros(len(idx))
    kwh[evening] = annual_kwh * evening_share / evening.sum()
    kwh[~evening] = annual_kwh * (1 - evening_share) / (~evening).sum()
    return IntervalSeries(
        utility=Utility.SDGE,
        interval=pd.Timedelta(hours=1).to_pytimedelta(),
        meta=MeterMeta(utility=Utility.SDGE),
        frame=pd.DataFrame({COL_KWH: kwh, COL_ESTIMATED: False}, index=idx),
    )


def run(specs, evening_share: float, **kw) -> BreakEven:
    dr1, dr_p = specs
    return break_even(
        probe(evening_share),
        dr1=dr1,
        dr_p=dr_p,
        period_start=START,
        period_end=END,
        territory=TERRITORY,
        **kw,
    )


def test_it_reports_a_break_even_and_never_a_forecast(specs):
    """The decision, asserted as a property of the output: nothing here names a date.

    `BreakEven` has no field for event days, event dates or an expected count. It cannot
    express a forecast, which is stronger than choosing not to make one.
    """
    result = run(specs, evening_share=5 / 24)
    assert not hasattr(result, "expected_events")
    assert not hasattr(result, "event_days")
    assert set(vars(result)) == {
        "zero_event_saving",
        "cost_per_event_day",
        "break_even_events",
        "events_called",
    }


def test_the_zero_event_case_and_the_per_event_cost_are_both_reported(specs):
    """Neither number is useful alone. The saving without the event cost is the numerator
    only — which is exactly how a schedule like this gets mis-sold."""
    result = run(specs, evening_share=5 / 24)
    assert result.cost_per_event_day > 0
    assert result.break_even_events is not None
    assert result.break_even_events == pytest.approx(
        result.zero_event_saving / result.cost_per_event_day, rel=1e-9
    )


def test_the_verdict_can_say_no(specs):
    """⭐ CLAUDE.md invariant 2: the engine must be equally capable of outputting "don't".

    A household with very little evening load LOSES on TOU-DR-P before any event is called.
    The schedule flattens the summer curve rather than lowering it — its on-peak generation
    is cheaper than TOU-DR1's, but its off-peak and super-off-peak are dearer — so a load
    sitting mostly outside 16:00-21:00 pays for a discount it never collects. The verdict
    must say so outright rather than report a smaller saving.
    """
    result = run(specs, evening_share=0.05)
    assert result.loses_at_zero_events
    assert result.break_even_events is None
    assert "Do not switch" in result.verdict()
    assert result.years_that_would_have_lost() == sorted(EVENTS_CALLED)


def test_a_household_that_gains_gets_its_failure_condition_named(specs):
    """No recommendation without its failure condition. The verdict carries the count and
    the history in the same breath as the saving.

    At a 15% evening share the break-even is ~10.6 events — inside the tariff's cap of 18,
    so this saving is genuinely cancellable, and 2020's nine events came close.
    """
    result = run(specs, evening_share=0.15)
    assert not result.loses_at_zero_events
    assert result.break_even_events is not None
    assert result.break_even_events < TARIFF_CAP
    verdict = result.verdict()
    assert "breaks even" in verdict
    assert "SDG&E has not exceeded that" in verdict  # 9 < 10.6, narrowly


def test_the_three_regimes(specs):
    """⭐ The finding that makes break-even reporting worth more than a forecast would be.

    Break-even RISES with evening load, because a heavier 16:00-21:00 load earns a bigger
    everyday discount faster than it raises the per-event penalty. So TOU-DR-P splits
    households into three genuinely different situations, and which one you are in is a fact
    about your own meter, not about the tariff:

      * little evening load  -> loses at zero events. Don't switch.
      * moderate             -> gains, but a lawful event year can cancel it. Real risk.
      * heavy evening load   -> gains, and even the 18-event cap cannot cancel it.

    A single forecast number would collapse all three into one answer.
    """
    losing = run(specs, evening_share=0.05)
    at_risk = run(specs, evening_share=0.15)
    unconditional = run(specs, evening_share=0.60)

    assert losing.loses_at_zero_events
    assert at_risk.break_even_events is not None and at_risk.break_even_events < TARIFF_CAP
    assert unconditional.break_even_exceeds_the_cap
    assert "no lawful event year can cancel it" in unconditional.verdict()

    # And the ordering that drives it, asserted rather than described.
    assert at_risk.break_even_events < unconditional.break_even_events


def test_the_history_is_reported_and_is_the_reason_a_point_estimate_would_mislead():
    """⭐ Four of the six complete years are zero, so the modal year is also the one that
    makes the schedule look free — and the mean is carried almost entirely by 2020. Any
    single-number forecast lands on one side of that and hides the other."""
    counts = list(EVENTS_CALLED.values())
    assert len(counts) == 6
    assert counts.count(0) == 4
    assert max(counts) == 9 < TARIFF_CAP
    assert sum(counts) / len(counts) == pytest.approx(2.0, abs=0.01)


def test_the_break_even_is_an_upper_bound_because_events_land_on_hot_days(specs):
    """⚠ The bias is known, unquantifiable without a forecast, and its DIRECTION is stated.

    Per-event cost is exactly (mean weekday 16:00-21:00 kWh) x (RYU adder). A real event is
    called when the grid is stressed — a hot day, when an air-conditioned household draws
    MORE in those hours than its own average. That raises the denominator and leaves the
    everyday saving untouched, so the true break-even count is strictly LOWER than reported
    and every figure here is optimistic for TOU-DR-P.

    Asserted as the arithmetic it rests on: cost per event is linear in window load, so a
    household drawing k times its average on an event day breaks even at 1/k of the
    reported count.
    """
    result = run(specs, evening_share=0.15)
    dr_p = specs[1]
    adder = next(s.event_adder for s in dr_p if s.event_adder is not None)
    mean_window_kwh = result.cost_per_event_day / adder.per_kwh.standard
    assert mean_window_kwh > 0

    for k in (1.25, 1.5, 2.0):
        true_cost = mean_window_kwh * k * adder.per_kwh.standard
        true_n = result.zero_event_saving / true_cost
        assert true_n == pytest.approx(result.break_even_events / k, rel=1e-6)
        assert true_n < result.break_even_events


def test_care_uses_the_printed_care_adder_not_a_derived_one(specs):
    """The RYU adder's CARE value is PRINTED on SDG&E's own CARE table: 0.75 against 1.16.

    ⚠ It is very nearly, but not exactly, the 35% discount applied elsewhere on this
    schedule: 0.65 x 1.16 = 0.754, which SDG&E prints as 0.75. The gap is 0.004/kWh, about
    0.5% — small enough that a derived value would look right in any eyeball check and
    still be wrong. That closeness is the reason to assert on the printed number rather
    than trust a derivation, not a reason to stop caring.
    """
    standard = run(specs, evening_share=0.15)
    care = run(specs, evening_share=0.15, care=True)
    ratio = care.cost_per_event_day / standard.cost_per_event_day

    assert ratio == pytest.approx(0.75 / 1.16, abs=0.002)
    # The derived alternative, and how little separates them.
    derived = 0.65 * 1.16
    assert derived == pytest.approx(0.754, abs=1e-9)
    assert abs(derived - 0.75) == pytest.approx(0.004, abs=1e-9)


def test_a_period_with_no_summer_evening_hours_refuses_rather_than_returning_zero(specs):
    """An RYU event can only be called on a summer weekday afternoon. A winter-only period
    cannot produce a break-even, and returning one would be a confident wrong answer."""
    dr1, dr_p = specs
    with pytest.raises(ValueError, match="no summer weekday"):
        break_even(
            probe(0.2),
            dr1=dr1,
            dr_p=dr_p,
            period_start=date(2026, 12, 1),
            period_end=date(2027, 1, 31),
            territory=TERRITORY,
        )
