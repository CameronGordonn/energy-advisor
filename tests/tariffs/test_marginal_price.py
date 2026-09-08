"""`marginal_energy_price` — the price a dispatch model is allowed to arbitrage against.

The point of this helper is that the battery dispatch and the bill settlement read the
same specs. These tests pin the properties that make that true: it reproduces the
utility's own published retail total, it respects effective dates instead of
extrapolating, and it refuses inputs whose layers disagree about what period an hour is.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tariffs.bill import marginal_energy_price, period_codes
from tariffs.loader import SPECS_DIR, load_spec_file, load_spec_versions
from tariffs.schema import Layer

TZ = "America/Los_Angeles"

DELIVERY = load_spec_file(SPECS_DIR / "sdge_tou_dr1_delivery_2026-06-01.yaml")
GENERATION = load_spec_file(SPECS_DIR / "sdge_tou_dr1_generation_2026-06-01.yaml")


def _hours(day: str, n: int = 24) -> pd.DatetimeIndex:
    return pd.date_range(day, periods=n, freq="h", tz=TZ)


def test_reproduces_sdge_printed_total_electric_rate():
    """A Wednesday in July: the three windows must equal SDG&E's own printed totals."""
    idx = _hours("2026-07-01")
    price = marginal_energy_price([[DELIVERY], [GENERATION]], idx)
    assert price[17] == pytest.approx(0.68459, abs=1e-5)  # 5 p.m. on-peak
    assert price[15] == pytest.approx(0.46392, abs=1e-5)  # 3 p.m. off-peak
    assert price[11] == pytest.approx(0.37660, abs=1e-5)  # 11 a.m. super-off-peak
    assert price[3] == pytest.approx(0.37660, abs=1e-5)  # overnight super-off-peak


def test_care_prices_are_the_printed_care_totals():
    idx = _hours("2026-07-01")
    price = marginal_energy_price([[DELIVERY], [GENERATION]], idx, care=True)
    assert price[17] == pytest.approx(0.43553, abs=1e-5)
    assert price[11] == pytest.approx(0.23533, abs=1e-5)


def test_winter_season_is_priced_from_the_winter_row():
    """SDG&E's winter is Nov-May, so a January hour must not take a summer rate."""
    idx = _hours("2027-01-13")
    price = marginal_energy_price([[DELIVERY], [GENERATION]], idx)
    assert price[17] == pytest.approx(0.61014, abs=1e-5)
    assert price[11] == pytest.approx(0.43767, abs=1e-5)


def test_weekend_uses_the_weekend_table():
    """Saturday 8 a.m. is super-off-peak on the weekend table but off-peak on weekdays."""
    sat = _hours("2026-07-04")  # a Saturday, and a holiday
    wed = _hours("2026-07-01")
    assert marginal_energy_price([[DELIVERY], [GENERATION]], sat)[8] == pytest.approx(
        0.37660, abs=1e-5
    )
    assert marginal_energy_price([[DELIVERY], [GENERATION]], wed)[8] == pytest.approx(
        0.46392, abs=1e-5
    )


def test_holiday_on_a_weekday_takes_the_weekend_table():
    """Christmas Day 2026 falls on a Friday; SDG&E prices observed holidays as weekends."""
    idx = _hours("2026-12-25")
    price = marginal_energy_price([[DELIVERY], [GENERATION]], idx)
    assert price[8] == pytest.approx(0.43767, abs=1e-5)  # winter super-off-peak, not off-peak


def test_refuses_to_price_a_date_no_spec_version_covers():
    """Never fabricate: extrapolating a 2026-06-01 rate back to January would invent one."""
    with pytest.raises(ValueError, match="effective on 2026-01-01"):
        marginal_energy_price([[DELIVERY], [GENERATION]], _hours("2026-01-01"))


def test_rejects_layers_that_classify_hours_differently():
    """TOU-DR2 is two-period; pairing it with TOU-DR1's generation would price the same
    kWh into two different buckets, so it must raise rather than silently sum."""
    dr2 = load_spec_file(SPECS_DIR / "sdge_tou_dr2_delivery_2026-06-01.yaml")
    with pytest.raises(ValueError, match="must define the same TOU periods"):
        marginal_energy_price([[dr2], [GENERATION]], _hours("2026-07-01"))


def test_rejects_empty_input():
    with pytest.raises(ValueError, match="non-empty version list per layer"):
        marginal_energy_price([], _hours("2026-07-01"))
    with pytest.raises(ValueError, match="non-empty version list per layer"):
        marginal_energy_price([[DELIVERY], []], _hours("2026-07-01"))


def test_picks_the_version_in_effect_on_each_day():
    """A window straddling a rate change must switch price on the effective date, the way
    compute_bill splits a billing period — not use one version for the whole span."""
    versions = load_spec_versions("E-TOU-C", Layer.DELIVERY)
    assert len(versions) > 1, "this test needs a schedule with multiple committed vintages"
    cutover = versions[-1].effective_date
    idx = pd.date_range(
        pd.Timestamp(cutover, tz=TZ) - pd.Timedelta(days=1),
        periods=48,
        freq="h",
        tz=TZ,
    )
    price = marginal_energy_price([versions], idx)
    before, after = price[:24], price[24:]
    older, newer = versions[-2], versions[-1]
    season = older.seasons.season_for(cutover.month)
    period = period_codes(newer.tou, idx)[24]
    want_after = newer.energy_rate(season, period).for_customer(care=False)
    want_before = older.energy_rate(season, period).for_customer(care=False)
    assert want_before != want_after, "pick a cutover where the rate actually changed"
    assert after[0] == pytest.approx(want_after)
    assert before[0] == pytest.approx(want_before)
    assert not np.array_equal(before, after)


def test_marginal_price_excludes_fixed_charges_and_the_baseline_credit():
    """It is the cost of the NEXT kWh: no $/day terms, no credit that does not move with it."""
    idx = _hours("2026-07-01")
    price = marginal_energy_price([[DELIVERY], [GENERATION]], idx)
    energy_only = DELIVERY.energy_rate(DELIVERY.seasons.season_for(7), "on_peak").for_customer(
        care=False
    ) + GENERATION.energy_rate(GENERATION.seasons.season_for(7), "on_peak").for_customer(care=False)
    assert price[17] == pytest.approx(energy_only)
    assert DELIVERY.fixed_per_day is not None  # exists on the spec ...
    assert DELIVERY.baseline is not None  # ... and so does the credit ...
    assert price[17] < 1.0  # ... but neither is in the marginal price
