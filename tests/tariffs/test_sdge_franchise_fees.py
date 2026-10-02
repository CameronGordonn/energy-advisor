"""SDG&E's city-dependent franchise fees and the CCA's CEC surcharge (session 31).

The lines were found missing by pricing SDCP's published specimen statement
(``notes/sdcp_specimen_bill_2026-10.md``): every rate on it matched the specs to the fifth
decimal and the bill still came out ~$11 short. The specimen is NOT a golden bill — its
account number is a placeholder and its own SDCP lines do not equal kWh x rate — so it is
used here the way ``tests/published_impacts/`` uses rate alerts: to pin the *structure*
of three lines whose arithmetic it shows, never to count toward the ±$2 claim.
"""

from __future__ import annotations

from datetime import date

import pytest

from tariffs.bill import MissingImputedGenerationError
from tariffs.bucketed import UsageSegment, compute_bill_from_usage
from tariffs.loader import load_spec_versions
from tariffs.schema import (
    Layer,
    MissingJurisdictionError,
    Service,
    Surcharge,
    UnverifiedChargeError,
)

FFD = "City of San Diego Franchise Fee Differential"
FFES = "Franchise Fee Equivalent Surcharge"

# SDCP "Understanding your bill" specimen, pages 2-3 (retrieved 2026-10-01).
PS, PE = date(2026, 2, 12), date(2026, 3, 13)
KWH = {"on_peak": 73, "off_peak": 115, "super_off_peak": 63}


@pytest.fixture(scope="module")
def specs():
    return {
        "delivery": load_spec_versions("TOU-DR1", Layer.DELIVERY),
        "sdcp": load_spec_versions("TOU-DR1", Layer.GENERATION, provider="SDCP-2021V"),
        "eecc": load_spec_versions("TOU-DR1", Layer.GENERATION, provider="SDG&E"),
    }


def _bill(specs, **kw):
    kw.setdefault("service", Service.CCA)
    kw.setdefault("territory", "coastal_basic")
    kw.setdefault("vintage", "2021")
    kw.setdefault("imputed_generation", specs["eecc"])
    return compute_bill_from_usage(
        [UsageSegment(start=PS, end=PE, kwh=KWH)],
        [specs["delivery"], specs["sdcp"]],
        PS,
        PE,
        **kw,
    )


# --- the specimen: what it pins, and what it deliberately does not ------------------


def test_the_differential_base_is_delivery_less_pcia_and_wildfire_exactly(specs):
    """Printed: 82.01 x 5.78% = 4.74. 82.01 = 92.42 electric charges - 8.93 PCIA - 1.48 WF.

    The WF-NBC is folded into our energy rate (0.34692 = UDC 0.34101 + 0.00591), so the base
    only lands on 82.01 if it is carved back out as kWh x rate. Pinned to the cent because the
    specimen pins it to the cent. Our base is 82.04, and both cents of the gap are named:
    +0.01 is the Economic Development Program Credit we do not model, +0.02 is SDG&E
    rounding delivery and WF as two lines (85.59 + 1.48) where we round one (87.09).
    """
    d = _bill(specs, jurisdiction="city_of_san_diego").layers[0].bucket()
    assert d[FFD] == 4.74
    base = sum(v for k, v in d.items() if k not in (FFD, FFES))
    base -= d["Power Charge Indifference Adjustment (vintaged)"] + round(251 * 0.00591, 2)
    edp_credit, two_line_rounding = 0.01, 0.02
    assert base == pytest.approx(82.01 + edp_credit + two_line_rounding, abs=1e-9)


def test_the_equivalent_surcharge_is_on_imputed_eecc_and_misses_the_specimen_by_7_cents(specs):
    """Schedule CCA: a franchise fee on the EECC SDG&E imputes to a CCA customer.

    The imputed EECC is printed on the specimen as its own line (48.76), and 6.88% of it is
    3.35. The specimen prints 3.42 on a base of 49.71. That 0.95 is UNEXPLAINED and is
    pinned here as a known gap, not fitted: if a real statement explains it, this test is
    the one to change, on purpose.
    """
    bill = _bill(specs, jurisdiction="city_of_san_diego")
    line = next(li for li in bill.layers[0].line_items if li.name == FFES)
    assert line.quantity == 48.76  # the imputed EECC — equal to the printed generation line
    assert line.amount == 3.35
    assert round(3.42 - line.amount, 2) == 0.07
    # A surcharge, so NBT SC 2.d keeps every export credit off it.
    assert line.volumetric is False


def test_the_cca_collects_the_cec_surcharge(specs):
    """Printed "State Surcharge Tax" .08 on the SDCP side = 251 x $0.0003 (CDTFA L-1020)."""
    g = _bill(specs, jurisdiction="city_of_san_diego").layers[1].bucket()
    assert g["Energy Commission Tax"] == 0.08


