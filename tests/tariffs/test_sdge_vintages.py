"""The three earlier 2026 TOU-DR1 vintages, and the version-switching they exercise.

Session 6 committed only the 6/1/2026 vintage, which is why nothing in this repo could
price an SDG&E calendar year: `marginal_energy_price` refuses dates no spec covers rather
than extrapolating, so the M3 window had to start on 2026-06-01. These specs restore
January onward.

Two things make the transcription worth pinning rather than trusting:

1. **Two different kinds of effective date collide in 2026.** RATES changed on 1/1, 4/1
   and 6/1; the weekday 10:00-14:00 SUPER-OFF-PEAK WINDOW went year-round on 5/1, in the
   middle of the 4/1 rate vintage. Delivery and generation also move on different dates
   (generation held from 4/1 through 6/1 while delivery changed again).
2. **The layer split has to keep reconstructing SDG&E's own printed totals** on every
   vintage, standard and CARE — the same gate `test_sdge_layers.py` applies to 6/1/2026.

Sources, all retrieved 2026-09-07:
  "1-1-26 Schedule TOU-DR1 Total Rates Table.pdf" / "...TOU-DR1-CARE..."
  "4-1-26 Schedule TOU-DR1 Total Rates Table.pdf" / "...TOU-DR1-CARE..."
  (there is no 5-1-26 sheet in that series; the URL returns HTTP 404)
"""

from __future__ import annotations

from datetime import date

import pytest

from tariffs.loader import SPECS_DIR, load_spec_file, load_spec_versions, load_specs
from tariffs.schema import Layer, Season

# effective_date -> (delivery file, generation file)
VINTAGES = {
    date(2026, 1, 1): (
        "sdge_tou_dr1_delivery_2026-01-01.yaml",
        "sdge_tou_dr1_generation_2026-01-01.yaml",
    ),
    date(2026, 4, 1): (
        "sdge_tou_dr1_delivery_2026-04-01.yaml",
        "sdge_tou_dr1_generation_2026-04-01.yaml",
    ),
    date(2026, 5, 1): (
        "sdge_tou_dr1_delivery_2026-05-01.yaml",
        "sdge_tou_dr1_generation_2026-05-01.yaml",
    ),
    date(2026, 6, 1): (
        "sdge_tou_dr1_delivery_2026-06-01.yaml",
        "sdge_tou_dr1_generation_2026-06-01.yaml",
    ),
}

# (season, period) -> (Total Electric Rate, Total Adjusted CARE Rate), as printed.
# The 5/1 vintage is the 4/1 sheet's rates (no 5/1 sheet exists), so it shares that table.
PRINTED = {
    date(2026, 1, 1): {
        ("summer", "on_peak"): (0.69654, 0.44329),
        ("summer", "off_peak"): (0.47560, 0.29968),
        ("summer", "super_off_peak"): (0.38818, 0.24286),
        ("winter", "on_peak"): (0.62200, 0.39484),
        ("winter", "off_peak"): (0.54019, 0.34167),
        ("winter", "super_off_peak"): (0.44933, 0.28261),
    },
    date(2026, 4, 1): {
        ("summer", "on_peak"): (0.69572, 0.44276),
        ("summer", "off_peak"): (0.47505, 0.29933),
        ("summer", "super_off_peak"): (0.38773, 0.24257),
        ("winter", "on_peak"): (0.62127, 0.39437),
        ("winter", "off_peak"): (0.53956, 0.34126),
        ("winter", "super_off_peak"): (0.44880, 0.28226),
    },
}
PRINTED[date(2026, 5, 1)] = PRINTED[date(2026, 4, 1)]

CELLS = sorted(PRINTED[date(2026, 1, 1)])


def _layers(effective: date):
    delivery, generation = VINTAGES[effective]
    return load_spec_file(SPECS_DIR / delivery), load_spec_file(SPECS_DIR / generation)


# --- the layer identity, on every vintage ----------------------------------------------


@pytest.mark.parametrize("effective", sorted(PRINTED))
@pytest.mark.parametrize(("season", "period"), CELLS)
def test_layers_sum_to_the_printed_total_electric_rate(effective, season, period):
    delivery, generation = _layers(effective)
    s = Season(season)
    total = delivery.energy_rate(s, period).for_customer(care=False) + generation.energy_rate(
        s, period
    ).for_customer(care=False)
    assert total == pytest.approx(PRINTED[effective][(season, period)][0], abs=1e-5)


@pytest.mark.parametrize("effective", sorted(PRINTED))
@pytest.mark.parametrize(("season", "period"), CELLS)
def test_layers_sum_to_the_printed_total_adjusted_care_rate(effective, season, period):
    """The CARE split — delivery keeps the 0.00864 exemption, both layers take the 35% —
    is not a convention chosen here; it is the only split that rebuilds SDG&E's printed
    CARE total, and it has to keep doing so on every vintage, not just the one it was
    derived on."""
    delivery, generation = _layers(effective)
    s = Season(season)
    total = delivery.energy_rate(s, period).for_customer(care=True) + generation.energy_rate(
        s, period
    ).for_customer(care=True)
    assert total == pytest.approx(PRINTED[effective][(season, period)][1], abs=1e-5)


@pytest.mark.parametrize("effective", sorted(VINTAGES))
def test_the_two_layers_of_a_vintage_agree_on_structure(effective):
    """Two layers bucketing the same kWh differently would be silent nonsense."""
    delivery, generation = _layers(effective)
    assert delivery.layer is Layer.DELIVERY
    assert generation.layer is Layer.GENERATION
    assert delivery.schedule_id == generation.schedule_id == "TOU-DR1"
    assert delivery.effective_date == generation.effective_date == effective
    assert delivery.seasons == generation.seasons
    assert delivery.tou == generation.tou


