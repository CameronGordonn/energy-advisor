"""The SDG&E delivery + generation layers must re-sum to SDG&E's own printed totals.

This is the tariff-exactness gate for SDG&E, and it is the same kind of artifact as the
golden-bill tests: the numbers on the right-hand side are transcribed from SDG&E's
published rate tables, and the engine's layer decomposition has to reproduce them. If a
future rate update touches one layer and not the other, this fails loudly instead of
quietly mispricing every SDG&E bill.

Sources (both retrieved 2026-09-07):
  "6-1-26 Schedule TOU-DR1 Total Rates Table.pdf"      -> Total Electric Rate column
  "6-1-26 Schedule TOU-DR1-CARE Total Rates Table.pdf" -> Total Adjusted CARE Rate column
"""

from __future__ import annotations

import pytest

from tariffs.loader import SPECS_DIR, load_spec_file
from tariffs.schema import Layer, Season

DELIVERY = SPECS_DIR / "sdge_tou_dr1_delivery_2026-06-01.yaml"
GENERATION = SPECS_DIR / "sdge_tou_dr1_generation_2026-06-01.yaml"

# season, period -> (printed Total Electric Rate, printed Total Adjusted CARE Rate)
PRINTED = {
    ("summer", "on_peak"): (0.68459, 0.43553),
    ("summer", "off_peak"): (0.46392, 0.29209),
    ("summer", "super_off_peak"): (0.37660, 0.23533),
    ("winter", "on_peak"): (0.61014, 0.38713),
    ("winter", "off_peak"): (0.52843, 0.33402),
    ("winter", "super_off_peak"): (0.43767, 0.27503),
}


@pytest.fixture(scope="module")
def layers():
    return load_spec_file(DELIVERY), load_spec_file(GENERATION)


def test_the_two_layers_are_the_two_halves_of_one_schedule(layers):
    delivery, generation = layers
    assert delivery.layer is Layer.DELIVERY
    assert generation.layer is Layer.GENERATION
    assert delivery.schedule_id == generation.schedule_id == "TOU-DR1"
    assert delivery.provider == generation.provider == "SDG&E"
    assert delivery.effective_date == generation.effective_date


def test_layers_classify_every_hour_identically(layers):
    """Two layers pricing the same kWh into different TOU buckets would be silent nonsense."""
    delivery, generation = layers
    assert delivery.seasons == generation.seasons
    assert delivery.tou == generation.tou
    for month in range(1, 13):
        for hour in range(24):
            for weekday in (True, False):
                assert delivery.tou.period_for(hour, month, weekday) == generation.tou.period_for(
                    hour, month, weekday
                )


@pytest.mark.parametrize(("season", "period"), sorted(PRINTED))
def test_standard_layers_sum_to_the_printed_total_electric_rate(layers, season, period):
    delivery, generation = layers
    s = Season(season)
    total = delivery.energy_rate(s, period).for_customer(care=False) + generation.energy_rate(
        s, period
    ).for_customer(care=False)
    assert total == pytest.approx(PRINTED[(season, period)][0], abs=1e-5)


@pytest.mark.parametrize(("season", "period"), sorted(PRINTED))
def test_care_layers_sum_to_the_printed_total_adjusted_care_rate(layers, season, period):
    """The CARE split (delivery keeps the 0.00864 exemption, both layers take the 35%) is
    not a convention we chose — it is the only split that rebuilds SDG&E's printed CARE
    total, and this asserts it does, exactly."""
    delivery, generation = layers
    s = Season(season)
    total = delivery.energy_rate(s, period).for_customer(care=True) + generation.energy_rate(
        s, period
    ).for_customer(care=True)
    assert total == pytest.approx(PRINTED[(season, period)][1], abs=1e-5)


def test_generation_carries_the_entire_tou_price_signal(layers):
    """On TOU-DR1 the UDC total is period-flat; every cent of TOU spread is EECC.

    Worth pinning: it is why the delivery/generation split is load-bearing on SDG&E rather
    than cosmetic, and any load-shift or battery conclusion rests on it.
    """
    delivery, generation = layers
    for season in (Season.SUMMER, Season.WINTER):
        d = {
            p: delivery.energy_rate(season, p).for_customer(care=False)
            for p in delivery.tou.periods
        }
        assert len(set(d.values())) == 1, f"delivery is not period-flat in {season}: {d}"
    summer = {
        p: generation.energy_rate(Season.SUMMER, p).for_customer(care=False)
        for p in generation.tou.periods
    }
    assert summer["on_peak"] - summer["super_off_peak"] == pytest.approx(0.30799, abs=1e-5)


