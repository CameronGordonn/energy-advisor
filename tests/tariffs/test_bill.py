"""Billing-function tests: exact synthetic reconciliation + real golden bills."""

from __future__ import annotations

import glob
from datetime import date

import pandas as pd
import pytest

from greenbutton.models import COL_ESTIMATED, COL_KWH, LOCAL_TZ, IntervalSeries, MeterMeta, Utility
from tariffs.bill import _season_subperiods, compute_bill, compute_layer
from tariffs.loader import load_spec_file
from tariffs.schema import Season, TariffSpec

# --- helpers ---------------------------------------------------------------


def make_series(start: str, n_days: int, kwh_per_hour: float = 1.0) -> IntervalSeries:
    idx = pd.date_range(start, periods=n_days * 24, freq="h", tz=LOCAL_TZ)
    frame = pd.DataFrame({COL_KWH: kwh_per_hour, COL_ESTIMATED: False}, index=idx)
    return IntervalSeries(
        utility=Utility.PGE,
        interval=pd.Timedelta(hours=1).to_pytimedelta(),
        meta=MeterMeta(utility=Utility.PGE),
        frame=frame,
    )


SPEC = {
    "schedule_id": "T",
    "name": "t",
    "provider": "PG&E",
    "layer": "delivery",
    "effective_date": "2026-01-01",
    "citation": "test",
    "seasons": {"summer_months": [6, 7, 8, 9], "winter_months": [1, 2, 3, 4, 5, 10, 11, 12]},
    "tou": {"peak_hours": [16, 17, 18, 19, 20]},
    "fixed_per_day": {"standard": 1.00, "care": 0.50},
    "energy": {
        "winter_peak": {"standard": 0.40, "care": 0.30},
        "winter_offpeak": {"standard": 0.30, "care": 0.20},
        "summer_peak": {"standard": 0.60},
        "summer_offpeak": {"standard": 0.45},
    },
    "baseline": {
        "territory": "T",
        "allowance_kwh_per_day_summer": 8.0,
        "allowance_kwh_per_day_winter": 10.0,
        "credit_per_kwh": {"standard": -0.05, "care": -0.03},
    },
}


# --- season proration ------------------------------------------------------


def test_season_subperiods_split_at_june_1():
    spec = TariffSpec.model_validate(SPEC)
    runs = _season_subperiods(date(2026, 5, 30), date(2026, 6, 2), spec)
    assert runs == [
        (Season.WINTER, date(2026, 5, 30), date(2026, 5, 31)),
        (Season.SUMMER, date(2026, 6, 1), date(2026, 6, 2)),
    ]


def test_single_season_one_run():
    spec = TariffSpec.model_validate(SPEC)
    runs = _season_subperiods(date(2026, 1, 1), date(2026, 1, 31), spec)
    assert len(runs) == 1 and runs[0][0] is Season.WINTER


# --- exact synthetic reconciliation ---------------------------------------


def test_delivery_line_items_exact():
    # 2 winter days, 1 kWh/hour => peak 10 kWh (5h*2), off 38 kWh, total 48.
    spec = TariffSpec.model_validate(SPEC)
    lb = compute_layer(make_series("2026-01-01", 2), spec, date(2026, 1, 1), date(2026, 1, 2))
    b = lb.bucket()
    assert b["Base Services Charge"] == 2.00  # 2 days * $1
    assert b["Energy Peak"] == 4.00  # 10 * 0.40
    assert b["Energy Off Peak"] == 11.40  # 38 * 0.30
    assert b["Baseline Credit"] == -1.00  # min(48, 20) * -0.05
    assert lb.total == 16.40
    assert "CARE Discount" not in b  # standard customer


def test_care_discount_exact():
    spec = TariffSpec.model_validate(SPEC)
    lb = compute_layer(
        make_series("2026-01-01", 2), spec, date(2026, 1, 1), date(2026, 1, 2), care=True
    )
    b = lb.bucket()
    # sum (care - std) x kWh: peak 10*(-0.10) + off 38*(-0.10) + baseline 20*(+0.02)
    assert b["CARE Discount"] == -4.40
    assert b["Energy Peak"] == 4.00  # still charged at standard
    assert b["Base Services Charge"] == 1.00  # 2 days * CARE $0.50/day
    assert lb.total == 11.00  # 1.00 + 4.00 + 11.40 - 1.00 - 4.40


def test_non_care_fixed_rate_missing_raises():
    # fixed charge has only a CARE value; billing a standard customer must refuse.
    care_only = {**SPEC, "fixed_per_day": {"care": 0.19713}}
    spec = TariffSpec.model_validate(care_only)
    with pytest.raises(ValueError, match="no standard value"):
        compute_layer(make_series("2026-01-01", 1), spec, date(2026, 1, 1), date(2026, 1, 1))


# --- real golden bills (skipped if the git-ignored export is absent) -------


def _interval_file() -> str | None:
    m = glob.glob("data/pge_electric_usage_interval_data*.csv")
    return m[0] if m else None


@pytest.mark.skipif(_interval_file() is None, reason="real PG&E export not present")
@pytest.mark.parametrize(
    "ps,pe,net_total",
    [
        (date(2026, 4, 28), date(2026, 5, 27), 112.20),  # stmt 2026-05-29, all winter
        (date(2026, 5, 28), date(2026, 6, 25), 79.47),  # stmt 2026-06-28, winter->summer
    ],
)
def test_real_bill_within_tolerance(ps, pe, net_total):
    from greenbutton import parse_pge_interval_csv
    from tariffs.bill import LineItem

    series, _ = parse_pge_interval_csv(_interval_file())
    deliv = load_spec_file("src/tariffs/specs/pge_etou_c_delivery_2026-03-01.yaml")
    gen = load_spec_file("src/tariffs/specs/cce_mbretch1_generation_2026-01-01.yaml")
    # observed UUT adjustments read from the statements
    adj = {
        (date(2026, 4, 28)): [-3.47, -2.81],
        (date(2026, 5, 28)): [-3.93, -2.78],
    }[ps]
    obs = [
        LineItem(name="UUT Adjustment (delivery)", amount=adj[0]),
        LineItem(name="UUT Adjustment (generation)", amount=adj[1]),
    ]
    bill = compute_bill(series, [deliv, gen], ps, pe, care=True, observed_adjustments=obs)
    assert abs(bill.total - net_total) < 2.0, f"modeled {bill.total} vs bill {net_total}"
