"""Billing-function tests: exact synthetic reconciliation + real golden bills."""

from __future__ import annotations

import glob
from datetime import date

import pandas as pd
import pytest

from greenbutton.models import COL_ESTIMATED, COL_KWH, LOCAL_TZ, IntervalSeries, MeterMeta, Utility
from tariffs.bill import _rate_subperiods, _season_subperiods, compute_bill, compute_layer
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


# --- rate-version splitting within one billing period ----------------------


def _versioned_spec(effective: str, peak_rate: float) -> TariffSpec:
    """A minimal winter-only delivery spec with an 8.5% pretax surcharge."""
    return TariffSpec.model_validate(
        {
            **SPEC,
            "effective_date": effective,
            "energy": {
                "winter_peak": {"standard": peak_rate},
                "winter_offpeak": {"standard": peak_rate},
                "summer_peak": {"standard": peak_rate},
                "summer_offpeak": {"standard": peak_rate},
            },
            "fixed_per_day": None,
            "baseline": None,
            "surcharges": [{"name": "UUT", "rate": 0.085, "of": "pretax", "citation": "test"}],
        }
    )


def test_rate_subperiods_split_at_version_within_one_season():
    v1 = _versioned_spec("2026-01-01", 0.40)
    v2 = _versioned_spec("2026-01-15", 0.30)
    runs = _rate_subperiods(date(2026, 1, 10), date(2026, 1, 20), [v1, v2])
    assert [(r[0].effective_date, r[1], r[2], r[3]) for r in runs] == [
        (date(2026, 1, 1), Season.WINTER, date(2026, 1, 10), date(2026, 1, 14)),
        (date(2026, 1, 15), Season.WINTER, date(2026, 1, 15), date(2026, 1, 20)),
    ]


def test_surcharge_scoped_per_subperiod_not_per_season():
    # Two versions, same (winter) season, split at Jan 15. The 8.5% surcharge must apply
    # to each run's own energy subtotal — not the running season total (regression: a
    # season-tag filter double-counted the first run in the second run's surcharge base).
    v1 = _versioned_spec("2026-01-01", 0.40)
    v2 = _versioned_spec("2026-01-15", 0.30)
    # 1 kWh/hour, 24 kWh/day. Days 10-14 on v1 (5 days), 15-20 on v2 (6 days).
    series = make_series("2026-01-10", 11)
    lb = compute_layer(series, [v1, v2], date(2026, 1, 10), date(2026, 1, 20))
    energy = lb.bucket()["Energy Peak"] + lb.bucket()["Energy Off Peak"]
    assert lb.bucket()["UUT"] == round(0.085 * energy + 1e-9, 2)


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


def test_pge_etou_c_non_care_delivery_runs_and_is_sane():
    """The real 2026-03-01 E-TOU-C delivery spec must now bill a *non-CARE* customer.

    Regression for Workstream B: `fixed_per_day.standard` (the Income Tier 3 Base Services
    Charge, $0.79343/day) was filled from Cal. P.U.C. Sheet 61364-E, unblocking non-CARE
    billing. Before the fix this raised "no standard value". This is a sanity/no-raise
    check (not a golden reconciliation — no non-CARE bill exists yet): every headline line
    is present with the tariff-sheet rate, and the non-CARE bill exceeds the CARE bill on
    the same usage (no CARE discount, higher fixed charge).
    """
    from tariffs.loader import load_spec_versions
    from tariffs.schema import Layer

    deliv = load_spec_versions("E-TOU-C", Layer.DELIVERY)
    # 20 winter days, 1 kWh/hour => 480 kWh. April 2026 has no DST transition, so the split
    # is clean; the 2026-03-01 version (Base Services Charge era) is the one selected.
    series = make_series("2026-04-01", 20)
    ps, pe = date(2026, 4, 1), date(2026, 4, 20)

    non_care = compute_layer(series, deliv, ps, pe, care=False)
    b = non_care.bucket()

    # Base Services Charge = Income Tier 3 * days.
    assert b["Base Services Charge"] == round(0.79343 * 20 + 1e-9, 2)
    # Energy at the tariff-sheet winter standard rates: peak 16-20 (5h) => 100 kWh @ 0.39757,
    # off-peak 380 kWh @ 0.36757.
    assert b["Energy Peak"] == round(100 * 0.39757 + 1e-9, 2)
    assert b["Energy Off Peak"] == round(380 * 0.36757 + 1e-9, 2)
    assert b["Baseline Credit"] < 0
    assert any("Power Charge Indifference" in name for name in b)  # PCIA adder present
    assert "CARE Discount" not in b  # non-CARE customer
    assert non_care.total > 0

    # Same usage under CARE should cost less (CARE discount + lower Tier-1 fixed charge).
    care = compute_layer(series, deliv, ps, pe, care=True)
    assert care.total < non_care.total


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
    from tariffs.loader import load_spec_versions
    from tariffs.schema import Layer

    series, _ = parse_pge_interval_csv(_interval_file())
    deliv = load_spec_versions("E-TOU-C", Layer.DELIVERY)
    gen = load_spec_versions("MBRETCH1", Layer.GENERATION)
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
