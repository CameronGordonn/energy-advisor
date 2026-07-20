"""Parser for PG&E Green Button "Download my data" interval CSV exports.

Input shape (PG&E residential SmartMeter, "Export usage for a range of days"):

    <BOM>
    Name,JANE DOE
    Address,"123 EXAMPLE ST, CITY CA 90000"
    Account Number,0000000000
    Service,Service 1
    <blank>
    TYPE,DATE,START TIME,END TIME,USAGE (kWh),COST,NOTES
    Electric usage,2025-08-02,00:00,00:14,0.12,$0.03,
    ...

The billing-history export (``TYPE,START DATE,END DATE,USAGE (kWh),...``, one row per
bill period) is a *different* file; it is detected and rejected with a clear message,
because it cannot be re-priced under a counterfactual tariff.

Output: a canonical :class:`IntervalSeries` (tz-aware ``America/Los_Angeles``, PII
stripped) plus a :class:`ParseReport` capturing interval length, gaps, estimated
count, and DST transitions actually seen in the data.
"""

from __future__ import annotations

import csv
import io
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


def _decode(path: Path) -> list[str]:
    # utf-8-sig transparently strips the BOM PG&E prepends.
    text = path.read_text(encoding="utf-8-sig")
    return text.splitlines()


def _split_header_and_table(lines: list[str]) -> tuple[dict[str, str], list[str]]:
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


def _mask_account(meta: dict[str, str]) -> str | None:
    acct = meta.get("Account Number") or meta.get("Account")
    if not acct:
        return None
    digits = "".join(ch for ch in acct if ch.isdigit())
    return digits[-4:] if len(digits) >= 4 else None


def _zip_from_address(meta: dict[str, str]) -> str | None:
    addr = meta.get("Address")
    if not addr:
        return None
    # last token that starts with 5 digits (e.g. "900001234" -> "90000")
    for token in reversed(addr.replace(",", " ").split()):
        digits = "".join(ch for ch in token if ch.isdigit())
        if len(digits) >= 5:
            return digits[:5]
    return None


def _interval_minutes(df: pd.DataFrame, naive: pd.DatetimeIndex) -> int:
    """The file's declared interval in minutes, cross-checked two independent ways.

    PG&E writes ``END TIME`` as the interval's *inclusive last minute*
    (``00:00``->``00:59`` is a 60-min interval), so the per-row span is
    ``(END - START) mod 1440 + 1``. That is cross-checked against the modal gap
    between consecutive interval starts; the two must agree, which rejects both
    mixed-granularity files and any export that instead used an exclusive end.
    """
    span = ((df["_end_min"] - df["_start_min"]) % _DAY_MINUTES) + 1
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


