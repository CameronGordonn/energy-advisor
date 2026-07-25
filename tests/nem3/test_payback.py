"""Payback ranking, vintage timing, and the Monte Carlo distribution."""

from __future__ import annotations

from datetime import date

import pytest

from greenbutton.models import Utility
from nem3.acc import ExportRateSchedule, Vintage
from nem3.netting import NbtSettings
from nem3.payback import InstallCosts, compare_vintage_timing, evaluate
from tariffs.loader import load_spec_versions
from tariffs.schema import Layer, Service
from uncertainty.montecarlo import Drivers, simulate_payback


@pytest.fixture
def pieces(load_series, production, monthly_periods):
    delivery = load_spec_versions("TOU-DR1", Layer.DELIVERY)
    schedule = ExportRateSchedule(
        "SDG&E", Vintage(application_year=2026, pto_date=date(2026, 4, 1))
    )
    settings = NbtSettings(
        service=Service.BUNDLED, territory="coastal_basic", acc_plus_eligible=False
    )
    return delivery, schedule, settings, monthly_periods


def test_scenarios_ranked_and_battery_band_ordered(load_series, production, pieces):
    delivery, schedule, settings, periods = pieces
    idx = load_series.frame.index
    import numpy as np

    imp_price = np.where(idx.hour.values >= 16, 0.6, 0.3)
    exp_price = (schedule.rates(idx)["delivery"] + schedule.rates(idx)["generation"]).to_numpy()
    scenarios = evaluate(
        load_series,
        production,
        delivery,
        delivery,
        schedule,
        periods,
        settings=settings,
        utility=Utility.SDGE,
        system_kw=4.0,
        import_price=imp_price,
        export_price=exp_price,
        costs=InstallCosts(),
    )
    names = [s.name for s in scenarios]
    assert names[0] == "Solar only"
    greedy = next(s for s in scenarios if "greedy" in s.name)
    lp = next(s for s in scenarios if "LP" in s.name)
    # Both battery strategies add value over solar alone, and cost more upfront. Note the
    # LP is NOT guaranteed to settle cheaper than greedy: it optimizes a marginal-price
    # proxy, while the dollars come from the full NBT settlement whose credit caps and NBC
    # floor the LP ignores — so which of the two wins in settled dollars is itself a
    # finding, not a fixed ordering.
    assert greedy.annual_savings > scenarios[0].annual_savings
    assert lp.annual_savings > scenarios[0].annual_savings
    assert greedy.upfront_cost > scenarios[0].upfront_cost


def test_payback_none_when_savings_nonpositive():
    from nem3.netting import NbtYear
    from nem3.payback import _scenario

    empty = NbtYear(
        periods=[], vintage_application_year=2026, pto_date=date(2026, 4, 1), lock_in_through=None
    )
    s = _scenario("x", empty, baseline=0.0, upfront=10000.0)
    assert s.simple_payback_years is None
    assert not s.pays_back


def test_vintage_timing_identical_tables_reads_immaterial(load_series, production, pieces):
    delivery, _schedule, settings, periods = pieces
    # SDG&E's NBT2025 and NBT2026 tables are byte-identical, so timing must read immaterial.
    timing = compare_vintage_timing(
        load_series,
        production,
        delivery,
        delivery,
        periods,
        settings=settings,
        utility=Utility.SDGE,
        this_year=2025,
    )
    assert abs(timing.lock_in_delta) < 1.0
    assert "immaterial" in timing.recommendation


# --- Monte Carlo ------------------------------------------------------------------------


def test_payback_distribution_is_ordered_and_bounded():
    dist = simulate_payback(15000.0, 2000.0, horizon_years=25, seed=1)
    assert dist.payback_p10 <= dist.payback_p50 <= dist.payback_p90
    assert dist.prob_never_pays_back == 0.0  # 2000/yr escalating clears 15k in 25 yr
    assert dist.cumulative_savings_p50 > 15000.0


def test_high_cost_low_savings_can_never_pay_back():
    dist = simulate_payback(
        60000.0,
        500.0,
        horizon_years=20,
        seed=2,
        drivers=Drivers(rate_escalation_mean=0.0, rate_escalation_sd=0.005),
    )
    assert dist.prob_never_pays_back > 0.5
    # When most samples never cover the cost, the median payback is either None or at the
    # horizon edge — either way the honest output is "likely never".
    assert dist.payback_p50 is None or dist.payback_p50 >= 20


def test_rate_escalation_shortens_payback():
    slow = simulate_payback(15000.0, 1500.0, drivers=Drivers(rate_escalation_mean=0.0), seed=3)
    fast = simulate_payback(15000.0, 1500.0, drivers=Drivers(rate_escalation_mean=0.08), seed=3)
    assert fast.payback_p50 <= slow.payback_p50
