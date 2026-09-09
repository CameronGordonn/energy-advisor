"""TOU-DR-P: the sourced windows, and the event charge that must never be assumed away.

TOU-DR-P is SDG&E's residential "Time of Use Plus" — TOU-DR1's periods and TOU-DR1's
delivery charges, with a flatter generation curve paid for by exposure to Reduce Your Use
(RYU) event days at an extra $1.16/kWh, 4-9 p.m., up to eighteen days a year.

Both gaps that kept this schedule unloadable (HANDOFF open decision 2) closed on
2026-09-09, and each left behind something worth pinning:

* **The windows were a research gap.** They came off TOU-DR-P's own two sheets — Schedule
  TOU-DR Sheet 5 (Cal. P.U.C. Sheet 29300-E) for the UDC, Schedule EECC-TOU-DR-P Sheet 2
  (Sheet 29436-E) for the commodity — which agree with each other and turn out to equal
  TOU-DR1's. That equality is a *finding*, not an assumption, so it is asserted across all
  576 hour-cells rather than spot-checked: a future TOU-DR1 edit that drags TOU-DR-P along,
  or leaves it behind, has to be deliberate.

* **The event adder was a modeling gap**, and the resolution is the interesting half. The
  engine now bills it, and `event_days` is a REQUIRED argument that raises when omitted —
  the same treatment `territory` and the PCIA `vintage` get. The load-bearing test here is
  `test_billing_without_event_days_raises`. Zero events is simultaneously the most likely
  single-year outcome (SDG&E called none in 2021, 2022, 2023, 2025 or 2026-to-date) and the
  assumption that makes the schedule look free, so a default would be both usually right
  and systematically flattering — the exact failure mode invariant 2 exists to catch.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
import yaml

from greenbutton.models import COL_ESTIMATED, COL_KWH, LOCAL_TZ, IntervalSeries, MeterMeta, Utility
from tariffs.bill import MissingEventDaysError, compute_bill, compute_layer
from tariffs.loader import SPECS_DIR, load_spec_file
from tariffs.schema import Layer, Season, Service, TouDef

DR_P_DELIVERY = SPECS_DIR / "sdge_tou_dr_p_delivery_2026-06-01.yaml"
DR_P_GENERATION = SPECS_DIR / "sdge_tou_dr_p_generation_2026-06-01.yaml"
DR_1_DELIVERY = SPECS_DIR / "sdge_tou_dr1_delivery_2026-06-01.yaml"
DR_1_GENERATION = SPECS_DIR / "sdge_tou_dr1_generation_2026-06-01.yaml"


def _raw(path):
    return yaml.safe_load(path.read_text())


def _series(start: str, n_days: int, kwh_per_hour: float = 1.0) -> IntervalSeries:
    idx = pd.date_range(start, periods=n_days * 24, freq="h", tz=LOCAL_TZ)
    frame = pd.DataFrame({COL_KWH: kwh_per_hour, COL_ESTIMATED: False}, index=idx)
    return IntervalSeries(
        utility=Utility.SDGE,
        interval=pd.Timedelta(hours=1).to_pytimedelta(),
        meta=MeterMeta(utility=Utility.SDGE),
        frame=frame,
    )


def _specs():
    return [load_spec_file(DR_P_DELIVERY), load_spec_file(DR_P_GENERATION)]


# SDG&E publishes baseline allowances per climate zone, so `territory` is required too;
# supplied here so the exceptions under test are the event-day ones and not that.
ZONE = "coastal_basic"

# TOU-DR-P is BUNDLED-ONLY by tariff — Schedule EECC-TOU-DR-P is closed to Direct Access
# and CCA customers — so every comparison in this file is a bundled one. It also keeps the
# TOU-DR1 side honest: billed as a CCA it would carry a vintaged PCIA that a TOU-DR-P
# customer can never pay, which would flatter TOU-DR-P by several cents a kWh.
BUNDLED = Service.BUNDLED


# --- the gate: no dollar figure without an explicit event assumption -----------------------


def test_billing_without_event_days_raises():
    """THE load-bearing test. TOU-DR-P became loadable on 2026-09-09; the point of the
    events model is that becoming loadable did not make it silently priceable. Omitting the
    event days is not "assume none", it is an error — because the schedule's whole risk
    lives in a number the tariff cannot supply."""
    with pytest.raises(MissingEventDaysError) as exc:
        compute_bill(
            _series("2026-09-01", 30),
            _specs(),
            date(2026, 9, 1),
            date(2026, 9, 30),
            territory=ZONE,
            service=BUNDLED,
        )
    msg = str(exc.value)
    assert "event_days" in msg
    assert "RYU Event Period Adder" in msg


def test_the_zero_event_case_must_be_asked_for_explicitly():
    """The optimistic case is available, but only on the record. `[]` prices it and emits
    the RYU line at 0.00 rather than omitting it, so a reader of the bill can see that the
    charge exists and was assumed not to fire."""
    bill = compute_bill(
        _series("2026-09-01", 30),
        _specs(),
        date(2026, 9, 1),
        date(2026, 9, 30),
        territory=ZONE,
        service=BUNDLED,
        event_days=[],
    )
    gen = next(layer for layer in bill.layers if layer.layer is Layer.GENERATION)
    assert gen.bucket()["RYU Event Period Adder"] == 0.0


def test_supplying_more_events_than_the_tariff_allows_raises():
    """18 is a tariff cap (Schedule EECC-TOU-DR-P SC 14), not a modeling convention. A
    19-event stress case is not conservative, it is impossible, and a range built on one
    would overstate the downside — which is its own kind of dishonesty."""
    too_many = [date(2026, 9, 1) + pd.Timedelta(days=i).to_pytimedelta() for i in range(19)]
    with pytest.raises(ValueError, match="caps"):
        compute_bill(
            _series("2026-09-01", 30),
            _specs(),
            date(2026, 9, 1),
            date(2026, 9, 30),
            territory=ZONE,
            service=BUNDLED,
            event_days=too_many,
        )


# --- what the adder actually costs ---------------------------------------------------------


def test_the_adder_bills_only_the_event_hours_of_the_event_days():
    """1 kWh/hour flat, three event days, a 5-hour window: 15 kWh at $1.16. Anything that
    leaked into neighbouring hours or ordinary days would show up here as a multiple of
    1.16 that is not 17.40."""
    bill = compute_bill(
        _series("2026-09-01", 30),
        _specs(),
        date(2026, 9, 1),
        date(2026, 9, 30),
        territory=ZONE,
        service=BUNDLED,
        event_days=[date(2026, 9, 5), date(2026, 9, 6), date(2026, 9, 9)],
    )
    gen = next(layer for layer in bill.layers if layer.layer is Layer.GENERATION)
    assert gen.bucket()["RYU Event Period Adder"] == pytest.approx(3 * 5 * 1.16)


def test_care_customers_pay_the_printed_care_adder_not_the_standard_one():
    """SDG&E prints the RYU row's own Total Adjusted CARE Rate (0.75) rather than folding
    it into the bill's CARE Discount line, and the engine bills it the same way."""
    bill = compute_bill(
        _series("2026-09-01", 30),
        _specs(),
        date(2026, 9, 1),
        date(2026, 9, 30),
        territory=ZONE,
        service=BUNDLED,
        event_days=[date(2026, 9, 5)],
        care=True,
    )
    gen = next(layer for layer in bill.layers if layer.layer is Layer.GENERATION)
    assert gen.bucket()["RYU Event Period Adder"] == pytest.approx(5 * 0.75)


