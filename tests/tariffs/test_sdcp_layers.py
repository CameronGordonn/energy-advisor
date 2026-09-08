"""San Diego Community Power: the second San Diego CCA generation overlay.

`test_cca_overlay.py` covers the vintaged PCIA and the CEA layer. This file covers what
SDCP adds that CEA did not, and each of those is a way a generic calculator gets a San
Diego bill wrong:

1. **SDCP publishes two different rate sheets by enrollment cohort.** Which one applies is
   a jurisdiction fact the customer cannot elect, invisible on SDCP's marketing pages, and
   worth ~$33/yr. Modeled as two providers so the loader refuses to choose.
2. **Two 2026 vintages, and they carry different TOU WINDOWS** — the same 2026-05-01
   super-off-peak change SDG&E made. The same publisher's two dated sheets differing in
   exactly the disputed way is the cleanest corroboration yet of open decision 1.
3. **The PCIA can invert the supplier comparison in the cheapest hours.** SDCP is cheaper
   than bundled SDG&E in every period on a matched vintage — until the exit fee a CCA
   customer pays is added back, which flips exactly the window a battery or EV charges in.
"""

from __future__ import annotations

from datetime import date

import pytest

from tariffs.loader import (
    AmbiguousProviderError,
    load_spec_versions,
    load_specs,
)
from tariffs.schema import Layer, Season

COHORTS = ("SDCP-2021V", "SDCP-2022V")
VINTAGES = (date(2026, 1, 1), date(2026, 5, 1))

# Read off the PowerOn column of each cohort's sheet; see the spec citations.
SHEET = {
    ("SDCP-2021V", date(2026, 1, 1)): {
        "summer_on_peak": 0.29626,
        "summer_off_peak": 0.08656,
        "summer_super_off_peak": 0.01000,
        "winter_on_peak": 0.22551,
        "winter_off_peak": 0.14787,
        "winter_super_off_peak": 0.06163,
    },
    ("SDCP-2021V", date(2026, 5, 1)): {
        "summer_on_peak": 0.29579,
        "summer_off_peak": 0.08635,
        "summer_super_off_peak": 0.01000,
        "winter_on_peak": 0.22513,
        "winter_off_peak": 0.14758,
        "winter_super_off_peak": 0.06144,
    },
    ("SDCP-2022V", date(2026, 1, 1)): {
        "summer_on_peak": 0.30184,
        "summer_off_peak": 0.09214,
        "summer_super_off_peak": 0.01000,
        "winter_on_peak": 0.23109,
        "winter_off_peak": 0.15345,
        "winter_super_off_peak": 0.06721,
    },
    ("SDCP-2022V", date(2026, 5, 1)): {
        "summer_on_peak": 0.30138,
        "summer_off_peak": 0.09194,
        "summer_super_off_peak": 0.01000,
        "winter_on_peak": 0.23072,
        "winter_off_peak": 0.15317,
        "winter_super_off_peak": 0.06703,
    },
}


def _sdcp(provider, on):
    return load_specs("TOU-DR1", Layer.GENERATION, on=on, provider=provider)


def _rate(spec, key, care=False):
    season, period = key.split("_", 1)
    return spec.energy_rate(Season(season), period).for_customer(care=care)


# --- the rates themselves -------------------------------------------------------------


@pytest.mark.parametrize("provider", COHORTS)
@pytest.mark.parametrize("effective", VINTAGES)
def test_sdcp_rates_are_the_adopted_sheet(provider, effective):
    spec = _sdcp(provider, effective)
    for key, expected in SHEET[(provider, effective)].items():
        assert _rate(spec, key) == pytest.approx(expected, abs=1e-9), key


@pytest.mark.parametrize("provider", COHORTS)
@pytest.mark.parametrize("effective", VINTAGES)
def test_every_sdcp_spec_carries_a_citation(provider, effective):
    assert "sdcommunitypower.org" in _sdcp(provider, effective).citation


