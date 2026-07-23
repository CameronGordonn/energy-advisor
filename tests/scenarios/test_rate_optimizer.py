"""M2 optimizer: the tiered-rate identity, load reshaping, and assumption invariance."""

from __future__ import annotations

import glob
from datetime import date

import pytest

from scenarios.rate_optimizer import (
    ALL_PGE_CANDIDATES,
    EVENING_HOURS,
    PGE_3CE_CANDIDATES,
    UutPolicy,
    _uut_adjustment,
    explain,
    max_shift_factor,
    rank,
    scale_hours,
    shift_hours,
    simulate,
)
from tariffs.bill import compute_layer
from tariffs.loader import load_specs
from tariffs.schema import Layer

from ..tariffs.test_bill import make_series

AS_OF = date(2026, 7, 1)


# --- E-1: the tiered-rate identity the spec is built on --------------------


def test_e1_baseline_credit_reproduces_explicit_tier_arithmetic():
    """E-1 modeled as (over-baseline rate + tier differential on the baseline block)
    must equal the textbook two-tier calculation, exactly.

    This is the load-bearing claim in pge_e1_delivery_*.yaml: the engine has no `tiers`
    concept and does not need one, because
        tier1 x min(u,B) + tier2 x max(0,u-B) == tier2 x u + (tier1-tier2) x min(u,B).
    If this ever fails, E-1 is being flattened rather than modeled and the spec's decision
    note is wrong.
    """
    spec = load_specs("E-1", Layer.DELIVERY, on=AS_OF)
    tier2 = spec.energy_rate(spec.seasons.season_for(6), "all").standard
    credit = spec.baseline.credit_per_kwh.standard
    tier1 = tier2 + credit
    assert tier1 == pytest.approx(0.32561, abs=1e-9)  # printed Tier 1 Usage rate
    assert tier2 == pytest.approx(0.40702, abs=1e-9)  # printed Tier 2 Usage rate

    days = 20
    # June 2026: summer, and after this spec's 2026-06-01 effective date. 480 kWh against a
    # 142 kWh allowance, so both tiers are genuinely exercised.
    series = make_series("2026-06-01", days, kwh_per_hour=1.0)
    ps, pe = date(2026, 6, 1), date(2026, 6, 20)
    lb = compute_layer(series, spec, ps, pe)
    b = lb.bucket()

    usage = 24.0 * days
    allowance = days * spec.baseline.allowance_kwh_per_day_summer
    assert 0 < allowance < usage, "test must straddle the tier boundary"
    explicit = tier1 * min(usage, allowance) + tier2 * max(0.0, usage - allowance)
    modeled = b["Energy Total Usage"] + b["Baseline Credit"]
    assert modeled == pytest.approx(explicit, abs=0.005)


def test_e1_is_billed_as_one_period_not_flattened_tou():
    spec = load_specs("E-1", Layer.DELIVERY, on=AS_OF)
    assert spec.tou.periods == ["all"]
    assert spec.tou.label("all") == "Total Usage"


# --- E-TOU-D: the holiday rule actually moves money ------------------------


def test_etou_d_prices_a_holiday_off_peak():
    """2026-07-03 is the observed Independence Day; 2026-07-02 is an ordinary Thursday.

    Same usage, same weekday-shaped day — the holiday one must have zero peak kWh.
    """
    spec = load_specs("E-TOU-D", Layer.DELIVERY, on=AS_OF)
    normal = compute_layer(
        make_series("2026-07-02", 1), spec, date(2026, 7, 2), date(2026, 7, 2)
    ).bucket()
    holiday = compute_layer(
        make_series("2026-07-03", 1), spec, date(2026, 7, 3), date(2026, 7, 3)
    ).bucket()
    assert normal["Energy Peak"] > 0
    assert holiday["Energy Peak"] == 0.0
    assert holiday["Energy Off Peak"] > normal["Energy Off Peak"]


def test_etou_d_peak_is_weekday_only():
    spec = load_specs("E-TOU-D", Layer.DELIVERY, on=AS_OF)
    sat = compute_layer(
        make_series("2026-07-11", 1), spec, date(2026, 7, 11), date(2026, 7, 11)
    ).bucket()
    assert sat["Energy Peak"] == 0.0  # 2026-07-11 is a Saturday


# --- load reshaping --------------------------------------------------------


def test_scale_hours_changes_total_load():
    s = make_series("2026-01-01", 7)
    doubled = scale_hours(s, EVENING_HOURS, 2.0)
    assert doubled.total_kwh > s.total_kwh
    assert doubled.total_kwh == pytest.approx(s.total_kwh + 7 * len(EVENING_HOURS))


def test_shift_hours_preserves_total_load():
    s = make_series("2026-01-01", 7)
    shifted = shift_hours(s, EVENING_HOURS, 2.0)
    assert shifted.total_kwh == pytest.approx(s.total_kwh)
    mask = shifted.frame.index.hour.isin(list(EVENING_HOURS))
    assert shifted.frame.loc[mask, "kwh"].sum() == pytest.approx(2 * s.frame.loc[mask, "kwh"].sum())


