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
