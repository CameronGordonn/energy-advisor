"""Loader invariants: citation mandatory, UNVERIFIED raises, effective-date selection."""

from __future__ import annotations

from datetime import date

import pytest
import yaml

from tariffs.loader import UnverifiedSpecError, load_spec_file, load_specs
from tariffs.schema import Layer

MINIMAL = {
    "schedule_id": "TEST",
    "name": "Test schedule",
    "provider": "PG&E",
    "layer": "delivery",
    "effective_date": "2026-03-01",
    "citation": "Test tariff sheet",
    "seasons": {"summer_months": [6, 7, 8, 9], "winter_months": [1, 2, 3, 4, 5, 10, 11, 12]},
    "tou": {"peak_hours": [16, 17, 18, 19, 20]},
    "energy": {
        "summer_peak": {"standard": 0.5},
        "summer_offpeak": {"standard": 0.4},
        "winter_peak": {"standard": 0.4},
        "winter_offpeak": {"standard": 0.35},
    },
}


def _write(tmp_path, spec: dict, name="spec.yaml"):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(spec))
    return p


def test_loads_minimal(tmp_path):
    spec = load_spec_file(_write(tmp_path, MINIMAL))
    assert spec.schedule_id == "TEST"
    assert spec.layer is Layer.DELIVERY


def test_unverified_field_raises(tmp_path):
    bad = {**MINIMAL, "adders": [{"name": "PCIA", "per_kwh": "UNVERIFIED", "citation": "x"}]}
    with pytest.raises(UnverifiedSpecError, match="UNVERIFIED"):
        load_spec_file(_write(tmp_path, bad))


def test_missing_citation_raises(tmp_path):
    bad = {**MINIMAL, "citation": ""}
    with pytest.raises(ValueError, match="citation"):
        load_spec_file(_write(tmp_path, bad))


def test_citation_literally_unverified_raises(tmp_path):
    # caught by the UNVERIFIED scan before pydantic validation
    bad = {**MINIMAL, "citation": "UNVERIFIED"}
    with pytest.raises(UnverifiedSpecError, match="UNVERIFIED"):
        load_spec_file(_write(tmp_path, bad))


def test_effective_date_selection(tmp_path):
    old = {**MINIMAL, "effective_date": "2025-01-01", "name": "old"}
    new = {**MINIMAL, "effective_date": "2026-03-01", "name": "new"}
    _write(tmp_path, old, "a.yaml")
    _write(tmp_path, new, "b.yaml")

    assert load_specs("TEST", Layer.DELIVERY, on=date(2025, 6, 1), specs_dir=tmp_path).name == "old"
    assert load_specs("TEST", Layer.DELIVERY, on=date(2026, 6, 1), specs_dir=tmp_path).name == "new"
    with pytest.raises(ValueError, match="no delivery spec"):
        load_specs("TEST", Layer.DELIVERY, on=date(2024, 1, 1), specs_dir=tmp_path)


def test_unverified_spec_does_not_block_other_schedules(tmp_path):
    """An UNVERIFIED spec must fail only its OWN schedule.

    Regression: the loaders used to parse (and validate) every YAML in the directory in
    order to filter by schedule_id, so a single half-finished SDG&E spec made every PG&E
    lookup raise — including the golden-bill reconciliation. Filtering now happens on the
    raw keys, before the UNVERIFIED gate.
    """
    from tariffs.loader import load_spec_versions

    _write(tmp_path, MINIMAL, "good.yaml")
    blocked = {
        **MINIMAL,
        "schedule_id": "OTHER",
        "baseline": {
            "territory": "UNVERIFIED",
            "allowance_kwh_per_day_summer": "UNVERIFIED",
            "allowance_kwh_per_day_winter": "UNVERIFIED",
            "credit_per_kwh": {"standard": -0.1},
        },
    }
    _write(tmp_path, blocked, "blocked.yaml")

    assert load_specs("TEST", Layer.DELIVERY, on=date(2026, 6, 1), specs_dir=tmp_path).name
    assert len(load_spec_versions("TEST", Layer.DELIVERY, specs_dir=tmp_path)) == 1
    # ...but asking for the incomplete schedule still raises.
    with pytest.raises(UnverifiedSpecError, match="baseline"):
        load_specs("OTHER", Layer.DELIVERY, on=date(2026, 6, 1), specs_dir=tmp_path)


def test_shipped_specs_either_load_or_raise_with_a_clear_reason():
    """Every spec in the repo is either billable or explicitly incomplete — never silent."""
    from tariffs.loader import SPECS_DIR, load_spec_file

    loaded, blocked = [], {}
    for p in sorted(SPECS_DIR.glob("*.yaml")):
        try:
            loaded.append(load_spec_file(p).schedule_id)
        except UnverifiedSpecError as e:
            blocked[p.name] = str(e)
    assert loaded, "no spec loads at all"
    for name, msg in blocked.items():
        assert "UNVERIFIED field(s)" in msg and "before this spec can bill" in msg, name


def test_sdge_specs_use_sdge_seasons_and_130_percent_baseline():
    """SDG&E's structural differences from PG&E must actually be in the specs."""
    from tariffs.loader import SPECS_DIR

    spec = load_spec_file(SPECS_DIR / "sdge_ev_tou_5_delivery_2026-06-01.yaml")
    assert spec.seasons.summer_months == [6, 7, 8, 9, 10]  # EECC: Jun 1 - Oct 31, not Jun-Sep
    assert spec.tou.periods == ["on_peak", "super_off_peak", "off_peak"]
    assert spec.tou.holiday_calendar == "sdge_residential"
    assert spec.minimum_bill is not None
    assert spec.minimum_bill.per_day.standard == 0.329
    assert spec.minimum_bill.per_day.care == 0.164
    assert spec.baseline is None  # EV-TOU-5 has no baseline credit


def test_sdge_and_pge_holiday_calendars_differ_on_saturday_holidays():
    """Independence Day 2026 falls on a Saturday: PG&E observes Fri 7/3, SDG&E keeps 7/4."""
    from tariffs.holidays import holiday_dates

    pge, sdge = holiday_dates("pge_residential", 2026), holiday_dates("sdge_residential", 2026)
    assert date(2026, 7, 3) in pge and date(2026, 7, 4) not in pge
    assert date(2026, 7, 4) in sdge and date(2026, 7, 3) not in sdge
    assert len(pge) == len(sdge) == 8