def test_with_the_three_unmodelled_lines_observed_the_specimen_lands_within_10_cents(specs):
    """137.97 modelled + State Regulatory Fee 0.25 + Power100 2.50 + EDP credit -0.01 = 140.71,
    against 140.64 printed. The +0.07 is the FFES base gap above. NOT a reconciliation —
    the specimen's own SDCP lines are 0.12 off kWh x rate — but it says nothing is missing.
    """
    bill = _bill(specs, jurisdiction="city_of_san_diego")
    assert bill.total == 137.97
    assert round(bill.total + 0.25 + 2.50 - 0.01 - 140.64, 2) == 0.07


# --- jurisdiction is a customer fact: refused, never defaulted ---------------------------


def test_a_missing_jurisdiction_is_refused(specs):
    with pytest.raises(MissingJurisdictionError, match="no default"):
        _bill(specs)


def test_an_unknown_jurisdiction_is_refused(specs):
    with pytest.raises(ValueError, match="chula_vista"):
        _bill(specs, jurisdiction="chula_vista")


def test_outside_the_city_there_is_no_differential_and_the_cca_pays_1_1_percent(specs):
    d = _bill(specs, jurisdiction="other").layers[0].bucket()
    assert FFD not in d  # a fee the city does not levy is not a $0.00 line
    assert d[FFES] == round(48.76 * 0.011, 2)


def test_a_cca_bill_without_the_imputed_generation_is_refused(specs):
    with pytest.raises(MissingImputedGenerationError, match=FFES):
        _bill(specs, jurisdiction="other", imputed_generation=None)


# --- the unverified branches raise instead of guessing ---------------------------------


def test_a_bundled_city_customer_is_refused_because_the_base_is_unsettled(specs):
    """Does a bundled bill's EECC sit inside the 5.78% base? The CCA specimen cannot say:
    its EECC line and the matching credit net to zero inside the base either way."""
    with pytest.raises(UnverifiedChargeError, match=FFD):
        compute_bill_from_usage(
            [UsageSegment(start=PS, end=PE, kwh=KWH)],
            [specs["delivery"], specs["eecc"]],
            PS,
            PE,
            service=Service.BUNDLED,
            territory="coastal_basic",
            jurisdiction="city_of_san_diego",
        )


def test_a_bundled_customer_outside_the_city_bills_no_franchise_line(specs):
    bill = compute_bill_from_usage(
        [UsageSegment(start=PS, end=PE, kwh=KWH)],
        [specs["delivery"], specs["eecc"]],
        PS,
        PE,
        service=Service.BUNDLED,
        territory="coastal_basic",
        jurisdiction="other",
    )
    assert not {FFD, FFES} & set(bill.layers[0].bucket())


@pytest.mark.parametrize("jurisdiction", ["city_of_san_diego", "other"])
def test_care_on_a_cca_is_refused(specs, jurisdiction):
    """Is EECC imputed at the CARE or the standard rate? Open decision 9 territory."""
    with pytest.raises(UnverifiedChargeError):
        _bill(specs, jurisdiction=jurisdiction, care=True)


# --- the schema refuses malformed fee definitions --------------------------------------


def test_an_exclusion_that_names_nothing_is_a_spec_error(specs):
    spec = specs["delivery"][0]
    bad = spec.surcharges[0].model_copy(update={"exclude": ["Wildfire Fnd / DWR Bond"]})
    broken = spec.model_copy(update={"surcharges": [bad, *spec.surcharges[1:]]})
    with pytest.raises(ValueError, match="Wildfire Fnd"):
        compute_bill_from_usage(
            [UsageSegment(start=PS, end=PE, kwh=KWH)],
            [[broken], specs["sdcp"]],
            PS,
            PE,
            service=Service.CCA,
            territory="coastal_basic",
            vintage="2021",
            jurisdiction="city_of_san_diego",
            imputed_generation=specs["eecc"],
        )


def test_imputed_provider_comes_with_imputed_generation_and_only_with_it():
    with pytest.raises(ValueError, match="imputed_provider"):
        Surcharge(name="x", rate=0.01, of="imputed_generation", citation="c")
    with pytest.raises(ValueError, match="imputed_provider"):
        Surcharge(name="x", rate=0.01, of="pretax", imputed_provider="SDG&E", citation="c")


def test_every_tou_dr1_vintage_carries_the_same_franchise_fees(specs):
    """A bill-level line cannot be split at a rate change, so it must not differ by vintage
    — the engine raises if it does; this catches the edit before a bill does."""
    first = specs["delivery"][0].surcharges
    assert [s.name for s in first] == [FFD, FFES]
    for v in specs["delivery"][1:]:
        assert v.surcharges == first, v.effective_date