def test_event_days_outside_the_billing_period_are_ignored_not_rejected():
    """A caller holds one list of the year's event days and bills twelve periods from it."""
    whole_year = [date(2026, 9, 5), date(2026, 9, 6), date(2026, 9, 9)]
    bill = compute_bill(
        _series("2026-08-01", 31),
        _specs(),
        date(2026, 8, 1),
        date(2026, 8, 31),
        territory=ZONE,
        service=BUNDLED,
        event_days=whole_year,
    )
    gen = next(layer for layer in bill.layers if layer.layer is Layer.GENERATION)
    assert gen.bucket()["RYU Event Period Adder"] == 0.0


def test_the_adder_rides_on_generation_not_delivery():
    """A tariff fact, not a filing convenience: the Total Rates Table prints the RYU Adder
    in the Schedule EECC-TOU-DR-P column and SC 15 defines it there. It matters because
    EECC-TOU-DR-P is closed to CCA and Direct Access customers, so the charge can never
    reach a customer who buys commodity elsewhere."""
    assert load_spec_file(DR_P_DELIVERY).event_adder is None
    assert load_spec_file(DR_P_GENERATION).event_adder is not None


def test_delivery_alone_can_still_be_billed_without_event_days():
    """The requirement attaches to the layer that carries the adder, not to the schedule
    name, so a delivery-only computation (the NBT import floor, for instance) is unaffected."""
    layer = compute_layer(
        _series("2026-09-01", 30),
        load_spec_file(DR_P_DELIVERY),
        date(2026, 9, 1),
        date(2026, 9, 30),
        territory=ZONE,
        service=BUNDLED,
    )
    assert layer.total > 0


