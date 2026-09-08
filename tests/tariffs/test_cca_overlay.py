"""The CCA generation overlay: SDG&E delivery + vintaged PCIA + a CCA's own generation.

CLAUDE.md's differentiation invariant 4 names this explicitly — "model the CCA layer:
[a CCA's] generation rates layered on SDG&E delivery ... generic calculators skip [it]".
Three things have to hold for that layering to be trustworthy:

1. **The PCIA is vintaged, and the vintage is never guessed.** Across SDG&E's 2026 sheets
   it spans 0.01535 to 0.05055 $/kWh — a wider range than TOU-DR1's entire super-off-peak
   generation rate — so a defaulted vintage would be the largest single error on a CCA bill.
2. **A bundled layer and a CCA layer are not interchangeable.** Both are legitimately
   "TOU-DR1 generation"; loading one when the customer is on the other misprices by up to
   20 c/kWh in a single period, and would look entirely normal doing it.
3. **The two layers must classify every hour identically**, or they price the same kWh into
   different TOU buckets.
"""

from __future__ import annotations

from datetime import date

import pytest

from tariffs.loader import (
    SPECS_DIR,
    AmbiguousProviderError,
    load_spec_file,
    load_spec_versions,
    load_specs,
)
from tariffs.schema import AppliesTo, Layer, Season, Service

CEA = "cea_tou_dr1_generation_2026-06-01.yaml"


@pytest.fixture(scope="module")
def cea():
    return load_spec_file(SPECS_DIR / CEA)


@pytest.fixture(scope="module")
def sdge_delivery():
    return load_specs("TOU-DR1", Layer.DELIVERY, on=date(2026, 6, 1), provider="SDG&E")


@pytest.fixture(scope="module")
def sdge_generation():
    return load_specs("TOU-DR1", Layer.GENERATION, on=date(2026, 6, 1), provider="SDG&E")


# --- the vintaged PCIA -------------------------------------------------------------------


def _pcia(spec):
    return next(a for a in spec.adders if "Power Charge Indifference" in a.name)


@pytest.mark.parametrize(
    ("effective", "vintage", "expected"),
    [
        # The 1/1/2026 sheet prints its own table; 4/1 onward print a different one.
        (date(2026, 1, 1), "2018", 0.03662),
        (date(2026, 1, 1), "2024", 0.05045),
        (date(2026, 1, 1), "2009", 0.01535),
        (date(2026, 4, 1), "2018", 0.03670),
        (date(2026, 5, 1), "2018", 0.03670),
        (date(2026, 6, 1), "2018", 0.03670),
        (date(2026, 6, 1), "2024", 0.05055),
        (date(2026, 6, 1), "2009", 0.01538),
    ],
)
def test_pcia_is_read_per_vintage_and_per_rate_sheet(effective, vintage, expected):
    spec = load_specs("TOU-DR1", Layer.DELIVERY, on=effective, provider="SDG&E")
    assert _pcia(spec).vintage_rate(vintage) == pytest.approx(expected, abs=1e-9)


def test_the_vintage_spread_is_wide_enough_to_matter(sdge_delivery):
    """Motivates refusing to default. The cheapest and dearest vintages differ by about
    3.5 c/kWh; on a 6,000 kWh/yr household that is ~$210 a year, more than the entire
    annual saving the PG&E case study found from switching supplier ($170.72)."""
    table = _pcia(sdge_delivery).per_kwh_by_vintage
    spread = max(table.values()) - min(table.values())
    assert spread == pytest.approx(0.03517, abs=1e-5)
    assert spread * 6000 > 170.72


def test_a_missing_vintage_raises_rather_than_defaulting(sdge_delivery):
    with pytest.raises(ValueError, match="never defaulted"):
        _pcia(sdge_delivery).vintage_rate(None)


def test_an_unknown_vintage_raises_and_names_what_is_priced(sdge_delivery):
    with pytest.raises(ValueError, match="unknown vintage"):
        _pcia(sdge_delivery).vintage_rate("1999")


def test_the_pcia_is_billed_only_to_unbundled_customers(sdge_delivery):
    """A bundled customer pays EECC instead; charging them a PCIA would double-count."""
    pcia = _pcia(sdge_delivery)
    assert pcia.applies_to is AppliesTo.CCA
    assert pcia.applies_to.covers(Service.CCA)
    assert not pcia.applies_to.covers(Service.BUNDLED)


def test_the_2001_legacy_vintage_is_absent_because_it_is_direct_access_only(sdge_delivery):
    assert "2001" not in _pcia(sdge_delivery).per_kwh_by_vintage