@pytest.mark.parametrize("provider", COHORTS)
@pytest.mark.parametrize("effective", VINTAGES)
def test_sdcp_charges_care_customers_the_same_generation_rate(provider, effective):
    """SDCP's Rate Key says the mapping "will not impact service, billing, or CARE/FERA
    status"; its SDG&E mapping table lists base schedule codes only, with no CARE or FERA
    variants, and no rate table on the sheet carries a CARE column. SDCP prices by
    SCHEDULE — CARE is a customer STATUS that SDG&E administers on the SDG&E bill.

    This settles what the CCA charges. It does NOT settle how SDG&E composes the CARE
    discount for a CCA customer — open decision 9, still open."""
    spec = _sdcp(provider, effective)
    for key in SHEET[(provider, effective)]:
        assert _rate(spec, key, care=True) == _rate(spec, key, care=False), key


@pytest.mark.parametrize("provider", COHORTS)
@pytest.mark.parametrize("effective", VINTAGES)
def test_summer_super_off_peak_is_floored_at_a_penny(provider, effective):
    """A round $0.01000 repeated across four independent sheets is a policy floor, not a
    computed rate. It is the reason the PCIA inversion below bites where it does."""
    assert _rate(_sdcp(provider, effective), "summer_super_off_peak") == pytest.approx(0.01)


# --- the cohort split ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("effective", "differential"), [(date(2026, 1, 1), 0.00558), (date(2026, 5, 1), 0.00559)]
)
def test_the_cohort_differential_is_a_clean_constant(effective, differential):
    """National City and the unincorporated county pay a flat adder over the 2021 cohort —
    the same in every period, so it shifts the level without reshaping the TOU signal. It
    is not electable, which is why it is a provider and not a product."""
    a, b = _sdcp("SDCP-2021V", effective), _sdcp("SDCP-2022V", effective)
    for key in SHEET[("SDCP-2021V", effective)]:
        expected = 0.0 if key == "summer_super_off_peak" else differential
        assert _rate(b, key) - _rate(a, key) == pytest.approx(expected, abs=1e-9), key


def test_the_two_cohorts_cannot_be_selected_by_the_loader_for_the_customer():
    with pytest.raises(AmbiguousProviderError, match="customer fact"):
        load_spec_versions("TOU-DR1", Layer.GENERATION)
    for provider in COHORTS:
        versions = load_spec_versions("TOU-DR1", Layer.GENERATION, provider=provider)
        got = {s.provider for s in versions}
        assert got == {provider}


def test_four_providers_now_supply_this_schedules_generation():
    """SDG&E bundled, CEA, and SDCP's two cohorts. Asserted as a count because session 9's
    provider bug was caught by a count assertion, not by inspection."""
    with pytest.raises(AmbiguousProviderError) as exc:
        load_spec_versions("TOU-DR1", Layer.GENERATION)
    assert "4 providers" in str(exc.value)


# --- vintages and the 2026-05-01 window change -----------------------------------------


@pytest.mark.parametrize("provider", COHORTS)
def test_each_cohort_has_both_2026_vintages(provider):
    versions = load_spec_versions("TOU-DR1", Layer.GENERATION, provider=provider)
    assert [v.effective_date for v in versions] == list(VINTAGES)


@pytest.mark.parametrize("provider", COHORTS)
def test_the_january_sheet_restricts_the_midday_window_to_march_and_april(provider):
    """Pricing Jan-Apr 2026 with the year-round window would reclassify four hours of every
    weekday from off-peak to super-off-peak."""
    spec = _sdcp(provider, date(2026, 1, 1))
    for month in range(1, 13):
        expected = "super_off_peak" if month in (3, 4) else "off_peak"
        assert spec.tou.period_for(11, month, weekday=True) == expected, month