# --- (b), the reporting half: the band is wide enough that a point estimate lies -----------


def test_the_event_count_decides_the_recommendation_not_the_rates():
    """Invariant 3, made concrete, and the reason (b) is not optional. Billing the SAME load
    on TOU-DR-P and on TOU-DR1 over one summer:

      * at ZERO events TOU-DR-P wins, and the win is small;
      * at the tariff's own 18-event cap it loses by an order of magnitude more than it won.

    So the event assumption, not the rate table, decides the answer — which is exactly why
    a point estimate for this schedule is a lie whichever number you pick. Any ranking that
    includes TOU-DR-P has to show both ends.

    This pins the *shape* of the reporting requirement rather than wiring it into a ranking:
    there is no SDG&E candidate set yet, and choosing WHICH days a forecast should assume is
    a further modeling decision that has not been made (see HANDOFF open decision 2).
    """
    load = _series("2026-06-01", 60)
    start, end = date(2026, 6, 1), date(2026, 7, 30)
    dr_1 = compute_bill(
        load,
        [load_spec_file(DR_1_DELIVERY), load_spec_file(DR_1_GENERATION)],
        start,
        end,
        territory=ZONE,
        service=BUNDLED,
    ).total
    args = (load, _specs(), start, end)
    no_events = compute_bill(*args, territory=ZONE, service=BUNDLED, event_days=[]).total
    cap = [start + pd.Timedelta(days=i).to_pytimedelta() for i in range(18)]
    at_cap = compute_bill(*args, territory=ZONE, service=BUNDLED, event_days=cap).total

    assert no_events < dr_1, "TOU-DR-P should win the zero-event case on this load"
    assert at_cap > dr_1, "18 events should flip the verdict"
    won = dr_1 - no_events
    lost = at_cap - dr_1
    assert lost > 10 * won, (won, lost)
    assert at_cap - no_events == pytest.approx(18 * 5 * 1.16, abs=0.02)


def test_the_event_adder_dwarfs_the_everyday_saving():
    """The honest-broker number, load-independent and therefore assertable without a
    household. At 6/1/2026 rates a summer event hour costs 1.00928/kWh more than the
    TOU-DR1 hour it replaces, while an ordinary summer on-peak hour saves 0.15072/kWh — so
    one event day cancels ~6.7 ordinary summer days of on-peak benefit at equal load. Any
    treatment of TOU-DR-P that reports a saving without an event assumption is reporting
    the numerator only."""
    dr_p = load_spec_file(DR_P_GENERATION).energy_rate(Season.SUMMER, "on_peak").standard
    dr_1 = load_spec_file(DR_1_GENERATION).energy_rate(Season.SUMMER, "on_peak").standard
    everyday_saving = dr_1 - dr_p
    event_penalty = (dr_p + 1.16) - dr_1
    assert everyday_saving == pytest.approx(0.15072)
    assert event_penalty == pytest.approx(1.00928)
    assert event_penalty / everyday_saving == pytest.approx(6.7, abs=0.05)


def test_tou_dr_p_is_cheaper_than_tou_dr1_in_every_winter_period():
    """Why option (c) — dropping the schedule from rankings — was rejected. For the seven
    winter months TOU-DR-P beats TOU-DR1 in all three periods, so excluding it would hide a
    real saving rather than merely omit a risky one. The risk and the saving both have to
    be shown."""
    dr_p, dr_1 = load_spec_file(DR_P_GENERATION), load_spec_file(DR_1_GENERATION)
    for period in ("on_peak", "off_peak", "super_off_peak"):
        assert (
            dr_p.energy_rate(Season.WINTER, period).standard
            < dr_1.energy_rate(Season.WINTER, period).standard
        ), period