def _localize(naive: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Localize PG&E's nominal wall-clock labels to true LA time.

    PG&E does not export true wall-clock local time across DST; it writes a nominal
    hourly sequence (see ``docs`` in the module header). Two quirks, resolved by
    policy rather than trusting the label:

    * **Fall-back** (e.g. 2025-11-02): 24 labels for a 25-hour day. The lone,
      ambiguous ``01:00`` is assigned the DST/earlier fold (``ambiguous=True`` ->
      PDT). Both physical 01:00 hours' energy is already summed into that one PG&E
      reading, so the second physical hour shows up as a single expected-grid gap.
    * **Spring-forward** (e.g. 2026-03-08): the file labels the transition slot
      ``02:00`` (which does not exist in LA) and omits ``03:00`` (which does).
      ``nonexistent='shift_forward'`` maps that label to ``03:00``, yielding the
      correct contiguous real-time sequence with no collision.

    Both quirks fall in the early-morning super-off-peak window, so the sub-hour of
    energy they can misplace is TOU-neutral. This is a flagged billing decision
    (see SESSION_NOTES.md); revisit if a schedule ever prices 01:00-03:00 specially.
    """
    try:
        return naive.tz_localize(LOCAL_TZ, ambiguous=True, nonexistent="shift_forward")
    except ValueError as e:
        raise AmbiguousDSTError(f"could not localize interval timestamps to {LOCAL_TZ}: {e}") from e


def _dst_transition_days(idx: pd.DatetimeIndex) -> tuple[list[str], list[str]]:
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


def parse_pge_interval_csv(
    path: str | Path,
    *,
    service_id: str | None = None,
) -> tuple[IntervalSeries, ParseReport]:
    """Parse a PG&E interval CSV into a canonical series and a parse report."""
    path = Path(path)
    lines = _decode(path)
    meta, table_lines = _split_header_and_table(lines)

    header = next(csv.reader([table_lines[0]]))
    header_upper = [h.strip().upper() for h in header]

    if "START DATE" in header_upper and "END DATE" in header_upper:
        raise BillingSummaryError(
            f"{path.name} looks like a PG&E *billing-history* export (columns "
            "START DATE/END DATE, one row per bill period). The engine needs the "
            "interval export: on the Energy Usage Details page, Green Button -> "
            "'Export usage for a range of days'."
        )
    for required in ("DATE", "START TIME", "END TIME"):
        if required not in header_upper:
            raise GreenButtonParseError(
                f"{path.name}: interval header missing {required!r}; got {header}"
            )

    df = pd.read_csv(io.StringIO("\n".join(table_lines)), dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]

    usage_col = next((c for c in df.columns if c.strip().upper().startswith("USAGE")), None)
    if usage_col is None:
        raise GreenButtonParseError(f"{path.name}: no 'USAGE (kWh)' column; got {list(df.columns)}")

    # --- timestamps (file order preserved for DST inference) ---
    start_time = df["START TIME"].str.strip()
    end_time = df["END TIME"].str.strip()
    naive_start = pd.to_datetime(df["DATE"].str.strip() + " " + start_time, format="%Y-%m-%d %H:%M")
    if naive_start.isna().any():
        bad = df["DATE"][naive_start.isna()].iloc[0]
        raise GreenButtonParseError(f"{path.name}: unparseable DATE/START TIME near {bad!r}")

    def _to_minutes(s: pd.Series) -> pd.Series:
        parts = s.str.split(":", expand=True).astype(int)
        return parts[0] * 60 + parts[1]

    df = df.assign(
        _naive=naive_start.to_numpy(),
        _start_min=_to_minutes(start_time),
        _end_min=_to_minutes(end_time),
    )

    interval_min = _interval_minutes(df, pd.DatetimeIndex(df["_naive"]))

    # --- kWh + estimated flag ---
    kwh = pd.to_numeric(df[usage_col].str.replace(r"[$,]", "", regex=True), errors="coerce")
    if kwh.isna().any():
        bad = df[usage_col][kwh.isna()].iloc[0]
        raise GreenButtonParseError(f"{path.name}: non-numeric usage value {bad!r}")

    notes_col = next((c for c in df.columns if c.strip().upper() == "NOTES"), None)
    if notes_col is not None:
        estimated = df[notes_col].str.contains("estimat", case=False, na=False)
    else:
        estimated = pd.Series(False, index=df.index)

    # --- localize and assemble ---
    local_idx = _localize(pd.DatetimeIndex(df["_naive"]))
    frame = pd.DataFrame(
        {COL_KWH: kwh.to_numpy(), COL_ESTIMATED: estimated.to_numpy()},
        index=local_idx,
    )

    dup = frame.index.duplicated(keep=False)
    if dup.any():
        example = frame.index[dup][:2].tolist()
        raise GreenButtonParseError(
            f"{path.name}: {int(dup.sum())} rows resolve to identical timestamps "
            f"(not a DST fold), e.g. {example}"
        )

    frame = frame.sort_index()
    frame.index.name = "interval_start"

    series = IntervalSeries(
        utility=Utility.PGE,
        interval=pd.Timedelta(minutes=interval_min).to_pytimedelta(),
        meta=MeterMeta(
            utility=Utility.PGE,
            service_id=service_id or meta.get("Service"),
            account_tail=_mask_account(meta),
            address_zip=_zip_from_address(meta),
            source_file=path.name,
        ),
        frame=frame,
    )

    fall_back, spring_fwd = _dst_transition_days(frame.index)
    gaps = series.gaps()
    notes: list[str] = []
    if len(gaps):
        notes.append(f"{len(gaps)} missing interval(s); coverage {series.coverage():.4f}")
    n_est = int(frame[COL_ESTIMATED].sum())
    if n_est:
        notes.append(f"{n_est} interval(s) flagged estimated")

    report = ParseReport(
        utility=Utility.PGE,
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
