"""PVWatts v8 hourly production — real NREL API, cached to disk, never fabricated.

PVWatts is a physical model of a PV system's output given location, tilt, azimuth and
system size. Modeling *production* this way is exactly what M3 asks for and does not
violate invariant 6, which forbids modeling the customer's *load* — production has no
metered alternative, load does (and stays the customer's real intervals throughout).

What this module will not do is invent PVWatts numbers. A response is either fetched live
from NREL (needs a free developer key in ``NREL_API_KEY``) and cached, or read back from a
cache written by an earlier real fetch. With neither, :func:`hourly_production` raises with
the sign-up URL rather than returning a plausible-looking array — a fabricated production
profile would poison every payback figure downstream.

The cache key is the full request (lat/lon rounded, system params), so a given system is
fetched once and thereafter reproduces byte-for-byte offline, which also keeps tests
deterministic and network-free.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from greenbutton.models import LOCAL_TZ

CACHE_DIR = Path(__file__).parent / "pvwatts_cache"
PVWATTS_URL = "https://developer.nrel.gov/api/pvwatts/v8.json"
SIGNUP_URL = "https://developer.nrel.gov/signup/"

# PVWatts hourly output is a full non-leap year, local standard time, hour-beginning.
HOURS_PER_YEAR = 8760


@dataclass(frozen=True)
class SystemSpec:
    """A PV system as PVWatts parameters. Defaults are PVWatts' own residential defaults."""

    lat: float
    lon: float
    system_capacity_kw: float  # DC nameplate
    tilt: float  # degrees from horizontal
    azimuth: float  # degrees clockwise from north; 180 = south-facing
    array_type: int = 1  # 0 fixed open rack, 1 fixed roof mount, 2/3/4 tracking
    module_type: int = 0  # 0 standard, 1 premium, 2 thin film
    losses: float = 14.08  # system loss %, PVWatts default
    dc_ac_ratio: float = 1.2
    inv_eff: float = 96.0
    gcr: float = 0.4

    def cache_key(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class ProductionResult:
    """Hourly AC production plus the provenance that makes it citable."""

    spec: SystemSpec
    ac_kwh: np.ndarray  # 8760 hourly kWh, local standard time
    station_info: dict
    source: str  # "nrel-api" | "cache"
    fetched_at: str

    @property
    def annual_kwh(self) -> float:
        return float(self.ac_kwh.sum())

    def to_series(self, year: int) -> pd.Series:
        """Map the 8760 hourly values onto a tz-aware local index for ``year``.

        PVWatts returns a generic non-leap year in local *standard* time. Aligning it to
        real wall-clock timestamps means the calendar's own weekday/weekend pattern and
        DST apply — the model provides the shape, the calendar provides the labels.
        """
        idx = pd.date_range(f"{year}-01-01", periods=HOURS_PER_YEAR, freq="h")
        s = pd.Series(self.ac_kwh, index=idx)
        # Localize wall-clock; a leap year simply leaves Dec 31 short, which is immaterial
        # for annual production and keeps every hour on a real local timestamp.
        local = s.tz_localize(LOCAL_TZ, nonexistent="shift_forward", ambiguous="NaT")
        return local[local.index.notna()]


def _cache_path(spec: SystemSpec, cache_dir: Path) -> Path:
    return cache_dir / f"pvwatts_{spec.cache_key()}.json"


def _load_cache(spec: SystemSpec, cache_dir: Path) -> ProductionResult | None:
    path = _cache_path(spec, cache_dir)
    if not path.exists():
        return None
    blob = json.loads(path.read_text())
    return ProductionResult(
        spec=spec,
        ac_kwh=np.asarray(blob["ac_kwh"], dtype=float),
        station_info=blob.get("station_info", {}),
        source="cache",
        fetched_at=blob.get("fetched_at", "unknown"),
    )


def _save_cache(result: ProductionResult, cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(result.spec, cache_dir).write_text(
        json.dumps(
            {
                "spec": asdict(result.spec),
                "ac_kwh": [round(float(x), 6) for x in result.ac_kwh],
                "station_info": result.station_info,
                "source": "nrel-api",
                "fetched_at": result.fetched_at,
            }
        )
    )


def _fetch(spec: SystemSpec, api_key: str) -> ProductionResult:
    import requests  # local import so the module loads without the dep in offline use

    params = {
        "api_key": api_key,
        "lat": spec.lat,
        "lon": spec.lon,
        "system_capacity": spec.system_capacity_kw,
        "azimuth": spec.azimuth,
        "tilt": spec.tilt,
        "array_type": spec.array_type,
        "module_type": spec.module_type,
        "losses": spec.losses,
        "dc_ac_ratio": spec.dc_ac_ratio,
        "inv_eff": spec.inv_eff,
        "gcr": spec.gcr,
        "timeframe": "hourly",
    }
    resp = requests.get(PVWATTS_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"PVWatts API error: {data['errors']}")
    ac_wh = np.asarray(data["outputs"]["ac"], dtype=float)  # watt-hours per hour
    if len(ac_wh) != HOURS_PER_YEAR:
        raise RuntimeError(f"PVWatts returned {len(ac_wh)} hours, expected {HOURS_PER_YEAR}")
    return ProductionResult(
        spec=spec,
        ac_kwh=ac_wh / 1000.0,
        station_info=data.get("station_info", {}),
        source="nrel-api",
        fetched_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )


def hourly_production(
    spec: SystemSpec,
    *,
    api_key: str | None = None,
    cache_dir: str | Path = CACHE_DIR,
    allow_fetch: bool = True,
) -> ProductionResult:
    """Hourly AC production for ``spec`` — from cache, else a live NREL fetch.

    Resolution order: cache hit; then, if ``allow_fetch`` and a key is available
    (argument or ``NREL_API_KEY``), a live fetch that is cached for next time. With
    neither, raises — it never returns a modeled array dressed up as PVWatts output.
    """
    cache_dir = Path(cache_dir)
    cached = _load_cache(spec, cache_dir)
    if cached is not None:
        return cached

    key = api_key or os.environ.get("NREL_API_KEY")
    if not allow_fetch or not key:
        raise RuntimeError(
            f"no cached PVWatts result for this system and "
            f"{'fetching disabled' if not allow_fetch else 'no NREL_API_KEY set'}. "
            f"Get a free key at {SIGNUP_URL} and set NREL_API_KEY, or import a cached "
            f"response into {cache_dir}. Refusing to fabricate a production profile."
        )
    result = _fetch(spec, key)
    _save_cache(result, cache_dir)
    return result
