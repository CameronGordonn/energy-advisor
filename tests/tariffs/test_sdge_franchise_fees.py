"""SDG&E's city-dependent franchise fees and the CCA's CEC surcharge (sessions 31-32).

The lines were found missing by pricing SDCP's published specimen statement
(``dev/notes/sdcp_specimen_bill_2026-10.md``): every rate on it matched the specs to the fifth
decimal and the bill still came out ~$11 short. The specimen is NOT a golden bill — its
account number is a placeholder and its own SDCP lines do not equal kWh x rate — so it is
used here the way ``tests/published_impacts/`` uses rate alerts: to pin the *structure*
of three lines whose arithmetic it shows, never to count toward the ±$2 claim.
"""

from __future__ import annotations

from datetime import date

import pytest

from tariffs.bill import MissingImputedGenerationError
from tariffs.bucketed import UsageSegment, compute_bill_from_usage, compute_layer_from_usage
from tariffs.loader import SPECS_DIR, load_spec_file, load_spec_versions
from tariffs.schema import (
    Layer,
    MissingJurisdictionError,
    Service,
    Surcharge,
    UnverifiedChargeError,
)

FFD = "City of San Diego Franchise Fee Differential"
FFD_GEN = "City of San Diego Franchise Fee Differential (generation)"
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


def _bundled(specs, **kw):
    kw.setdefault("territory", "coastal_basic")
    return compute_bill_from_usage(
        [UsageSegment(start=PS, end=PE, kwh=KWH)],
        [specs["delivery"], specs["eecc"]],
        PS,
        PE,
        service=Service.BUNDLED,
        **kw,
    )


def test_a_bundled_city_customer_pays_the_differential_on_delivery_and_on_generation(specs):
    """Settled session 32 by Schedule EECC's own clause (Sheet 30030-E): 5.78% of "the total
    bills calculated under this schedule". So a bundled household in the city pays it twice
    over, once per schedule — TOU-DR1's on delivery (less the Wildfire Fund charge, as on
    the specimen) and EECC's on generation. Session 31 refused this case because the
    delivery sheet alone could not say whether generation was in the base."""
    bill = _bundled(specs, jurisdiction="city_of_san_diego")
    d, g = bill.layers[0].bucket(), bill.layers[1].bucket()
    delivery_base = sum(v for k, v in d.items() if k != FFD) - 251 * 0.00591
    assert d[FFD] == pytest.approx(0.0578 * delivery_base, abs=0.005)
    assert g[FFD_GEN] == pytest.approx(
        0.0578 * sum(v for k, v in g.items() if k != FFD_GEN), abs=0.005
    )
    assert FFES not in d  # a CCA-only line


def test_the_generation_differential_stays_out_of_the_imputed_base(specs):
    """Schedule CCA imputes EECC's charges; EECC's differential is a fee on them. The bundled
    EECC layer less its own differential IS the imputed base — 48.76, the specimen's
    printed generation line — and the CCA customer never sees the bundled line at all."""
    eecc = _bundled(specs, jurisdiction="city_of_san_diego").layers[1]
    assert round(eecc.total - eecc.bucket()[FFD_GEN], 2) == 48.76
    cca = _bill(specs, jurisdiction="city_of_san_diego")
    assert FFD_GEN not in cca.layers[1].bucket()
    assert next(li for li in cca.layers[0].line_items if li.name == FFES).quantity == 48.76


def test_the_cca_surcharge_and_the_bundled_differential_are_the_same_fee(specs):
    """A cross-check between two sheets that were read separately: a CCA customer pays 6.88%
    of imputed EECC in the city and 1.1% outside it, and the 5.78-point difference is
    exactly the differential EECC charges a bundled customer."""
    ffes = next(x for x in specs["delivery"][-1].surcharges if x.name == FFES)
    gen = next(x for x in specs["eecc"][-1].surcharges if x.name == FFD_GEN)
    in_city = ffes.rate_by_jurisdiction["city_of_san_diego"]
    outside = ffes.rate_by_jurisdiction["other"]
    assert in_city - outside == pytest.approx(gen.rate_by_jurisdiction["city_of_san_diego"])


def test_a_bundled_care_customer_in_the_city_is_refused(specs):
    """Before or after the CARE discount? Schedule E-CARE says nothing about franchise fees."""
    with pytest.raises(UnverifiedChargeError, match=FFD):
        _bundled(specs, jurisdiction="city_of_san_diego", care=True)