def test_super_off_peak_is_year_round_on_weekdays_not_march_april_only(layers):
    """HANDOFF open decision 1, resolved: SDG&E extended weekday 10:00-14:00 super-off-peak
    to year-round effective 2026-05-01, so this 2026-06-01 vintage must apply it in every
    month. A regression here would silently reprice ten months of the year."""
    for spec in layers:
        for month in range(1, 13):
            assert spec.tou.period_for(11, month, weekday=True) == "super_off_peak"
            # ... while the overnight and weekend windows are unchanged by that filing.
            assert spec.tou.period_for(3, month, weekday=True) == "super_off_peak"
            assert spec.tou.period_for(11, month, weekday=False) == "super_off_peak"
            assert spec.tou.period_for(17, month, weekday=True) == "on_peak"
            assert spec.tou.period_for(15, month, weekday=True) == "off_peak"


# --- Non-bypassable charges: the NEM import floor on every SDG&E schedule ---------------

SDGE_DELIVERY = [
    "sdge_tou_dr1_delivery_2026-06-01.yaml",
    "sdge_tou_dr2_delivery_2026-06-01.yaml",
    "sdge_ev_tou_5_delivery_2026-06-01.yaml",
]


@pytest.mark.parametrize("filename", SDGE_DELIVERY)
def test_every_sdge_delivery_spec_can_be_settled_under_nbt(filename):
    """No SDG&E schedule may reach the NEM engine without a declared import floor.

    A missing `non_bypassable` block is not a harmless omission: it would silently let
    export credits offset charges that Schedule NBT SC 2.f says they can never offset,
    overstating solar/battery value. Differentiation invariant 4.
    """
    spec = load_spec_file(SPECS_DIR / filename)
    nbc = spec.non_bypassable
    assert nbc is not None, f"{filename} has no non_bypassable block"
    assert nbc.included_in_energy_rate, "SDG&E folds NBCs into the published energy rate"
    assert nbc.per_kwh(care=False) == pytest.approx(0.02099, abs=1e-9)
    assert nbc.per_kwh(care=True) == pytest.approx(0.00980, abs=1e-9)


@pytest.mark.parametrize("filename", SDGE_DELIVERY)
def test_the_import_floor_never_exceeds_the_delivery_charge_it_is_carved_from(filename):
    """`included_in_energy_rate` means netting subtracts the NBC from the offsettable
    energy subtotal. If an NBC total ever exceeded its own layer's energy rate that
    subtraction would go negative — a sign the two were read off different vintages."""
    spec = load_spec_file(SPECS_DIR / filename)
    for care in (False, True):
        floor = spec.non_bypassable.per_kwh(care=care)
        for season in (Season.SUMMER, Season.WINTER):
            for period in spec.tou.periods:
                rate = spec.energy_rate(season, period).for_customer(care=care)
                assert floor <= rate, f"{filename} {season}/{period} care={care}: {floor} > {rate}"


def test_ev_tou_5_super_off_peak_is_about_half_non_bypassable():
    """The finding the EV-TOU-5 spec header claims, pinned so it cannot rot.

    EV-TOU-5 collapses its super-off-peak distribution charge but not its NBCs, so a NEM
    analysis netting exports against the headline delivery rate overstates the value of
    shifting imports into that window by roughly 2x.
    """
    spec = load_spec_file(SPECS_DIR / "sdge_ev_tou_5_delivery_2026-06-01.yaml")
    floor = spec.non_bypassable.per_kwh(care=False)
    sop = spec.energy_rate(Season.SUMMER, "super_off_peak").for_customer(care=False)
    on = spec.energy_rate(Season.SUMMER, "on_peak").for_customer(care=False)
    assert floor / sop == pytest.approx(0.446, abs=0.005)
    assert floor / on == pytest.approx(0.065, abs=0.005)