@pytest.mark.parametrize("effective", sorted(VINTAGES))
def test_delivery_is_period_flat_on_every_vintage(effective):
    """TOU-DR1's UDC total is period- and season-flat on all four 2026 vintages, so 100%
    of the schedule's TOU price signal lives in generation. If a future transcription
    breaks this, every SDG&E load-shift conclusion changes."""
    delivery, _ = _layers(effective)
    for season in (Season.SUMMER, Season.WINTER):
        rates = {
            p: delivery.energy_rate(season, p).for_customer(care=False)
            for p in delivery.tou.periods
        }
        assert len(set(rates.values())) == 1, f"{effective} delivery not flat in {season}: {rates}"


# --- the window change, which has its own effective date --------------------------------


@pytest.mark.parametrize("effective", [date(2026, 1, 1), date(2026, 4, 1)])
@pytest.mark.parametrize("month", range(1, 13))
def test_pre_may_vintages_restrict_daytime_super_off_peak_to_march_and_april(effective, month):
    """The 10:00-14:00 weekday window was March/April-only until 2026-05-01. A vintage
    effective before that date must say so: applying the year-round rule to January would
    reprice four hours a day at the off-peak/super-off-peak spread."""
    expected = "super_off_peak" if month in (3, 4) else "off_peak"
    for spec in _layers(effective):
        assert spec.tou.period_for(11, month, weekday=True) == expected


@pytest.mark.parametrize("effective", [date(2026, 5, 1), date(2026, 6, 1)])
@pytest.mark.parametrize("month", range(1, 13))
def test_post_may_vintages_apply_daytime_super_off_peak_year_round(effective, month):
    for spec in _layers(effective):
        assert spec.tou.period_for(11, month, weekday=True) == "super_off_peak"


@pytest.mark.parametrize("effective", sorted(VINTAGES))
@pytest.mark.parametrize("month", range(1, 13))
def test_the_windows_the_2026_filing_did_not_touch_are_identical_everywhere(effective, month):
    """Only the weekday 10:00-14:00 carve-out moved. Overnight, evening peak and the
    weekend table are the same on all four vintages."""
    for spec in _layers(effective):
        assert spec.tou.period_for(3, month, weekday=True) == "super_off_peak"
        assert spec.tou.period_for(17, month, weekday=True) == "on_peak"
        assert spec.tou.period_for(15, month, weekday=True) == "off_peak"
        assert spec.tou.period_for(11, month, weekday=False) == "super_off_peak"
        assert spec.tou.period_for(17, month, weekday=False) == "on_peak"


# --- version switching ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("on", "expected"),
    [
        (date(2026, 1, 1), date(2026, 1, 1)),
        (date(2026, 3, 31), date(2026, 1, 1)),
        (date(2026, 4, 1), date(2026, 4, 1)),
        (date(2026, 4, 30), date(2026, 4, 1)),
        (date(2026, 5, 1), date(2026, 5, 1)),
        (date(2026, 5, 31), date(2026, 5, 1)),
        (date(2026, 6, 1), date(2026, 6, 1)),
        (date(2026, 12, 31), date(2026, 6, 1)),
    ],
)
@pytest.mark.parametrize("layer", [Layer.DELIVERY, Layer.GENERATION])
def test_the_right_vintage_is_selected_for_a_date(on, expected, layer):
    assert load_specs("TOU-DR1", layer, on=on).effective_date == expected


def test_a_calendar_2026_sdge_run_is_now_covered_end_to_end():
    """The concrete thing these specs unblock. Session 6 could not price an SDG&E calendar
    year because the only committed vintage began 2026-06-01 and the engine refuses to
    extrapolate to a date no spec covers."""
    for layer in (Layer.DELIVERY, Layer.GENERATION):
        versions = load_spec_versions("TOU-DR1", layer)
        assert min(v.effective_date for v in versions) <= date(2026, 1, 1)
        assert len(versions) == 4


def test_generation_held_across_the_june_delivery_change():
    """Documented in the spec headers and worth pinning: the 6/1/2026 filing moved the
    delivery layer (UDC total 0.34061 -> 0.32948) and left EECC untouched. A tool that
    models "the rate changed on 6/1" as one event misprices one layer or the other for
    every bill spanning that date."""
    april_d, april_g = _layers(date(2026, 4, 1))
    june_d, june_g = _layers(date(2026, 6, 1))
    for season in (Season.SUMMER, Season.WINTER):
        for period in april_g.tou.periods:
            assert april_g.energy_rate(season, period).for_customer(care=False) == pytest.approx(
                june_g.energy_rate(season, period).for_customer(care=False)
            )
    assert april_d.energy_rate(Season.SUMMER, "on_peak").for_customer(care=False) != pytest.approx(
        june_d.energy_rate(Season.SUMMER, "on_peak").for_customer(care=False)
    )


def test_may_and_april_vintages_differ_only_in_their_period_definitions():
    """The 2026-05-01 vintage exists solely because the window change landed inside the
    4/1 rate vintage — so its rates must be identical to 4/1's, and its TOU rules must
    not be."""
    april_d, april_g = _layers(date(2026, 4, 1))
    may_d, may_g = _layers(date(2026, 5, 1))
    for a, m in ((april_d, may_d), (april_g, may_g)):
        assert a.energy == m.energy
        assert a.seasons == m.seasons
        assert a.tou != m.tou
    assert april_d.baseline.credit_per_kwh == may_d.baseline.credit_per_kwh
    assert april_d.fixed_per_day == may_d.fixed_per_day
