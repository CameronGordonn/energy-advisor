"""NBT settlement: the NBC import floor, per-component credits, CCA exclusion."""

from __future__ import annotations

from datetime import date

import pytest

from greenbutton.models import Utility
from nem3.acc import ExportRateSchedule, Vintage
from nem3.netting import NbtSettings, settle_year
from nem3.solar import split_meter
from tariffs.loader import load_spec_versions
from tariffs.schema import Layer, Service


@pytest.fixture
def schedule():
    return ExportRateSchedule("SDG&E", Vintage(application_year=2026, pto_date=date(2026, 6, 1)))


@pytest.fixture
def delivery():
    return load_spec_versions("TOU-DR1", Layer.DELIVERY)


def _settle(load, production, delivery, schedule, periods, **kw):
    imp, exp = split_meter(load, production, utility=Utility.SDGE)
    settings = NbtSettings(
        service=kw.pop("service", Service.BUNDLED),
        territory="coastal_basic",
        # The delivery spec carries a vintaged PCIA, which a CCA customer pays and a
        # bundled one does not. Supplying it is mandatory for CCA service (the biller
        # refuses to guess a vintage), and harmless for bundled.
        vintage=kw.pop("vintage", "2018"),
        acc_plus_eligible=False,
        **kw,
    )
    # Generation layer is not authored for SDG&E yet; reuse delivery so the mechanics are
    # exercised. Dollar magnitudes are not asserted, only structural invariants.
    return settle_year(
        imp,
        exp,
        delivery,
        delivery,
        schedule,
        periods,
        settings=settings,
        allow_before_effective=True,
    )


def test_nbc_floor_is_positive_and_reported(
    load_series, production, delivery, schedule, monthly_periods
):
    year = _settle(load_series, production, delivery, schedule, monthly_periods)
    # The whole point of invariant 4: exports cannot erase the non-bypassable charges.
    assert year.nbc_floor > 0
    # Every period's amount due is at least its own NBC floor (credits can't go below it).
    for p in year.periods:
        assert p.amount_due >= p.nbc_floor - 0.01


def test_credits_never_drive_a_period_negative(
    load_series, production, delivery, schedule, monthly_periods
):
    year = _settle(load_series, production, delivery, schedule, monthly_periods)
    for p in year.periods:
        assert p.amount_due >= -0.01, f"{p.period_start} went negative: {p.amount_due}"


def test_protected_plus_offsettable_equals_total(
    load_series, production, delivery, schedule, monthly_periods
):
    year = _settle(load_series, production, delivery, schedule, monthly_periods)
    for p in year.periods:
        for ls in p.layers:
            assert ls.offsettable + ls.protected == pytest.approx(ls.total, abs=0.02)


def test_cca_generation_credit_excluded_by_default(
    load_series, production, delivery, schedule, monthly_periods
):
    bundled = _settle(
        load_series, production, delivery, schedule, monthly_periods, service=Service.BUNDLED
    )
    cca = _settle(load_series, production, delivery, schedule, monthly_periods, service=Service.CCA)
    # A CCA customer's generation-component export credit is not the utility's to pay
    # (SC 2.a), so their bill cannot be lower than the bundled customer's on that account.
    assert cca.amount_due >= bundled.amount_due
    assert any("generation component" in n for n in cca.notes)


def test_more_export_never_increases_amount_due(
    load_series, production, delivery, schedule, monthly_periods
):
    no_solar = _settle(load_series, production * 0.0, delivery, schedule, monthly_periods)
    solar = _settle(load_series, production, delivery, schedule, monthly_periods)
    assert solar.amount_due <= no_solar.amount_due


def test_lock_in_note_names_the_vintage_and_year(
    load_series, production, delivery, schedule, monthly_periods
):
    year = _settle(load_series, production, delivery, schedule, monthly_periods)
    assert year.lock_in_through == date(2035, 6, 1)
    assert any("locked to the 2026 ACC vintage" in n for n in year.notes)
