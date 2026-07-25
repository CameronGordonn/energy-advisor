"""PVWatts client: cache round-trip and the never-fabricate guard."""

from __future__ import annotations

import numpy as np
import pytest

from nem3.pvwatts import ProductionResult, SystemSpec, hourly_production


def test_refuses_to_fabricate_without_key_or_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("NREL_API_KEY", raising=False)
    spec = SystemSpec(32.7, -117.1, 5.0, 20, 180)
    with pytest.raises(RuntimeError, match="Refusing to fabricate"):
        hourly_production(spec, cache_dir=tmp_path, allow_fetch=True)


def test_allow_fetch_false_never_touches_network(tmp_path):
    spec = SystemSpec(32.7, -117.1, 5.0, 20, 180)
    with pytest.raises(RuntimeError, match="fetching disabled"):
        hourly_production(spec, cache_dir=tmp_path, allow_fetch=False)


def test_cache_round_trip(tmp_path):
    from nem3.pvwatts import _save_cache

    spec = SystemSpec(32.7, -117.1, 5.0, 20, 180)
    original = ProductionResult(
        spec=spec,
        ac_kwh=np.arange(8760, dtype=float),
        station_info={"city": "SAN DIEGO"},
        source="nrel-api",
        fetched_at="2026-07-25T00:00:00Z",
    )
    _save_cache(original, tmp_path)
    loaded = hourly_production(spec, cache_dir=tmp_path, allow_fetch=False)
    assert loaded.source == "cache"
    assert np.allclose(loaded.ac_kwh, original.ac_kwh)
    assert loaded.station_info["city"] == "SAN DIEGO"


def test_to_series_conserves_annual_energy():
    spec = SystemSpec(32.7, -117.1, 5.0, 20, 180)
    ac = np.ones(8760)
    result = ProductionResult(spec=spec, ac_kwh=ac, station_info={}, source="test", fetched_at="t")
    s = result.to_series(2026)
    # DST drops one spring-forward hour; annual total is otherwise preserved.
    assert 8758 <= s.sum() <= 8760
    assert str(s.index.tz) == "America/Los_Angeles"


def test_cache_key_is_stable_and_param_sensitive():
    a = SystemSpec(32.7, -117.1, 5.0, 20, 180)
    b = SystemSpec(32.7, -117.1, 5.0, 20, 180)
    c = SystemSpec(32.7, -117.1, 6.0, 20, 180)  # different capacity
    assert a.cache_key() == b.cache_key()
    assert a.cache_key() != c.cache_key()