@pytest.mark.parametrize("provider", COHORTS)
def test_the_may_sheet_makes_the_midday_window_year_round(provider):
    """The same publisher's two dated sheets differ in exactly the way SDG&E's own
    publications say the tariff changed on 2026-05-01 — the cleanest corroboration yet of
    open decision 1's residual caveat, which CEA had already supported."""
    spec = _sdcp(provider, date(2026, 5, 1))
    for month in range(1, 13):
        assert spec.tou.period_for(11, month, weekday=True) == "super_off_peak", month


@pytest.mark.parametrize("provider", COHORTS)
@pytest.mark.parametrize("effective", VINTAGES)
def test_sdcp_and_sdge_delivery_classify_every_hour_identically(provider, effective):
    """A CCA rides SDG&E's meter and schedule. If the two layers disagreed about an hour
    they would price the same kWh into different buckets."""
    sdcp = _sdcp(provider, effective)
    delivery = load_specs("TOU-DR1", Layer.DELIVERY, on=effective, provider="SDG&E")
    assert sdcp.seasons == delivery.seasons
    for month in range(1, 13):
        for hour in range(24):
            for weekday in (True, False):
                assert sdcp.tou.period_for(hour, month, weekday) == delivery.tou.period_for(
                    hour, month, weekday
                ), (month, hour, weekday)


# --- the finding: the exit fee decides, not the CCA's rates -----------------------------


def _pcia(on, vintage):
    delivery = load_specs("TOU-DR1", Layer.DELIVERY, on=on, provider="SDG&E")
    adder = next(a for a in delivery.adders if "Power Charge Indifference" in a.name)
    return adder.vintage_rate(vintage)


@pytest.mark.parametrize("provider", COHORTS)
def test_sdcp_undercuts_bundled_sdge_in_every_period_on_a_matched_vintage(provider):
    """The opposite shape to CEA, which is dearer in summer and cheaper in winter. Compared
    on the same 1/1/2026 vintage, so this is a rate difference and not a vintage artifact."""
    sdcp = _sdcp(provider, date(2026, 1, 1))
    eecc = load_specs("TOU-DR1", Layer.GENERATION, on=date(2026, 1, 1), provider="SDG&E")
    for key in SHEET[(provider, date(2026, 1, 1))]:
        assert _rate(sdcp, key) < _rate(eecc, key), key


def test_the_2018_pcia_inverts_the_comparison_only_in_summer_super_off_peak():
    """⭐ The finding. A CCA customer pays the exit fee a bundled customer does not, and on
    a 2018 vintage it is large enough to flip exactly ONE period — summer super-off-peak,
    which is the window a battery charges in and the window load-shifting advice targets.
    So "the CCA is cheaper" is true in general and false in precisely the hours a
    storage or EV recommendation turns on."""
    on = date(2026, 1, 1)
    sdcp = _sdcp("SDCP-2021V", on)
    eecc = load_specs("TOU-DR1", Layer.GENERATION, on=on, provider="SDG&E")
    pcia = _pcia(on, "2018")

    inverted = [k for k in SHEET[("SDCP-2021V", on)] if _rate(sdcp, k) + pcia > _rate(eecc, k)]
    assert inverted == ["summer_super_off_peak"]
    assert _rate(sdcp, "summer_super_off_peak") + pcia == pytest.approx(0.04662, abs=1e-9)
    assert _rate(eecc, "summer_super_off_peak") == pytest.approx(0.04126, abs=1e-9)


def test_a_2024_vintage_customer_loses_in_five_of_six_periods():
    """Same CCA, same sheet, different exit-fee vintage: the answer reverses. Which
    supplier wins is a function of the customer's PCIA vintage and load shape, not of the
    CCA — so no single verdict can be published for "SDCP customers"."""
    on = date(2026, 1, 1)
    sdcp = _sdcp("SDCP-2021V", on)
    eecc = load_specs("TOU-DR1", Layer.GENERATION, on=on, provider="SDG&E")
    pcia = _pcia(on, "2024")

    dearer = [k for k in SHEET[("SDCP-2021V", on)] if _rate(sdcp, k) + pcia > _rate(eecc, k)]
    assert len(dearer) == 5
    assert "summer_on_peak" not in dearer