# --- every SDG&E schedule, not just TOU-DR1 -------------------------------------------
# Session 31 built these lines on TOU-DR1 only, which left TOU-DR2, EV-TOU-5 and TOU-DR-P
# billing a City of San Diego household with no differential AND no refusal. These tests
# make that class of gap impossible to reintroduce with a new schedule or vintage.

SDGE_SPECS = sorted(SPECS_DIR.glob("sdge_*.yaml"))


@pytest.mark.parametrize("path", SDGE_SPECS, ids=lambda p: p.stem)
def test_every_sdge_spec_carries_the_city_differential(path):
    spec = load_spec_file(path)
    want = FFD if spec.layer is Layer.DELIVERY else FFD_GEN
    sur = next((x for x in spec.surcharges if x.name == want), None)
    assert sur is not None, f"{path.name} bills a City of San Diego household without {want}"
    assert sur.rate_by_jurisdiction == {"city_of_san_diego": 0.0578, "other": 0.0}
    if spec.layer is Layer.GENERATION:
        assert sur.applies_to.value == "bundled"  # Schedule EECC is bundled service


AUG, AUG_END = date(2026, 8, 1), date(2026, 8, 31)


def _sdge(schedule, kwh, service=Service.BUNDLED, **kw):
    return compute_bill_from_usage(
        [UsageSegment(start=AUG, end=AUG_END, kwh=kwh)],
        [
            load_spec_versions(schedule, Layer.DELIVERY),
            load_spec_versions(schedule, Layer.GENERATION, provider="SDG&E"),
        ],
        AUG,
        AUG_END,
        service=service,
        territory="coastal_basic",
        **kw,
    )


def test_tou_dr2_bills_both_lines_in_the_city():
    """Schedule TOU-DR2 Sheet 29959-E prints TOU-DR1's clause word for word."""
    bill = _sdge("TOU-DR2", {"on_peak": 80, "off_peak": 300}, jurisdiction="city_of_san_diego")
    assert FFD in bill.layers[0].bucket()
    assert FFD_GEN in bill.layers[1].bucket()


def test_tou_dr_p_delivery_bills_the_differential_in_the_city():
    """TOU-DR-P's delivery is Schedule TOU-DR (Sheet 29915-E). Its generation carries an
    event adder the bill-only path refuses, so only the delivery layer is billed here; the
    generation line's presence is pinned by the every-spec test above."""
    layer = compute_layer_from_usage(
        [
            UsageSegment(
                start=AUG, end=AUG_END, kwh={"on_peak": 80, "off_peak": 200, "super_off_peak": 100}
            )
        ],
        load_spec_versions("TOU-DR-P", Layer.DELIVERY),
        AUG,
        AUG_END,
        service=Service.BUNDLED,
        territory="coastal_basic",
        jurisdiction="city_of_san_diego",
    )
    assert FFD in layer.bucket()


EV_KWH = {"on_peak": 80, "off_peak": 200, "super_off_peak": 300}


def test_ev_tou_5_in_the_city_is_refused_until_its_own_sheet_is_read():
    """The EV-TOU-5 schedule sheet was not found; every other sheet's clause is analogy, and
    analogy is not a citation. Refuse in the city rather than bill without the fee."""
    with pytest.raises(UnverifiedChargeError, match="NOT VERIFIED"):
        _sdge("EV-TOU-5", EV_KWH, jurisdiction="city_of_san_diego")


def test_ev_tou_5_outside_the_city_still_bills():
    bill = _sdge("EV-TOU-5", EV_KWH, jurisdiction="other")
    assert FFD not in bill.layers[0].bucket() and bill.total > 0


def test_a_cca_customer_on_tou_dr2_in_the_city_is_refused():
    """The CCA base excludes the PCIA, and these specs carry none to exclude."""
    with pytest.raises(UnverifiedChargeError, match=FFD):
        compute_layer_from_usage(
            [UsageSegment(start=AUG, end=AUG_END, kwh={"on_peak": 80, "off_peak": 300})],
            load_spec_versions("TOU-DR2", Layer.DELIVERY),
            AUG,
            AUG_END,
            service=Service.CCA,
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
