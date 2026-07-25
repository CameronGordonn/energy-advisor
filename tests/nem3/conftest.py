"""Synthetic interval fixtures for the NEM 3.0 tests.

No real household has export data (Cameron has no solar; dad's SDG&E data is unavailable),
so these tests exercise the engine on deterministic synthetic load/production. The ACC
tables under test are the *real* committed SDG&E vintage files — only the load and
production shapes are synthetic, which is the opposite of the invariant-6 concern (that
forbids modeling the customer's load in a real analysis, not in a unit test).
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from greenbutton.models import (
    COL_ESTIMATED,
    COL_KWH,
    Direction,
    IntervalSeries,
    MeterMeta,
    Utility,
)
from nem3.pvwatts import ProductionResult, SystemSpec

YEAR = 2026


def _series(kwh: np.ndarray, index: pd.DatetimeIndex, direction: Direction) -> IntervalSeries:
    return IntervalSeries(
        utility=Utility.SDGE,
        direction=direction,
        interval=timedelta(hours=1),
        meta=MeterMeta(utility=Utility.SDGE),
        frame=pd.DataFrame({COL_KWH: kwh, COL_ESTIMATED: False}, index=index),
    )


@pytest.fixture
def year_index() -> pd.DatetimeIndex:
    return pd.date_range(f"{YEAR}-01-01", periods=8760, freq="h", tz="America/Los_Angeles")


@pytest.fixture
def load_series(year_index: pd.DatetimeIndex) -> IntervalSeries:
    """Evening-peaked residential load, ~3850 kWh/yr."""
    h = year_index.hour.values
    kwh = 0.3 + 0.5 * np.exp(-((h - 19) ** 2) / 8) + 0.2 * np.exp(-((h - 8) ** 2) / 6)
    return _series(kwh, year_index, Direction.IMPORT)


@pytest.fixture
def production(year_index: pd.DatetimeIndex) -> pd.Series:
    """A ~4 kW south array via a synthetic bell curve (not a PVWatts fetch)."""
    h = year_index.hour.values
    ac = (
        np.maximum(0, 4 * np.sin(np.pi * (h - 6) / 12))
        * np.where((h >= 6) & (h <= 18), 1, 0)
        * 0.55
    )
    result = ProductionResult(
        spec=SystemSpec(32.7, -117.1, 4, 20, 180),
        ac_kwh=ac,
        station_info={},
        source="synthetic-test",
        fetched_at="test",
    )
    return result.to_series(YEAR)


@pytest.fixture
def monthly_periods() -> list[tuple]:
    from datetime import date
    from datetime import timedelta as td

    out = []
    d = date(YEAR, 1, 1)
    while d <= date(YEAR, 12, 31):
        e = date(YEAR, 12, 31) if d.month == 12 else date(YEAR, d.month + 1, 1) - td(days=1)
        out.append((d, e))
        d = e + td(days=1)
    return out