def test_tou_dr_p_flattens_the_summer_curve_rather_than_lowering_it():
    """The counterintuitive half, and the reason TOU-DR-P is a poor rate for a battery: its
    summer on/super-off spread is 0.11601 against TOU-DR1's 0.30799, a 62% cut in the price
    signal a dispatch model has to arbitrage against. It is *dearer* off-peak and
    super-off-peak; only on-peak is cheaper."""
    dr_p, dr_1 = load_spec_file(DR_P_GENERATION), load_spec_file(DR_1_GENERATION)
    spread = lambda s: (  # noqa: E731
        s.energy_rate(Season.SUMMER, "on_peak").standard
        - s.energy_rate(Season.SUMMER, "super_off_peak").standard
    )
    assert spread(dr_p) == pytest.approx(0.11601)
    assert spread(dr_1) == pytest.approx(0.30799)
    for period in ("off_peak", "super_off_peak"):
        assert (
            dr_p.energy_rate(Season.SUMMER, period).standard
            > dr_1.energy_rate(Season.SUMMER, period).standard
        ), period


# --- the layer split must rebuild SDG&E's own printed totals ------------------------------

PRINTED_TOTAL = {
    (Season.SUMMER, "on_peak"): 0.53387,
    (Season.SUMMER, "off_peak"): 0.49062,
    (Season.SUMMER, "super_off_peak"): 0.41786,
    (Season.WINTER, "on_peak"): 0.58596,
    (Season.WINTER, "off_peak"): 0.51145,
    (Season.WINTER, "super_off_peak"): 0.42868,
}
PRINTED_CARE_TOTAL = {
    (Season.SUMMER, "on_peak"): 0.33756,
    (Season.SUMMER, "off_peak"): 0.30945,
    (Season.SUMMER, "super_off_peak"): 0.26215,
    (Season.WINTER, "on_peak"): 0.37142,
    (Season.WINTER, "off_peak"): 0.32298,
    (Season.WINTER, "super_off_peak"): 0.26919,
}


@pytest.mark.parametrize("cell", sorted(PRINTED_TOTAL, key=str))
def test_the_two_layers_resum_to_the_printed_total_electric_rate(cell):
    """The same gate every other SDG&E schedule passes: transcribing delivery and
    generation separately is only safe if their sum reproduces SDG&E's own printed total."""
    season, period = cell
    delivery = load_spec_file(DR_P_DELIVERY).energy_rate(season, period).standard
    generation = load_spec_file(DR_P_GENERATION).energy_rate(season, period).standard
    assert delivery + generation == pytest.approx(PRINTED_TOTAL[cell], abs=1e-9)


@pytest.mark.parametrize("cell", sorted(PRINTED_CARE_TOTAL, key=str))
def test_the_two_layers_resum_to_the_printed_care_total(cell):
    """The CARE split is the part most easily got wrong: delivery keeps the 0.00864 CARE
    surcharge exemption and both layers take the 35%. Tolerance is the sheet's own 5-dp
    rounding, not slack."""
    season, period = cell
    delivery = load_spec_file(DR_P_DELIVERY).energy_rate(season, period).care
    generation = load_spec_file(DR_P_GENERATION).energy_rate(season, period).care
    assert delivery + generation == pytest.approx(PRINTED_CARE_TOTAL[cell], abs=1e-5)


# --- the windows, and the fact that they equal TOU-DR1's ----------------------------------


def _tou(path) -> TouDef:
    return TouDef.model_validate(_raw(path)["tou"])


@pytest.mark.parametrize("weekday", [True, False])
@pytest.mark.parametrize("month", range(1, 13))
@pytest.mark.parametrize("hour", range(24))
def test_tou_dr_p_classifies_every_hour_exactly_as_tou_dr1_does(hour, month, weekday):
    """576 cells, not a spot check. The two schedules are sourced independently and happen
    to agree; if a later vintage of either diverges, this fails on the specific hour."""
    expected = _tou(DR_1_DELIVERY).period_for(hour, month, weekday)
    for path in (DR_P_DELIVERY, DR_P_GENERATION):
        assert _tou(path).period_for(hour, month, weekday) == expected, path.name


