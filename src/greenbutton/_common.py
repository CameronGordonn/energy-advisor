"""Shared primitives for Green Button interval parsers (PG&E, SDG&E, ...).

Both IOUs write a ``Key,Value`` metadata preamble followed by one interval table, and
the timezone / gap / PII handling is common to both. **The formats are otherwise less
alike than they look**, and two differences reach into this module:

* **The table header is not a fixed string.** PG&E writes
  ``TYPE,DATE,START TIME,END TIME,...``; SDG&E's real export writes
  ``Meter Number,Date,Start Time,Duration,Consumption,Generation,Net``. The table is
  therefore located by *signature* — a row carrying a date column and a start-time
  column — not by a leading literal. See :func:`split_header_and_table`.
* **DST is exported differently.** PG&E writes 24 nominal hour labels on the fall-back
  day and sums both physical 01:00 hours into one reading. SDG&E writes the true
  25-hour day, with ``1:00 AM`` appearing twice. :func:`localize` resolves the fold
  from *file order* so both are correct; see its docstring for what remains unverified.

Everything a parser would otherwise duplicate lives here, so there is one source of
truth for the tricky parts (interval inference, DST folding, the canonical assembly).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import numpy as np
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


def _is_table_header(fields: list[str]) -> bool:
    """Whether a CSV row is the table header, by signature rather than a leading literal.

    Both real export shapes have to match, and so does the *wrong* file, so that
    :func:`check_not_billing_summary` can produce its specific message rather than a
    generic "no table found"::

        TYPE,DATE,START TIME,END TIME,USAGE (kWh),COST,NOTES     PG&E interval
        Meter Number,Date,Start Time,Duration,Consumption,...    SDG&E interval
        TYPE,START DATE,END DATE,USAGE (kWh),COST,NOTES          billing history (rejected)

    Metadata rows are ``Key,Value`` pairs, so the >=3-field floor keeps a preamble row
    from matching. That floor matters more than it looks: SDG&E's preamble contains a
    literal ``Meter Number,00000000`` row *above* a header that also begins with
    ``Meter Number``, so a leading-token test would stop at the wrong line.
    """
    if len(fields) < 3:
        return False
    upper = {f.strip().upper() for f in fields}
    if "DATE" in upper and "START TIME" in upper:
        return True
    return "START DATE" in upper and "END DATE" in upper


def split_header_and_table(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """Return (metadata dict, table lines), locating the table by header signature."""
    meta: dict[str, str] = {}
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        # Rows are "Key,Value" (metadata) or the table header; use csv either way so a
        # quoted comma inside an Address or Disclaimer cell does not split the row.
        row = next(csv.reader([line]), [])
        if _is_table_header(row):
            return meta, lines[i:]
        if len(row) >= 2 and row[0]:
            meta[row[0].strip()] = row[1].strip()
    raise GreenButtonParseError(
        "no interval table found: expected a header row carrying a date column and a "
        "start-time column, e.g. 'TYPE,DATE,START TIME,END TIME,...' (PG&E) or "
        "'Meter Number,Date,Start Time,Duration,Consumption,...' (SDG&E)"
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


# "0:00", "00:00", "12:00 AM", "1:00 p.m." -> hour, minute, optional meridiem.
_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})(?:\s*([AaPp])\.?[Mm]\.?)?\s*$")


def to_minutes(s: pd.Series) -> pd.Series:
    """Clock time -> minutes since midnight, for both exports' time formats.

    PG&E writes 24-hour ``HH:MM``; SDG&E's real export writes 12-hour ``h:MM AM/PM``
    (and its documented shape writes unpadded 24-hour ``H:MM``). All three parse here,
    so neither parser has to carry a time format of its own.
    """
    parts = s.str.extract(_TIME_RE)
    bad = parts[0].isna()
    if bad.any():
        raise GreenButtonParseError(
            f"unparseable clock time {s[bad].iloc[0]!r}; expected 'H:MM' or 'h:MM AM/PM'"
        )

    hour = parts[0].astype(int)
    minute = parts[1].astype(int)
    meridiem = parts[2].str.upper()
    has_meridiem = meridiem.notna()

    if minute.gt(59).any():
        raise GreenButtonParseError(f"minute out of range in {s[minute.gt(59)].iloc[0]!r}")
    limit = has_meridiem.map({True: 12, False: 23})
    if hour.gt(limit).any():
        raise GreenButtonParseError(f"hour out of range in {s[hour.gt(limit)].iloc[0]!r}")

    if has_meridiem.any():
        # 12 AM -> 00, 12 PM -> 12, 1-11 PM -> +12. Order matters: fold midnight first.
        hour = hour.where(~(has_meridiem & meridiem.eq("A") & hour.eq(12)), 0)
        hour = hour.where(~(has_meridiem & meridiem.eq("P") & hour.ne(12)), hour + 12)

    return hour * 60 + minute


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


def _fold_flags(naive: pd.DatetimeIndex) -> np.ndarray | bool:
    """Per-row DST fold assignment for the ambiguous fall-back hour, from file order.

    ``True`` means the earlier (DST/PDT) reading, ``False`` the later (PST) one — pandas'
    ``ambiguous=`` convention. The two utilities need different answers and neither
    announces which it is, so it is inferred from whether the label repeats:

    * **PG&E writes 24 labels for the 25-hour day**, having summed both physical 01:00
      hours into one reading. Nothing repeats, every flag is ``True``, and the second
      physical hour surfaces as a single expected-grid gap. Unchanged behaviour.
    * **SDG&E writes the true 25-hour day** — ``1:00 AM`` appears twice, in real-time
      order. The first occurrence is PDT and the second PST, so there is no gap and no
      energy is merged. Confirmed against a real export (SESSION_NOTES 2026-09-08).

    A label repeating three or more times is not a fold — a fold is exactly two — so it
    is rejected here rather than silently mis-assigned.
    """
    if not naive.duplicated().any():
        return True  # scalar: the common path, no allocation
    labels = pd.Series(naive)
    occurrence = labels.groupby(labels, sort=False).cumcount().to_numpy()
    if (occurrence > 1).any():
        label = naive[occurrence > 1][0]
        raise AmbiguousDSTError(
            f"timestamp label {label} appears more than twice; a DST fall-back fold is "
            "exactly two readings, so this file has duplicated or malformed rows"
        )
    return occurrence == 0


def localize(naive: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Localize the export's wall-clock labels to true LA time.

    * **Fall-back** (e.g. 2025-11-02): the ambiguous ``01:00`` label is resolved by
      :func:`_fold_flags`, which handles both a summed single reading (PG&E) and a true
      repeated pair (SDG&E).
    * **Spring-forward** (e.g. 2026-03-08): PG&E labels the transition slot ``02:00``
      (which does not exist in LA) and omits ``03:00`` (which does).
      ``nonexistent='shift_forward'`` maps that label to ``03:00``, giving a contiguous
      real-time sequence with no collision. **UNVERIFIED for SDG&E** — the real export on
      hand covers November only, so whether SDG&E labels the missing hour or omits it is
      unknown. Both conventions happen to survive this policy (an omitted label simply
      never triggers ``shift_forward``), but that is luck, not evidence: check it against
      the first SDG&E export spanning March.

    Both quirks fall in the early-morning super-off-peak window, so the sub-hour of energy
    they can misplace is TOU-neutral. Flagged billing decision (see SESSION_NOTES.md);
    revisit if a schedule ever prices 01:00-03:00 specially, or for a 15-min meter.
    """
    try:
        return naive.tz_localize(
            LOCAL_TZ, ambiguous=_fold_flags(naive), nonexistent="shift_forward"
        )
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
