"""Shared primitives for Green Button interval parsers (PG&E, SDG&E, ...).

Both IOUs export via the same Opower "Download My Data" platform, so the file
skeleton (``Name``/``Address``/``Account Number`` metadata rows, then a
``TYPE,DATE,START TIME,END TIME,...`` interval table) and *all* the timezone / DST /
gap / PII handling are identical. Only per-cell details differ between utilities —
SDG&E writes ``M/D/YYYY`` dates and can split usage into ``IMPORT``/``EXPORT``
columns — and those differences live in the per-utility modules. Everything a parser
would otherwise duplicate lives here, so there is one source of truth for the tricky
parts (interval inference, DST folding, the canonical assembly).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from .models import (
    COL_ESTIMATED,
    COL_KWH,
    LOCAL_TZ,
    IntervalSeries,
    MeterMeta,
    ParseReport,
    Utility,
)

# Minutes-in-a-day, for wrap-around interval arithmetic (the 23:45->00:00 row).
_DAY_MINUTES = 24 * 60


class GreenButtonParseError(ValueError):
    """Base for parse failures. Subclasses give actionable, specific messages."""


class BillingSummaryError(GreenButtonParseError):
    """Raised when handed the billing-history export instead of interval data."""


class AmbiguousDSTError(GreenButtonParseError):
    """Raised when the fall-back hour cannot be resolved from row order."""


def decode(path: Path) -> list[str]:
    # utf-8-sig transparently strips the BOM the portal prepends.
    return path.read_text(encoding="utf-8-sig").splitlines()


def split_header_and_table(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """Return (metadata dict, table lines). The table begins at the ``TYPE,`` row."""
    meta: dict[str, str] = {}
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("TYPE,"):
            return meta, lines[i:]
        if not line.strip():
            continue
        # metadata rows are "Key,Value"; use csv to respect quoted commas in Address.
        row = next(csv.reader([line]), [])
        if len(row) >= 2 and row[0]:
            meta[row[0].strip()] = row[1].strip()
    raise GreenButtonParseError(
        "no interval table found: expected a 'TYPE,DATE,START TIME,END TIME,...' header row"
    )


def mask_account(meta: dict[str, str]) -> str | None:
    acct = meta.get("Account Number") or meta.get("Account")
    if not acct:
        return None
    digits = "".join(ch for ch in acct if ch.isdigit())
    return digits[-4:] if len(digits) >= 4 else None


def zip_from_address(meta: dict[str, str]) -> str | None:
    addr = meta.get("Address")
    if not addr:
        return None
    # last token that starts with 5 digits (e.g. "900001234" -> "90000")
    for token in reversed(addr.replace(",", " ").split()):
        digits = "".join(ch for ch in token if ch.isdigit())
        if len(digits) >= 5:
            return digits[:5]
    return None


def to_minutes(s: pd.Series) -> pd.Series:
    """ "H:MM"/"HH:MM" -> minutes since midnight (handles SDG&E's unpadded hours)."""
    parts = s.str.split(":", expand=True).astype(int)
    return parts[0] * 60 + parts[1]


def interval_minutes(start_min: pd.Series, end_min: pd.Series, naive: pd.DatetimeIndex) -> int:
    """The file's declared interval in minutes, cross-checked two independent ways.

    The portal writes ``END TIME`` as the interval's *inclusive last minute*
    (``00:00``->``00:59`` is a 60-min interval; ``00:00``->``00:14`` is 15-min), so the
    per-row span is ``(END - START) mod 1440 + 1``. That is cross-checked against the
    modal gap between consecutive interval starts; the two must agree, which rejects both
    mixed-granularity files and any export that instead used an exclusive end.
    """
    span = ((end_min - start_min) % _DAY_MINUTES) + 1
    distinct_span = sorted(int(v) for v in span.unique())
    if len(distinct_span) != 1:
        raise GreenButtonParseError(
            f"inconsistent interval length across rows (minutes seen: {distinct_span}); "
            "file mixes granularities or is malformed"
        )
    interval = distinct_span[0]

    if len(naive) >= 2:
        steps = naive.to_series().diff().dropna().dt.total_seconds() / 60
        modal_step = int(steps.mode().iloc[0])
        if modal_step != interval:
            raise GreenButtonParseError(
                f"interval mismatch: rows declare {interval}-min spans but starts advance "
                f"by {modal_step} min. File may use an exclusive END TIME or be irregular."
            )
    return interval


def localize(naive: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Localize the portal's nominal wall-clock labels to true LA time.

    The portal does not export true wall-clock local time across DST; it writes a nominal
    hourly sequence. Two quirks, resolved by policy rather than trusting the label:

    * **Fall-back** (e.g. 2025-11-02): 24 labels for a 25-hour day. The lone, ambiguous
      ``01:00`` is assigned the DST/earlier fold (``ambiguous=True`` -> PDT). Both physical
      01:00 hours' energy is already summed into that one reading, so the second physical
      hour shows up as a single expected-grid gap.
    * **Spring-forward** (e.g. 2026-03-08): the file labels the transition slot ``02:00``
      (which does not exist in LA) and omits ``03:00`` (which does).
      ``nonexistent='shift_forward'`` maps that label to ``03:00``, yielding the correct
      contiguous real-time sequence with no collision.

    Both quirks fall in the early-morning super-off-peak window, so the sub-hour of energy
    they can misplace is TOU-neutral. Flagged billing decision (see SESSION_NOTES.md);
    revisit if a schedule ever prices 01:00-03:00 specially, or for a 15-min meter.
    """
    try:
        return naive.tz_localize(LOCAL_TZ, ambiguous=True, nonexistent="shift_forward")
    except ValueError as e:
        raise AmbiguousDSTError(f"could not localize interval timestamps to {LOCAL_TZ}: {e}") from e


def dst_transition_days(idx: pd.DatetimeIndex) -> tuple[list[str], list[str]]:
    """Dates (local) where the UTC offset changes, as seen in the data.

    Fall-back: PDT(-7h) -> PST(-8h). Spring-forward: PST(-8h) -> PDT(-7h).
    """
    if len(idx) < 2:
        return [], []
    # Signed UTC offset: local - UTC (PDT = -7h, PST = -8h).
    offsets = idx.tz_localize(None) - idx.tz_convert("UTC").tz_localize(None)
    changed = offsets.values[1:] != offsets.values[:-1]
    fall_back: list[str] = []
    spring_fwd: list[str] = []
    for i in range(1, len(idx)):
        if not changed[i - 1]:
            continue
        day = idx[i].strftime("%Y-%m-%d")
        # offset dropped (-7h -> -8h) => DST ended => fall back
        if offsets.values[i] < offsets.values[i - 1]:
            fall_back.append(day)
        else:
            spring_fwd.append(day)
    return sorted(set(fall_back)), sorted(set(spring_fwd))


def check_not_billing_summary(header_upper: list[str], filename: str, guidance: str) -> None:
    """Reject the billing-history export (START DATE/END DATE, one row per bill period)."""
    if "START DATE" in header_upper and "END DATE" in header_upper:
        raise BillingSummaryError(
            f"{filename} looks like a *billing-history* export (columns START DATE/END "
            f"DATE, one row per bill period). The engine needs the interval export: {guidance}"
        )


def finalize(
    *,
    utility: Utility,
    naive_start: pd.Series,
    start_min: pd.Series,
    end_min: pd.Series,
    kwh: pd.Series,
    estimated: pd.Series,
    meta: dict[str, str],
    service_id: str | None,
    source_file: str,
    extra_notes: list[str] | None = None,
) -> tuple[IntervalSeries, ParseReport]:
    """Assemble the canonical series + report from already-extracted, file-order columns.

    Interval inference, DST localization, the duplicate-timestamp guard, PII masking, and
    report construction are identical across utilities, so every parser routes through
    here after doing only its file-specific cell extraction.
    """
    naive_idx = pd.DatetimeIndex(naive_start)
    interval_min = interval_minutes(start_min, end_min, naive_idx)

    local_idx = localize(naive_idx)
    frame = pd.DataFrame(
        {COL_KWH: kwh.to_numpy(), COL_ESTIMATED: estimated.to_numpy()},
        index=local_idx,
    )

    dup = frame.index.duplicated(keep=False)
    if dup.any():
        example = frame.index[dup][:2].tolist()
        raise GreenButtonParseError(
            f"{source_file}: {int(dup.sum())} rows resolve to identical timestamps "
            f"(not a DST fold), e.g. {example}"
        )

    frame = frame.sort_index()
    frame.index.name = "interval_start"

    series = IntervalSeries(
        utility=utility,
        interval=pd.Timedelta(minutes=interval_min).to_pytimedelta(),
        meta=MeterMeta(
            utility=utility,
            service_id=service_id or meta.get("Service"),
            account_tail=mask_account(meta),
            address_zip=zip_from_address(meta),
            source_file=source_file,
        ),
        frame=frame,
    )

    fall_back, spring_fwd = dst_transition_days(frame.index)
    gaps = series.gaps()
    notes: list[str] = list(extra_notes or [])
    if len(gaps):
        notes.append(f"{len(gaps)} missing interval(s); coverage {series.coverage():.4f}")
    n_est = int(frame[COL_ESTIMATED].sum())
    if n_est:
        notes.append(f"{n_est} interval(s) flagged estimated")

    report = ParseReport(
        utility=utility,
        interval_minutes=interval_min,
        n_intervals=len(frame),
        n_estimated=n_est,
        n_gaps=len(gaps),
        coverage=series.coverage(),
        first_start=str(frame.index[0]),
        last_start=str(frame.index[-1]),
        total_kwh=series.total_kwh,
        dst_fall_back_days=fall_back,
        dst_spring_forward_days=spring_fwd,
        notes=notes,
    )
    return series, report