# --- provider disambiguation --------------------------------------------------------------


def test_loading_tou_dr1_generation_without_a_provider_now_raises():
    """Bundled EECC and CEA are both TOU-DR1 generation. Choosing for the customer would
    misprice by up to 20 c/kWh while looking perfectly normal."""
    with pytest.raises(AmbiguousProviderError, match="customer fact"):
        load_spec_versions("TOU-DR1", Layer.GENERATION)


def test_naming_the_provider_selects_that_generation_layer():
    assert {
        s.provider for s in load_spec_versions("TOU-DR1", Layer.GENERATION, provider="SDG&E")
    } == {"SDG&E"}
    assert {
        s.provider for s in load_spec_versions("TOU-DR1", Layer.GENERATION, provider="CEA")
    } == {"CEA"}


def test_delivery_is_unambiguous_because_only_the_utility_delivers(sdge_delivery):
    """A CCA supplies generation only; SDG&E always delivers. So the delivery layer needs
    no provider and must keep loading without one."""
    versions = load_spec_versions("TOU-DR1", Layer.DELIVERY)
    assert {s.provider for s in versions} == {"SDG&E"}


# --- the CEA layer itself ------------------------------------------------------------------


def test_cea_and_sdge_delivery_classify_every_hour_identically(cea, sdge_delivery):
    assert cea.seasons == sdge_delivery.seasons
    for month in range(1, 13):
        for hour in range(24):
            for weekday in (True, False):
                assert cea.tou.period_for(hour, month, weekday) == sdge_delivery.tou.period_for(
                    hour, month, weekday
                )


def test_cea_super_off_peak_is_year_round(cea):
    """CEA's June 2026 schedule dropped the March/April restriction, independently
    corroborating SDG&E's 2026-05-01 window change (open decision 1's residual caveat)."""
    for month in range(1, 13):
        assert cea.tou.period_for(11, month, weekday=True) == "super_off_peak"


@pytest.mark.parametrize(
    ("season", "period", "expected"),
    [
        ("summer", "on_peak", 0.55397),
        ("summer", "off_peak", 0.22298),
        ("summer", "super_off_peak", 0.04914),
        ("winter", "on_peak", 0.19791),
        ("winter", "off_peak", 0.08433),
        ("winter", "super_off_peak", 0.05138),
    ],
)
def test_cea_rates_are_the_adopted_schedule(cea, season, period, expected):
    assert cea.energy_rate(Season(season), period).for_customer(care=False) == pytest.approx(
        expected, abs=1e-9
    )


def test_cea_charges_care_customers_the_same_generation_rate(cea):
    """CEA's own mapping table sends TOU-DR-1, -CARE and -MB to one CEA rate; the CARE
    discount is applied by SDG&E on its own charges. Read off the sheet, not assumed."""
    for season in (Season.SUMMER, Season.WINTER):
        for period in cea.tou.periods:
            rate = cea.energy_rate(season, period)
            assert rate.for_customer(care=True) == rate.for_customer(care=False)


def test_the_rate_relief_credit_is_carried_and_more_than_offsets_a_2018_pcia(cea, sdge_delivery):
    """At 3.871 c/kWh it exceeds the 3.670 c/kWh PCIA a 2018-vintage CCA customer pays, so
    dropping it would overstate their cost by more than the exit fee usually blamed."""
    credit = next(a for a in cea.adders if "Rate Relief" in a.name)
    assert credit.per_kwh == pytest.approx(-0.03871)
    assert abs(credit.per_kwh) > _pcia(sdge_delivery).vintage_rate("2018")
    assert credit.applies_to is AppliesTo.ALL


def test_cea_is_seasonally_opposite_to_bundled_sdge(cea, sdge_generation):
    """The finding the spec header claims, pinned so it cannot rot: CEA is dearer in summer
    and cheaper in winter, so which supplier wins depends on the household's seasonal shape
    rather than on the CCA. A tool reporting one answer for everyone is wrong for half of
    them."""
    for period in cea.tou.periods:
        summer_cea = cea.energy_rate(Season.SUMMER, period).for_customer(care=False)
        summer_sdge = sdge_generation.energy_rate(Season.SUMMER, period).for_customer(care=False)
        assert summer_cea > summer_sdge, f"expected CEA dearer in summer {period}"

        winter_cea = cea.energy_rate(Season.WINTER, period).for_customer(care=False)
        winter_sdge = sdge_generation.energy_rate(Season.WINTER, period).for_customer(care=False)
        assert winter_cea < winter_sdge, f"expected CEA cheaper in winter {period}"