@pytest.mark.parametrize("month", range(1, 13))
def test_the_weekday_daytime_super_off_peak_window_is_year_round(month):
    """The 2026-05-01 change, carried onto this 6/1 vintage. Both TOU-DR-P sheets still
    print the March-and-April restriction — the tariff book was never revised — so this is
    the one place the spec deliberately departs from the filed text, on the strength of
    sdge.com/super-off-peak-residential naming TOU-DR-P among the affected plans (HANDOFF
    open decision 1). A TOU-DR-P vintage before 5/1/2026 must restore `months: [3, 4]`."""
    for hour in (10, 11, 12, 13):
        assert _tou(DR_P_DELIVERY).period_for(hour, month, weekday=True) == "super_off_peak"


def test_the_weekend_table_differs_from_the_weekday_one():
    """Guards against a rules list that collapses to day-type-insensitive. Weekend
    10 a.m.-2 p.m. is super-off-peak in both tables, but 6-10 a.m. splits them."""
    tou = _tou(DR_P_DELIVERY)
    assert tou.day_type_sensitive
    assert tou.period_for(7, 7, weekday=True) == "off_peak"
    assert tou.period_for(7, 7, weekday=False) == "super_off_peak"


# --- the delivery layer is TOU-DR1's, because both bill Schedule TOU-DR --------------------


def test_delivery_energy_rates_are_identical_to_tou_dr1():
    """TOU-DR-P's own rate table, note 1: "the UDC rates associated with service under
    Schedule TOU-DR". So the entire difference between the two schedules lives in the
    generation layer — which is why the ranking question reduces to EECC vs EECC-TOU-DR-P
    plus event risk, and nothing else."""
    assert _raw(DR_P_DELIVERY)["energy"] == _raw(DR_1_DELIVERY)["energy"]
    assert _raw(DR_P_DELIVERY)["fixed_per_day"] == _raw(DR_1_DELIVERY)["fixed_per_day"]
    assert (
        _raw(DR_P_DELIVERY)["baseline"]["credit_per_kwh"]
        == _raw(DR_1_DELIVERY)["baseline"]["credit_per_kwh"]
    )


def test_delivery_is_period_flat_like_tou_dr1():
    """Restated on this schedule rather than inherited: 100% of TOU-DR-P's price signal is
    in generation, so a delivery-only comparison against TOU-DR1 finds nothing and a tool
    that stops there reports a $0 difference on a schedule that can swing by 15 c/kWh."""
    rates = _raw(DR_P_DELIVERY)["energy"]
    assert len({r["standard"] for r in rates.values()}) == 1
    assert len({r["care"] for r in rates.values()}) == 1


# --- the RYU facts, pinned so the stale tariff book cannot win an argument -----------------


def test_ryu_adder_facts_match_the_sourced_tariff():
    """$1.16/kWh and the 18-event cap are Schedule EECC-TOU-DR-P SC 15 and SC 14; the 0.75
    CARE rate is printed on the 6/1/2026 TOU-DR-P-CARE table."""
    adder = load_spec_file(DR_P_GENERATION).event_adder
    assert (adder.per_kwh.standard, adder.per_kwh.care) == (1.16, 0.75)
    assert adder.max_events_per_year == 18


def test_ryu_event_hours_are_the_current_ones_not_the_tariff_books():
    """⚠ The filed sheets print 2:00 p.m. - 6:00 p.m., frozen at Advice 3130-E (2017). The
    window moved to 4-9 p.m. on 2022-06-01; SDG&E's residential pricing-plans page says so,
    and every TOU-DR-P event row in SDG&E's monthly CPUC demand-response filings records
    4:00pm-9:00pm. This test exists so that "correcting" the spec against the tariff book
    fails loudly rather than shifting a $1.16/kWh charge onto the wrong five hours."""
    adder = load_spec_file(DR_P_GENERATION).event_adder
    assert adder.hours == [(16, 21)]
    assert not adder.covers(14) and not adder.covers(15)
    assert all(adder.covers(h) for h in range(16, 21))
