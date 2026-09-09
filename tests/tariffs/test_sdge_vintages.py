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

Sources, retrieved 2026-09-07 (1/1, 4/1) and 2026-09-09 (8/1):
  "1-1-26 Schedule TOU-DR1 Total Rates Table.pdf" / "...TOU-DR1-CARE..."
  "4-1-26 Schedule TOU-DR1 Total Rates Table.pdf" / "...TOU-DR1-CARE..."
  "8-1-26 Schedule TOU-DR1 Total Rates Table.pdf" / "...TOU-DR1-CARE..."
  (there is no 5-1-26 sheet in that series; the URL returns HTTP 404. Nor is there a
  7-1-26, 9-1-26, 10-1-26 or 11-1-26 — all four 404 as of 2026-09-09, so 8/1 is the last
  vintage of the year and governs August through December.)
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
    date(2026, 8, 1): (
        "sdge_tou_dr1_delivery_2026-08-01.yaml",
        "sdge_tou_dr1_generation_2026-08-01.yaml",
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
    date(2026, 6, 1): {
        ("summer", "on_peak"): (0.68459, 0.43553),
        ("summer", "off_peak"): (0.46392, 0.29209),
        ("summer", "super_off_peak"): (0.37660, 0.23533),
        ("winter", "on_peak"): (0.61014, 0.38713),
        ("winter", "off_peak"): (0.52843, 0.33402),
        ("winter", "super_off_peak"): (0.43767, 0.27503),
    },
    date(2026, 8, 1): {
        ("summer", "on_peak"): (0.69135, 0.43992),
        ("summer", "off_peak"): (0.46421, 0.29228),
        ("summer", "super_off_peak"): (0.37433, 0.23386),
        ("winter", "on_peak"): (0.61471, 0.39010),
        ("winter", "off_peak"): (0.53060, 0.33543),
        ("winter", "super_off_peak"): (0.43719, 0.27472),
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
    """TOU-DR1's UDC total is period- and season-flat on all five 2026 vintages, so 100%
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


@pytest.mark.parametrize("effective", [date(2026, 5, 1), date(2026, 6, 1), date(2026, 8, 1)])
@pytest.mark.parametrize("month", range(1, 13))
def test_post_may_vintages_apply_daytime_super_off_peak_year_round(effective, month):
    for spec in _layers(effective):
        assert spec.tou.period_for(11, month, weekday=True) == "super_off_peak"


@pytest.mark.parametrize("effective", sorted(VINTAGES))
@pytest.mark.parametrize("month", range(1, 13))
def test_the_windows_the_2026_filing_did_not_touch_are_identical_everywhere(effective, month):
    """Only the weekday 10:00-14:00 carve-out moved. Overnight, evening peak and the
    weekend table are the same on all five vintages."""
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
        (date(2026, 7, 31), date(2026, 6, 1)),
        (date(2026, 8, 1), date(2026, 8, 1)),
        (date(2026, 12, 31), date(2026, 8, 1)),
    ],
)
@pytest.mark.parametrize("layer", [Layer.DELIVERY, Layer.GENERATION])
def test_the_right_vintage_is_selected_for_a_date(on, expected, layer):
    assert load_specs("TOU-DR1", layer, on=on, provider="SDG&E").effective_date == expected


def test_a_calendar_2026_sdge_run_is_now_covered_end_to_end():
    """The concrete thing these specs unblock. Session 6 could not price an SDG&E calendar
    year because the only committed vintage began 2026-06-01 and the engine refuses to
    extrapolate to a date no spec covers."""
    for layer in (Layer.DELIVERY, Layer.GENERATION):
        versions = load_spec_versions("TOU-DR1", layer, provider="SDG&E")
        assert min(v.effective_date for v in versions) <= date(2026, 1, 1)
        assert len(versions) == 5


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


def test_the_august_filing_moved_both_layers_in_opposite_directions():
    """The counterpoint to `test_generation_held_across_the_june_delivery_change`, and the
    reason "the SDG&E rate changed" is never a single fact. On 8/1/2026 delivery went DOWN
    (UDC total 0.32948 -> 0.32601) while generation went UP in every period (summer
    on-peak EECC 0.34920 -> 0.35943), so the all-in summer on-peak rate ROSE even though
    the delivery rate fell. A blended single-rate model gets the sign wrong on one of them
    no matter which way it rounds."""
    june_d, june_g = _layers(date(2026, 6, 1))
    aug_d, aug_g = _layers(date(2026, 8, 1))
    for season in (Season.SUMMER, Season.WINTER):
        for period in june_g.tou.periods:
            june_delivery = june_d.energy_rate(season, period).for_customer(care=False)
            aug_delivery = aug_d.energy_rate(season, period).for_customer(care=False)
            june_gen = june_g.energy_rate(season, period).for_customer(care=False)
            aug_gen = aug_g.energy_rate(season, period).for_customer(care=False)
            assert aug_delivery < june_delivery, (season, period)
            assert aug_gen > june_gen, (season, period)
    assert (
        PRINTED[date(2026, 8, 1)][("summer", "on_peak")][0]
        > (PRINTED[date(2026, 6, 1)][("summer", "on_peak")][0])
    )


def test_the_august_filing_moved_the_pcia_too():
    """Invisible from the energy rates, and it lands on CCA customers only: every PCIA
    vintage fell ~0.00216/kWh on the 8/1 sheet (2018: 0.03670 -> 0.03454). An Aug-Dec CCA
    bill priced with the 6/1 sheet is wrong in a way no bundled test would catch, which is
    why this is pinned rather than left to the layer-sum gate."""
    june_d, _ = _layers(date(2026, 6, 1))
    aug_d, _ = _layers(date(2026, 8, 1))
    (june_pcia,) = june_d.adders
    (aug_pcia,) = aug_d.adders
    assert set(aug_pcia.per_kwh_by_vintage) == set(june_pcia.per_kwh_by_vintage)
    for vintage, rate in aug_pcia.per_kwh_by_vintage.items():
        assert rate < june_pcia.per_kwh_by_vintage[vintage], vintage
    assert aug_pcia.per_kwh_by_vintage["2018"] == pytest.approx(0.03454)
    assert aug_pcia.per_kwh_by_vintage["2026"] == pytest.approx(0.04771)


def test_the_baseline_credit_grew_on_the_august_sheet():
    """(0.10663) -> (0.10702) standard, (0.06931) -> (0.06956) CARE — read off the printed
    tables, and the largest single credit on a TOU-DR1 bill."""
    june_d, _ = _layers(date(2026, 6, 1))
    aug_d, _ = _layers(date(2026, 8, 1))
    assert aug_d.baseline.credit_per_kwh.standard == pytest.approx(-0.10702)
    assert aug_d.baseline.credit_per_kwh.care == pytest.approx(-0.06956)
    assert aug_d.baseline.credit_per_kwh.standard < june_d.baseline.credit_per_kwh.standard
    assert aug_d.baseline.allowances == june_d.baseline.allowances


# =========================================================================================
# TOU-DR2 and EV-TOU-5 — the other two rankable SDG&E residential schedules.
#
# Session 6 committed these at 6/1/2026 only, and only their DELIVERY halves, so neither
# could be priced for a bundled customer at all, let alone ranked over a calendar year.
# Session 16 added the earlier rate vintages AND the missing generation layers. Two things
# the TOU-DR1 block above does not exercise are pinned here:
#
# 1. **TOU-DR2 has no 2026-05-01 vintage, and that is a fact about the schedule.** It has
#    no super-off-peak period, so the filing that moved the weekday 10:00-14:00 window
#    year-round cannot touch it. Three vintages is correct; a fourth would be fiction.
# 2. **TOU-DR2's delivery layer is NOT period-flat** — unlike TOU-DR1, whose UDC total is
#    flat, so that 100% of its TOU signal lives in generation. TOU-DR2's UDC is
#    time-differentiated in summer. A load-shift analysis that varied only generation
#    would be right on TOU-DR1 and wrong here.
#
# Sources, retrieved 2026-09-08 (1/1, 4/1, 6/1) and 2026-09-09 (8/1), same series as above:
#   "{1,4,6,8}-1-26 Schedule TOU-DR2 Total Rates Table.pdf"  / "...TOU-DR2-CARE..."
#   "{1,4,6,8}-1-26 Schedule EV-TOU-5 Total Rates Table.pdf" / "...EV-TOU-5-CARE..."
#   (no 5-1-26 sheet exists for either schedule; both URLs return HTTP 404. 8/1 is the last
#   2026 vintage in the series and governs August through December.)
# =========================================================================================

DR2_VINTAGES = [date(2026, 1, 1), date(2026, 4, 1), date(2026, 6, 1), date(2026, 8, 1)]
EV_VINTAGES = [
    date(2026, 1, 1),
    date(2026, 4, 1),
    date(2026, 5, 1),
    date(2026, 6, 1),
    date(2026, 8, 1),
]

# (season, period) -> (Total Electric Rate, Total Adjusted CARE Rate), as printed.
DR2_PRINTED = {
    date(2026, 1, 1): {
        ("summer", "on_peak"): (0.70103, 0.44621),
        ("summer", "off_peak"): (0.42936, 0.26963),
        ("winter", "on_peak"): (0.62200, 0.39484),
        ("winter", "off_peak"): (0.48485, 0.30570),
    },
    date(2026, 4, 1): {
        ("summer", "on_peak"): (0.70021, 0.44568),
        ("summer", "off_peak"): (0.42886, 0.26930),
        ("winter", "on_peak"): (0.62127, 0.39437),
        ("winter", "off_peak"): (0.48429, 0.30533),
    },
    date(2026, 6, 1): {
        ("summer", "on_peak"): (0.68907, 0.43844),
        ("summer", "off_peak"): (0.41773, 0.26207),
        ("winter", "on_peak"): (0.61014, 0.38713),
        ("winter", "off_peak"): (0.47316, 0.29810),
    },
    date(2026, 8, 1): {
        ("summer", "on_peak"): (0.69597, 0.44292),
        ("summer", "off_peak"): (0.41666, 0.26137),
        ("winter", "on_peak"): (0.61471, 0.39010),
        ("winter", "off_peak"): (0.47372, 0.29846),
    },
}

EV_PRINTED = {
    date(2026, 1, 1): {
        ("summer", "on_peak"): (0.79988, 0.51046),
        ("summer", "off_peak"): (0.50245, 0.31714),
        ("summer", "super_off_peak"): (0.12424, 0.07130),
        ("winter", "on_peak"): (0.52926, 0.33456),
        ("winter", "off_peak"): (0.47267, 0.29778),
        ("winter", "super_off_peak"): (0.11686, 0.06650),
    },
    date(2026, 4, 1): {
        ("summer", "on_peak"): (0.80292, 0.51244),
        ("summer", "off_peak"): (0.50584, 0.31934),
        ("summer", "super_off_peak"): (0.12852, 0.07408),
        ("winter", "on_peak"): (0.53263, 0.33675),
        ("winter", "off_peak"): (0.47610, 0.30001),
        ("winter", "super_off_peak"): (0.12115, 0.06929),
    },
    date(2026, 6, 1): {
        ("summer", "on_peak"): (0.79321, 0.50613),
        ("summer", "off_peak"): (0.49613, 0.31303),
        ("summer", "super_off_peak"): (0.12852, 0.07408),
        ("winter", "on_peak"): (0.52292, 0.33044),
        ("winter", "off_peak"): (0.46639, 0.29370),
        ("winter", "super_off_peak"): (0.12115, 0.06929),
    },
    date(2026, 8, 1): {
        ("summer", "on_peak"): (0.80205, 0.51188),
        ("summer", "off_peak"): (0.49627, 0.31312),
        ("summer", "super_off_peak"): (0.13090, 0.07563),
        ("winter", "on_peak"): (0.52383, 0.33103),
        ("winter", "off_peak"): (0.46566, 0.29322),
        ("winter", "super_off_peak"): (0.12332, 0.07070),
    },
}
# The 5/1 vintage is the 4/1 sheet's rates (no 5/1 sheet exists), so it shares that table.
EV_PRINTED[date(2026, 5, 1)] = EV_PRINTED[date(2026, 4, 1)]

# schedule_id -> (file stem, vintages, printed table)
OTHER_SCHEDULES = {
    "TOU-DR2": ("sdge_tou_dr2", DR2_VINTAGES, DR2_PRINTED),
    "EV-TOU-5": ("sdge_ev_tou_5", EV_VINTAGES, EV_PRINTED),
}


def _other_layers(schedule: str, effective: date):
    stem, _, _ = OTHER_SCHEDULES[schedule]
    return (
        load_spec_file(SPECS_DIR / f"{stem}_delivery_{effective}.yaml"),
        load_spec_file(SPECS_DIR / f"{stem}_generation_{effective}.yaml"),
    )


def _other_cells(schedule: str):
    """(schedule, effective, season, period) for every printed cell of a schedule."""
    _, vintages, printed = OTHER_SCHEDULES[schedule]
    return [
        (schedule, eff, season, period)
        for eff in vintages
        for (season, period) in sorted(printed[eff])
    ]


ALL_OTHER_CELLS = _other_cells("TOU-DR2") + _other_cells("EV-TOU-5")


@pytest.mark.parametrize(("schedule", "effective", "season", "period"), ALL_OTHER_CELLS)
def test_other_schedules_layers_sum_to_the_printed_total_electric_rate(
    schedule, effective, season, period
):
    delivery, generation = _other_layers(schedule, effective)
    s = Season(season)
    total = delivery.energy_rate(s, period).for_customer(care=False) + generation.energy_rate(
        s, period
    ).for_customer(care=False)
    _, _, printed = OTHER_SCHEDULES[schedule]
    assert total == pytest.approx(printed[effective][(season, period)][0], abs=1e-5)


@pytest.mark.parametrize(("schedule", "effective", "season", "period"), ALL_OTHER_CELLS)
def test_other_schedules_layers_sum_to_the_printed_care_rate(schedule, effective, season, period):
    """The same CARE split derived on TOU-DR1 — delivery keeps the 0.00864 exemption, both
    layers take the 35% — has to rebuild the printed CARE total on two schedules it was
    never fitted to, including EV-TOU-5's collapsed super-off-peak row where the exemption
    is a quarter of the whole delivery charge."""
    delivery, generation = _other_layers(schedule, effective)
    s = Season(season)
    total = delivery.energy_rate(s, period).for_customer(care=True) + generation.energy_rate(
        s, period
    ).for_customer(care=True)
    _, _, printed = OTHER_SCHEDULES[schedule]
    assert total == pytest.approx(printed[effective][(season, period)][1], abs=1e-5)


@pytest.mark.parametrize(
    ("schedule", "effective"),
    [(s, e) for s, (_, v, _) in OTHER_SCHEDULES.items() for e in v],
)
def test_other_schedules_two_layers_agree_on_structure(schedule, effective):
    delivery, generation = _other_layers(schedule, effective)
    assert delivery.layer is Layer.DELIVERY
    assert generation.layer is Layer.GENERATION
    assert delivery.schedule_id == generation.schedule_id == schedule
    assert delivery.provider == generation.provider == "SDG&E"
    assert delivery.effective_date == generation.effective_date == effective
    assert delivery.seasons == generation.seasons
    assert delivery.tou == generation.tou


@pytest.mark.parametrize(("schedule", "expected"), [("TOU-DR2", 4), ("EV-TOU-5", 5)])
@pytest.mark.parametrize("layer", [Layer.DELIVERY, Layer.GENERATION])
def test_other_schedules_cover_calendar_2026_from_january(schedule, expected, layer):
    """The concrete thing these specs unblock: `marginal_energy_price` refuses dates no
    spec covers, so with 6/1 alone neither schedule could be ranked over a calendar year
    against TOU-DR1. EV-TOU-5 gets FIVE vintages (the 5/1 window split); TOU-DR2 gets
    four, because it has no super-off-peak window for that filing to move."""
    versions = load_spec_versions(schedule, layer, provider="SDG&E")
    assert len(versions) == expected
    assert min(v.effective_date for v in versions) <= date(2026, 1, 1)


# --- TOU-DR2: two periods, and a delivery layer that is NOT flat -------------------------


@pytest.mark.parametrize("effective", DR2_VINTAGES)
@pytest.mark.parametrize("month", range(1, 13))
@pytest.mark.parametrize("weekday", [True, False])
def test_tou_dr2_has_exactly_two_periods_every_day_of_the_year(effective, month, weekday):
    """No super-off-peak, and no weekday/weekend split: TOU-DR2 prices a Sunday in March
    exactly like a Tuesday in August. This is why it takes no 2026-05-01 vintage."""
    for spec in _other_layers("TOU-DR2", effective):
        assert set(spec.tou.periods) == {"on_peak", "off_peak"}
        assert spec.tou.period_for(17, month, weekday=weekday) == "on_peak"
        assert spec.tou.period_for(11, month, weekday=weekday) == "off_peak"
        assert spec.tou.period_for(3, month, weekday=weekday) == "off_peak"


def test_tou_dr2_has_no_may_vintage_because_it_has_no_super_off_peak_window():
    """Pinned as an assertion because 'the 5/1 file is missing' and 'the 5/1 file must not
    exist' look identical in a directory listing. SDG&E's super-off-peak page does not
    name TOU-DR2; one secondary source does, and is wrong."""
    for layer in (Layer.DELIVERY, Layer.GENERATION):
        versions = load_spec_versions("TOU-DR2", layer, provider="SDG&E")
        effectives = {v.effective_date for v in versions}
        assert date(2026, 5, 1) not in effectives
        assert effectives == set(DR2_VINTAGES)


@pytest.mark.parametrize("effective", DR2_VINTAGES)
def test_tou_dr2_delivery_is_period_differentiated_in_summer_but_flat_in_winter(effective):
    """The counterpoint to `test_delivery_is_period_flat_on_every_vintage` above. On
    TOU-DR1 every cent of TOU spread is generation; on TOU-DR2 the UDC total itself splits
    in summer (0.34550 vs 0.33903 on the 1/1 sheet) and not in winter. A tool that learned
    'SDG&E delivery is flat' from TOU-DR1 and applied it here misprices summer."""
    delivery, _ = _other_layers("TOU-DR2", effective)
    summer = {
        p: delivery.energy_rate(Season.SUMMER, p).for_customer(care=False)
        for p in delivery.tou.periods
    }
    winter = {
        p: delivery.energy_rate(Season.WINTER, p).for_customer(care=False)
        for p in delivery.tou.periods
    }
    assert summer["on_peak"] > summer["off_peak"], summer
    assert len(set(winter.values())) == 1, winter


# --- EV-TOU-5: the window change, and the 5/1 split ---------------------------------------


@pytest.mark.parametrize("effective", [date(2026, 1, 1), date(2026, 4, 1)])
@pytest.mark.parametrize("month", range(1, 13))
def test_ev_tou_5_pre_may_vintages_restrict_daytime_super_off_peak_to_march_and_april(
    effective, month
):
    """Sourced directly for EV-TOU-5, not inherited from TOU-DR1: SDG&E's own EV Pricing
    Plans page printed 'Midnight - 6:00 a.m. / 10:00 a.m. - 2:00 p.m. in March and April
    (Weekdays)' in its 2025-11-07 capture, the table in force on these effective dates."""
    expected = "super_off_peak" if month in (3, 4) else "off_peak"
    for spec in _other_layers("EV-TOU-5", effective):
        assert spec.tou.period_for(11, month, weekday=True) == expected


@pytest.mark.parametrize("effective", [date(2026, 5, 1), date(2026, 6, 1), date(2026, 8, 1)])
@pytest.mark.parametrize("month", range(1, 13))
def test_ev_tou_5_post_may_vintages_apply_daytime_super_off_peak_year_round(effective, month):
    for spec in _other_layers("EV-TOU-5", effective):
        assert spec.tou.period_for(11, month, weekday=True) == "super_off_peak"


@pytest.mark.parametrize("effective", EV_VINTAGES)
@pytest.mark.parametrize("month", range(1, 13))
def test_ev_tou_5_windows_the_2026_filing_did_not_touch_are_identical_everywhere(effective, month):
    """Only the weekday 10:00-14:00 carve-out moved. Overnight, evening peak and the
    weekend table are the same on all five vintages."""
    for spec in _other_layers("EV-TOU-5", effective):
        assert spec.tou.period_for(3, month, weekday=True) == "super_off_peak"
        assert spec.tou.period_for(17, month, weekday=True) == "on_peak"
        assert spec.tou.period_for(15, month, weekday=True) == "off_peak"
        assert spec.tou.period_for(11, month, weekday=False) == "super_off_peak"
        assert spec.tou.period_for(17, month, weekday=False) == "on_peak"


def test_ev_tou_5_may_and_april_vintages_differ_only_in_their_period_definitions():
    """Same shape as the TOU-DR1 assertion: the 2026-05-01 vintage exists solely because
    the window change landed inside the 4/1 rate vintage, so its rates must be identical
    to 4/1's and its TOU rules must not be."""
    april_d, april_g = _other_layers("EV-TOU-5", date(2026, 4, 1))
    may_d, may_g = _other_layers("EV-TOU-5", date(2026, 5, 1))
    for a, m in ((april_d, may_d), (april_g, may_g)):
        assert a.energy == m.energy
        assert a.seasons == m.seasons
        assert a.tou != m.tou
    assert april_d.fixed_per_day == may_d.fixed_per_day
    assert april_d.non_bypassable == may_d.non_bypassable


def test_ev_tou_5_has_no_baseline_credit_on_any_vintage():
    """Deliberately absent, not UNVERIFIED: no EV-TOU-5 rate table prints an 'Up to 130%
    of Baseline Adjustment Credit' row, where every TOU-DR1/TOU-DR2 table does. Modeling
    one would invent a credit the schedule does not grant."""
    for effective in EV_VINTAGES:
        delivery, _ = _other_layers("EV-TOU-5", effective)
        assert delivery.baseline is None
    for effective in DR2_VINTAGES:
        delivery, _ = _other_layers("TOU-DR2", effective)
        assert delivery.baseline is not None


@pytest.mark.parametrize(
    ("on", "expected"),
    [
        (date(2026, 1, 1), date(2026, 1, 1)),
        (date(2026, 3, 31), date(2026, 1, 1)),
        (date(2026, 4, 30), date(2026, 4, 1)),
        (date(2026, 5, 1), date(2026, 5, 1)),
        (date(2026, 5, 31), date(2026, 5, 1)),
        (date(2026, 6, 1), date(2026, 6, 1)),
        (date(2026, 7, 31), date(2026, 6, 1)),
        (date(2026, 8, 1), date(2026, 8, 1)),
        (date(2026, 12, 31), date(2026, 8, 1)),
    ],
)
@pytest.mark.parametrize("layer", [Layer.DELIVERY, Layer.GENERATION])
def test_ev_tou_5_selects_the_right_vintage_for_a_date(on, expected, layer):
    assert load_specs("EV-TOU-5", layer, on=on, provider="SDG&E").effective_date == expected


def test_the_august_filing_froze_ev_tou_5_super_off_peak_delivery_and_cut_the_rest():
    """⭐ One filing, three different behaviours on one schedule. On 8/1/2026 EV-TOU-5's
    on/off-peak UDC total fell 0.31711 -> 0.31218 while its SUPER-OFF-PEAK UDC total did
    not move at all, holding at 0.04114 for a third consecutive vintage — and generation
    rose in every period. So the delivery discount in the battery-charging window did not
    deepen; only the windows it is measured against got cheaper."""
    june_d, _ = _other_layers("EV-TOU-5", date(2026, 6, 1))
    aug_d, _ = _other_layers("EV-TOU-5", date(2026, 8, 1))
    for season in (Season.SUMMER, Season.WINTER):
        assert aug_d.energy_rate(season, "super_off_peak").for_customer(
            care=False
        ) == pytest.approx(june_d.energy_rate(season, "super_off_peak").for_customer(care=False))
        for period in ("on_peak", "off_peak"):
            assert aug_d.energy_rate(season, period).for_customer(care=False) < june_d.energy_rate(
                season, period
            ).for_customer(care=False)


@pytest.mark.parametrize("schedule", ["TOU-DR2", "EV-TOU-5"])
def test_the_august_filing_moved_generation_on_every_schedule(schedule):
    """The 6/1 filing moved delivery only on all three schedules; 8/1 moved generation on
    all three, upward in every period. Pinned per-schedule so a future transcription that
    copies one schedule's EECC table onto another fails here."""
    _, june_g = _other_layers(schedule, date(2026, 6, 1))
    _, aug_g = _other_layers(schedule, date(2026, 8, 1))
    for season in (Season.SUMMER, Season.WINTER):
        for period in june_g.tou.periods:
            assert aug_g.energy_rate(season, period).for_customer(care=False) > june_g.energy_rate(
                season, period
            ).for_customer(care=False), (schedule, season, period)


# --- the structural gap that let two schedules ship half-authored -------------------------


def test_every_sdge_delivery_vintage_has_a_matching_generation_vintage():
    """TOU-DR2 and EV-TOU-5 shipped in session 6 with delivery specs and no generation
    layer, so a bundled customer could not be priced on either — and nothing failed,
    because every test named its files explicitly. A half-authored schedule is invisible
    until someone tries to bill it, so pair completeness is asserted structurally here.

    TOU-DR-P was excluded here until 2026-09-09, when it stopped being unloadable and got
    its generation layer (Schedule EECC-TOU-DR-P, carrying the RYU event adder). It is now
    inside the gate, which means an 8/1/2026 TOU-DR-P delivery vintage cannot land without
    its generation twin either.
    """
    delivery = {
        (p.name.split("_delivery_")[0], p.name.split("_delivery_")[1])
        for p in SPECS_DIR.glob("sdge_*_delivery_*.yaml")
    }
    generation = {
        (p.name.split("_generation_")[0], p.name.split("_generation_")[1])
        for p in SPECS_DIR.glob("sdge_*_generation_*.yaml")
    }
    assert delivery, "glob found no SDG&E delivery specs"
    missing = delivery - generation
    assert not missing, (
        f"SDG&E delivery vintages with no matching generation layer: {sorted(missing)}"
    )