def test_max_shift_factor_is_the_point_where_other_hours_hit_zero():
    s = make_series("2026-01-01", 7)  # flat 1 kWh/h: 5 evening hours, 19 others
    assert max_shift_factor(s, EVENING_HOURS) == pytest.approx(1 + 19 / 5)
    with pytest.raises(ValueError, match="negative"):
        shift_hours(s, EVENING_HOURS, 6.0)


# --- the UUT assumption ----------------------------------------------------


def test_per_day_uut_policy_is_schedule_independent():
    """The adopted assumption must not be able to reorder the ranking.

    A per-day credit depends only on the billing calendar, so it contributes an identical
    constant to every candidate — which is exactly why it is safe to adopt despite the
    mechanism being UNVERIFIED.
    """
    a = _uut_adjustment(UutPolicy.PER_DAY, days=30, gross_uut=12.0)
    b = _uut_adjustment(UutPolicy.PER_DAY, days=30, gross_uut=99.0)
    assert a == b
    assert _uut_adjustment(UutPolicy.NONE, days=30, gross_uut=12.0) == 0.0
    assert _uut_adjustment(UutPolicy.PROPORTIONAL, days=30, gross_uut=12.0) < 0


# --- end-to-end on synthetic load (no customer data needed) ----------------


def _periods() -> list[tuple[date, date]]:
    return [(date(2026, 4, 1), date(2026, 4, 30)), (date(2026, 6, 1), date(2026, 6, 30))]


def test_every_candidate_bills_end_to_end_and_ranks():
    series = make_series("2026-04-01", 91)  # April through June
    plans = rank(series, _periods(), care=True, as_of=AS_OF)
    assert len(plans) == len(ALL_PGE_CANDIDATES)  # 3CE and PG&E-bundled halves
    assert all(p.total > 0 for p in plans)
    assert plans == sorted(plans, key=lambda p: p.total)
    # EV2-A must stay flagged so a report can never recommend it unconditionally.
    assert all(p.eligibility for p in plans if p.delivery == "EV2-A")


def test_ev_only_plans_are_excluded_unless_the_household_has_an_ev():
    """Eligibility is filtered, not merely flagged — an ineligible plan must never rank."""
    from scenarios.rate_optimizer import eligible_candidates

    without = eligible_candidates(ALL_PGE_CANDIDATES, has_ev=False)
    with_ev = eligible_candidates(ALL_PGE_CANDIDATES, has_ev=True)
    assert all(c.delivery != "EV2-A" for c in without)
    assert any(c.delivery == "EV2-A" for c in with_ev)
    assert len(with_ev) == len(ALL_PGE_CANDIDATES)


def test_explain_diff_sums_to_the_total_gap():
    series = make_series("2026-04-01", 91)
    plans = rank(series, _periods(), care=True, as_of=AS_OF)
    a, b = plans[0], plans[-1]
    total_gap = round(b.total - a.total, 2)
    all_keys = set(a.components) | set(b.components)
    full = sum(b.components.get(k, 0.0) - a.components.get(k, 0.0) for k in all_keys)
    assert full == pytest.approx(total_gap, abs=0.05)
    assert explain(a, b), "a non-trivial gap must decompose into at least one component"


def test_ranking_is_invariant_to_the_uut_assumption_on_this_load():
    series = make_series("2026-04-01", 91)
    orders = {
        policy: tuple(
            p.name for p in rank(series, _periods(), care=True, as_of=AS_OF, policy=policy)
        )
        for policy in UutPolicy
    }
    assert len(set(orders.values())) == 1, orders


@pytest.mark.skipif(
    not glob.glob("data/pge_electric_usage_interval_data*.csv"),
    reason="real PG&E export not present",
)
def test_real_household_ranking_is_stable_across_uut_policies():
    from greenbutton import parse_pge_interval_csv

    series, _ = parse_pge_interval_csv(glob.glob("data/pge_electric_usage_interval_data*.csv")[0])
    periods = [(date(2025, 8, 2), date(2025, 8, 25)), (date(2026, 4, 28), date(2026, 5, 27))]
    orders = {
        policy: tuple(p.name for p in rank(series, periods, care=True, as_of=AS_OF, policy=policy))
        for policy in UutPolicy
    }
    assert len(set(orders.values())) == 1, orders


def test_simulate_reports_period_level_detail():
    series = make_series("2026-04-01", 91)
    plan = simulate(series, PGE_3CE_CANDIDATES[0], _periods(), care=True, as_of=AS_OF)
    assert len(plan.periods) == 2
    assert plan.periods[0].days == 30
    assert plan.periods[0].kwh == pytest.approx(30 * 24)
    assert plan.total == pytest.approx(sum(p.total for p in plan.periods), abs=0.01)
