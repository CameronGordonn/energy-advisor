"""N-period, day-type-aware TOU: rule resolution, usage bucketing, schema guards.

The two-period PG&E form (``peak_hours``) must keep behaving exactly as before — that is
covered by :mod:`tests.tariffs.test_bill` and the golden-bill reconciliation. This module
covers what the rule form adds: three periods, weekday-vs-weekend tables, month-conditional
carve-outs, observed holidays, and the SDG&E 130%-of-baseline credit.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from tariffs.bill import _usage, compute_layer
from tariffs.holidays import (
    HolidayCalendar,
    UnverifiedHolidayCalendarError,
    holiday_dates,
    register,
)
from tariffs.schema import Baseline, Season, TariffSpec, TouDef

from .test_bill import SPEC, make_series

# SDG&E TOU-DR1 period structure (Cal. P.U.C. Sheets 29952-29955-E), used here as a
# structural fixture only — the rate values are placeholders, not tariff numbers.
SDGE_TOU = {
    "rules": [
        {"period": "on_peak", "hours": [[16, 21]], "days": "all"},
        {"period": "super_off_peak", "hours": [[0, 6]], "days": "weekday"},
        {
            "period": "super_off_peak",
            "hours": [[10, 14]],
            "days": "weekday",
            "months": [3, 4],
        },
        {"period": "super_off_peak", "hours": [[0, 14]], "days": "weekend"},
    ],
    "default_period": "off_peak",
}


def _sdge_spec(**overrides) -> TariffSpec:
    periods = ["on_peak", "super_off_peak", "off_peak"]
    return TariffSpec.model_validate(
        {
            **SPEC,
            "tou": {**SDGE_TOU, **overrides.pop("tou", {})},
            "energy": {
                f"{s}_{p}": {"standard": 0.10} for s in ("summer", "winter") for p in periods
            },
            "fixed_per_day": None,
            "baseline": None,
            **overrides,
        }
    )


# --- rule resolution -------------------------------------------------------


def test_three_periods_in_bill_line_order():
    tou = TouDef.model_validate(SDGE_TOU)
    assert tou.periods == ["on_peak", "super_off_peak", "off_peak"]
    assert tou.label("super_off_peak") == "Super Off Peak"


def test_first_match_wins_on_peak_beats_weekend_super_off_peak():
    # The weekend rule covers 00:00-14:00 and on-peak covers 16:00-21:00 — they do not
    # overlap, but on-peak is listed first, so ordering is what makes 16:00 on-peak on a
    # Saturday rather than falling through to the default.
    tou = TouDef.model_validate(SDGE_TOU)
    assert tou.period_for(17, month=7, weekday=False) == "on_peak"
    assert tou.period_for(13, month=7, weekday=False) == "super_off_peak"
    assert tou.period_for(15, month=7, weekday=False) == "off_peak"


def test_weekday_and_weekend_tables_differ():
    tou = TouDef.model_validate(SDGE_TOU)
    # 09:00 weekday is off-peak; 09:00 weekend is super-off-peak.
    assert tou.period_for(9, month=7, weekday=True) == "off_peak"
    assert tou.period_for(9, month=7, weekday=False) == "super_off_peak"
    # 03:00 is super-off-peak either way.
    assert tou.period_for(3, month=7, weekday=True) == "super_off_peak"
    assert tou.period_for(3, month=7, weekday=False) == "super_off_peak"


def test_month_conditional_carveout_applies_only_in_march_and_april():
    tou = TouDef.model_validate(SDGE_TOU)
    assert tou.period_for(11, month=3, weekday=True) == "super_off_peak"
    assert tou.period_for(11, month=4, weekday=True) == "super_off_peak"
    assert tou.period_for(11, month=5, weekday=True) == "off_peak"


def test_legacy_peak_hours_normalizes_to_two_periods():
    tou = TouDef.model_validate({"peak_hours": [16, 17, 18, 19, 20]})
    assert tou.periods == ["peak", "offpeak"]
    assert tou.rules[0].hours == [(16, 21)]  # contiguous hours collapse to one window
    assert tou.label("peak") == "Peak" and tou.label("offpeak") == "Off Peak"
    assert not tou.day_type_sensitive
    assert tou.period_for(17, month=1, weekday=False) == "peak"


def test_legacy_and_rule_forms_are_mutually_exclusive():
    with pytest.raises(ValidationError, match="either peak_hours"):
        TouDef.model_validate({"peak_hours": [16], **SDGE_TOU})


# --- usage bucketing -------------------------------------------------------


def test_usage_buckets_by_day_type():
    spec = _sdge_spec()
    # 2026-07-04 is a Saturday; 2026-07-06 a Monday. One day of each, 1 kWh/hour.
    sat = _usage(make_series("2026-07-04", 1), spec, date(2026, 7, 4), date(2026, 7, 4))
    mon = _usage(make_series("2026-07-06", 1), spec, date(2026, 7, 6), date(2026, 7, 6))
    assert sat == {"on_peak": 5.0, "super_off_peak": 14.0, "off_peak": 5.0}
    assert mon == {"on_peak": 5.0, "super_off_peak": 6.0, "off_peak": 13.0}
    assert sum(sat.values()) == sum(mon.values()) == 24.0


def test_usage_buckets_month_conditional_carveout():
    spec = _sdge_spec()
    # 2026-04-06 and 2026-05-04 are both Mondays. April gets the 10:00-14:00 carve-out.
    apr = _usage(make_series("2026-04-06", 1), spec, date(2026, 4, 6), date(2026, 4, 6))
    may = _usage(make_series("2026-05-04", 1), spec, date(2026, 5, 4), date(2026, 5, 4))
    assert apr["super_off_peak"] == 10.0 and apr["off_peak"] == 9.0
    assert may["super_off_peak"] == 6.0 and may["off_peak"] == 13.0


def test_empty_period_still_billed_as_a_zero_line():
    """A period with no usage keeps its line, so the bill shows every period."""
    spec = _sdge_spec()
    # 03:00-04:00 only: super-off-peak. Slice one hour out of a one-day series.
    series = make_series("2026-07-06", 1)
    series.frame.loc[series.frame.index.hour != 3, "kwh"] = 0.0
    u = _usage(series, spec, date(2026, 7, 6), date(2026, 7, 6))
    assert u == {"on_peak": 0.0, "super_off_peak": 1.0, "off_peak": 0.0}
    lb = compute_layer(series, spec, date(2026, 7, 6), date(2026, 7, 6))
    assert {li.name for li in lb.line_items} >= {
        "Energy On Peak",
        "Energy Super Off Peak",
        "Energy Off Peak",
    }


# --- holidays --------------------------------------------------------------

_TEST_CAL = register(
    HolidayCalendar(
        name="_test_july4",
        citation="test fixture",
        fixed=[(7, 4)],
        floating=[(9, 0, 1)],  # first Monday in September
    )
)


def test_holiday_dates_shift_off_the_weekend():
    # 2026-07-04 is a Saturday -> observed Friday 2026-07-03.
    assert date(2026, 7, 3) in holiday_dates("_test_july4", 2026)
    assert date(2026, 9, 7) in holiday_dates("_test_july4", 2026)  # 1st Monday in Sept


def test_holiday_is_billed_on_the_weekend_table():
    plain = _sdge_spec()
    with_hols = _sdge_spec(tou={"holiday_calendar": "_test_july4"})
    d = date(2026, 7, 3)  # observed July 4th, a Friday
    series = make_series("2026-07-03", 1)
    assert _usage(series, plain, d, d)["super_off_peak"] == 6.0  # weekday table
    assert _usage(series, with_hols, d, d)["super_off_peak"] == 14.0  # weekend table


def test_unknown_holiday_calendar_raises_at_spec_load():
    with pytest.raises(ValidationError, match="unknown holiday calendar"):
        _sdge_spec(tou={"holiday_calendar": "not_a_calendar"})


def test_unverified_holiday_calendar_raises_at_spec_load():
    register(HolidayCalendar(name="_test_unverified", citation="pending", verified=False))
    with pytest.raises(ValidationError, match="UNVERIFIED"):
        _sdge_spec(tou={"holiday_calendar": "_test_unverified"})
    with pytest.raises(UnverifiedHolidayCalendarError):
        holiday_dates("_test_unverified", 2026)


# --- schema guards ---------------------------------------------------------


def test_energy_must_cover_every_season_and_period():
    with pytest.raises(ValidationError, match="missing rate"):
        TariffSpec.model_validate(
            {
                **SPEC,
                "tou": SDGE_TOU,
                "energy": {"summer_on_peak": {"standard": 0.1}},
                "baseline": None,
            }
        )


def test_energy_rejects_an_unknown_key():
    periods = ["on_peak", "super_off_peak", "off_peak"]
    energy = {f"{s}_{p}": {"standard": 0.1} for s in ("summer", "winter") for p in periods}
    with pytest.raises(ValidationError, match="unknown key"):
        TariffSpec.model_validate(
            {**SPEC, "tou": SDGE_TOU, "energy": energy | {"winter_typo": {"standard": 0.1}}}
        )


def test_partial_tou_adder_raises_rather_than_falling_back_to_flat():
    """A TOU adder that prices some periods and not others must not invent the rest."""
    spec = _sdge_spec(
        adders=[
            {
                "name": "Partial",
                "per_kwh_tou": {"summer_on_peak": -0.10, "summer_off_peak": -0.05},
                "per_kwh": -0.07,
                "citation": "test",
            }
        ]
    )
    with pytest.raises(ValueError, match="super_off_peak"):
        compute_layer(make_series("2026-07-06", 1), spec, date(2026, 7, 6), date(2026, 7, 6))


# --- baseline multiplier ---------------------------------------------------


def test_baseline_multiplier_credits_up_to_130_percent():
    b = Baseline(
        territory="X",
        allowance_kwh_per_day_summer=10.0,
        allowance_kwh_per_day_winter=10.0,
        credit_per_kwh={"standard": -0.05},
        allowance_multiplier=1.30,
    )
    # 30 days x 10 kWh x 1.30 = 390 kWh creditable.
    assert b.credited_kwh(Season.SUMMER, 30, 500.0) == 390.0
    assert b.credited_kwh(Season.SUMMER, 30, 200.0) == 200.0  # usage below the cap


def test_baseline_multiplier_defaults_to_pge_100_percent():
    b = Baseline(
        territory="T",
        allowance_kwh_per_day_summer=7.1,
        allowance_kwh_per_day_winter=12.9,
        credit_per_kwh={"standard": -0.0814},
    )
    assert b.allowance_multiplier == 1.0
    assert b.credited_kwh(Season.WINTER, 30, 1000.0) == pytest.approx(387.0)
