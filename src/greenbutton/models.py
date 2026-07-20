"""Canonical interval-series model shared across the engine.

The tariff engine is a pure function of an :class:`IntervalSeries` (plus a tariff
spec and a billing period). Everything utility-specific — CSV quirks, DST, PII —
is resolved here at the parse boundary so downstream code sees one clean shape.

Privacy invariant (CLAUDE.md): no personally identifying data enters the canonical
model. Parsers strip names/addresses and keep only a masked account tail.
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

LOCAL_TZ = "America/Los_Angeles"

# Canonical columns of the interval frame.
COL_KWH = "kwh"
COL_ESTIMATED = "estimated"


class Utility(StrEnum):
    PGE = "PG&E"
    SDGE = "SDG&E"


class Direction(StrEnum):
    """Which way energy flows across the meter for a series.

    M0 is import-only (grid usage). Export is modeled here so the NEM 3.0 milestone
    can add an export series without reshaping the type.
    """

    IMPORT = "import"  # energy drawn from the grid (billed usage)
    EXPORT = "export"  # energy pushed to the grid (NEM credit) — future


class MeterMeta(BaseModel):
    """Non-identifying provenance for an interval series."""

    model_config = ConfigDict(frozen=True)

    utility: Utility
    service_id: str | None = None
    account_tail: str | None = Field(
        default=None, description="Last 4 of the account number; full number never stored."
    )
    address_zip: str | None = Field(
        default=None, description="ZIP only — kept for climate zone / tariff eligibility."
    )
    source_file: str | None = None


class IntervalSeries(BaseModel):
    """A gap-explicit, tz-aware series of metered energy per fixed interval.

    ``frame`` is a pandas DataFrame indexed by the tz-aware **interval start**
    (``America/Los_Angeles``), with at least a ``kwh`` column and an ``estimated``
    boolean column. Only *present* readings are rows; missing intervals are absent
    and enumerated by :meth:`gaps`, never silently zero-filled.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    utility: Utility
    direction: Direction = Direction.IMPORT
    interval: timedelta
    unit: str = "kWh"
    meta: MeterMeta
    frame: pd.DataFrame

    @model_validator(mode="after")
    def _validate_frame(self) -> IntervalSeries:
        f = self.frame
        idx = f.index

        if not isinstance(idx, pd.DatetimeIndex):
            raise ValueError("frame index must be a DatetimeIndex")
        if idx.tz is None or str(idx.tz) != LOCAL_TZ:
            raise ValueError(f"frame index must be tz-aware in {LOCAL_TZ}, got tz={idx.tz}")
        if not idx.is_monotonic_increasing:
            raise ValueError("frame index must be sorted ascending by interval start")
        if not idx.is_unique:
            dupes = idx[idx.duplicated()][:3].tolist()
            raise ValueError(f"frame index has duplicate timestamps, e.g. {dupes}")
        if COL_KWH not in f.columns:
            raise ValueError(f"frame must have a {COL_KWH!r} column")
        if COL_ESTIMATED not in f.columns:
            raise ValueError(f"frame must have an {COL_ESTIMATED!r} column")

        kwh = f[COL_KWH]
        if kwh.isna().any():
            raise ValueError("kwh column contains NaN")
        # Import usage is non-negative. A negative value means an export leaked into an
        # import series (or a sign/units bug) — surface it rather than bill it.
        if self.direction is Direction.IMPORT and (kwh < 0).any():
            n = int((kwh < 0).sum())
            raise ValueError(f"import series has {n} negative kwh value(s)")

        return self

    # -- convenience ---------------------------------------------------------

    @property
    def start(self) -> pd.Timestamp:
        return self.frame.index[0]

    @property
    def end(self) -> pd.Timestamp:
        """Exclusive end: start of the last interval + one interval length."""
        return self.frame.index[-1] + self.interval

    @property
    def total_kwh(self) -> float:
        return float(self.frame[COL_KWH].sum())

    def expected_index(self) -> pd.DatetimeIndex:
        """The complete grid of interval starts from first to last, DST-correct.

        Built in local wall-clock time so ``date_range`` naturally drops the
        spring-forward hour and repeats the fall-back hour.
        """
        return pd.date_range(
            start=self.frame.index[0],
            end=self.frame.index[-1],
            freq=self.interval,
            tz=LOCAL_TZ,
        )

    def gaps(self) -> pd.DatetimeIndex:
        """Interval starts that *should* exist within [start, last] but are missing."""
        return self.expected_index().difference(self.frame.index)

    def coverage(self) -> float:
        """Fraction of expected intervals that are present (1.0 == no gaps)."""
        expected = len(self.expected_index())
        return len(self.frame) / expected if expected else 1.0


class ParseReport(BaseModel):
    """What the parser observed — the artifact tests and humans inspect.

    Separate from the data so DST/gap/estimated facts are asserted explicitly
    rather than reverse-engineered from the frame.
    """

    model_config = ConfigDict(frozen=True)

    utility: Utility
    interval_minutes: int
    n_intervals: int
    n_estimated: int
    n_gaps: int
    coverage: float
    first_start: str
    last_start: str
    total_kwh: float
    dst_fall_back_days: list[str] = Field(default_factory=list)
    dst_spring_forward_days: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
