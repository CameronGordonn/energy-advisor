"""Parser for SDG&E Green Button interval CSV exports.

SDG&E emits **two different CSV shapes**, and this parser accepts both, because which
one a customer gets depends on where in the portal they clicked and neither is
announced in the file.

**1. The "meter" shape — the one a real export was observed to use.** A long
``Key,Value`` preamble, then a table keyed by meter number with an interval
``Duration`` in minutes and separate consumption/generation registers::

    Name,JANE DOE
    Address,123 EXAMPLE AVENUE  San Diego CA 92101
    Account Number,0000000000
    Disclaimer,The information contained in this file is intended for ...
    Title,CSV Export Electric Meter(s)
    Resource,Electric
    Meter Number,00000000
    Interval UOM,Minute(s)
    Reading Start,11/1/2022 00:00
    Reading End,11/30/2022 23:00
    Total Duration,30 Days
    Total Usage,817.415
    UOM,kWh
    Meter Number,Date,Start Time,Duration,Consumption,Generation,Net
    "00000000","11/1/2022","12:00 AM","60","0.2200","","0.2200"

**2. The "range" shape** — SDG&E's documented Opower "Download My Data" table, the
same skeleton PG&E writes::

    TYPE,DATE,START TIME,END TIME,IMPORT (kWh),EXPORT (kWh),COST,NOTES
    Electric usage,9/1/2025,0:00,0:14,0.12,0,$0.03,

Four things the meter shape does that the documented one does not, each of which broke
this parser before 2026-09-08 (see SESSION_NOTES):

* **``Duration`` in minutes instead of ``END TIME``.** Reconstructed here into the
  inclusive-last-minute end the shared interval inference expects, so that inference —
  including its cross-check against the modal step between rows — is unchanged.
* **12-hour ``h:MM AM/PM`` times**, handled in :func:`greenbutton._common.to_minutes`.
* **``Consumption``/``Generation``/``Net`` registers** rather than ``IMPORT``/``EXPORT``.
* **A true 25-hour DST fall-back day**, with ``1:00 AM`` written twice — where PG&E
  writes 24 labels and sums the two physical hours. Resolved from file order in
  :func:`greenbutton._common.localize`.

Import vs export: M1 bills grid import, so the canonical series is the consumption /
import register. An export register carrying energy is surfaced in the report notes
rather than billed — NEM export netting is the M3 milestone. **Unverified:** whether
SDG&E's ``Net`` column is per-interval netted for a NEM account, and therefore whether
``Consumption`` is gross. Establish that from a real solar export before M3 prices one;
the file on hand is a non-solar account with an empty ``Generation`` column.

Provenance of the observed shape: a real, author-anonymised export committed to
github.com/corruptbear/my_sdge (``example/Electric_60_Minute_11-1-2022_11-30-2022_20230819.csv``),
60-minute resolution, November 2022. That repo has no LICENSE file, so its bytes are not
vendored here; the fixtures below are hand-authored to the observed shape. **One file,
one portal vintage, one resolution** — the 15-minute variant and a spring-forward month
are both still unseen.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd

from ._common import (
    GreenButtonParseError,
    check_not_billing_summary,
    decode,
    finalize,
    split_header_and_table,
    to_minutes,
)
from .models import IntervalSeries, ParseReport, Utility

__all__ = ["parse_sdge_interval_csv"]

# SDG&E writes M/D unpadded (%m/%d accepts 1-2 digits) but is NOT consistent about the
# YEAR: the same portal emits four-digit ('11/1/2022') and two-digit ('3/1/24') years in
# otherwise identical meter-shape files. Both are tried, four-digit first, and the format
# is elected per FILE rather than per row: the first candidate that parses every row wins.
# A file mixing the two parses under neither and is refused, which is correct — '3/1/24'
# read as %m/%d/%Y is year 24, and a silent century slip is worse than a rejection.
_SDGE_DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y")

# The declared-total cross-check tolerates per-row printing at 4 decimal places.
_TOTAL_USAGE_ATOL = 0.05


def _find_import_col(columns: list[str]) -> str | None:
    """The column holding grid import (billed usage), by SDG&E naming priority."""
    upper = {c: c.strip().upper() for c in columns}
    # IMPORT wins when present (range-shape solar split); else the single usage column.
    for c, u in upper.items():
        if u.startswith("IMPORT"):
            return c
    for c, u in upper.items():
        if u.startswith("USAGE") or u == "CONSUMPTION":
            return c
    return None


def _find_export_col(columns: list[str]) -> str | None:
    """The export register: ``EXPORT (kWh)`` (range shape) or ``Generation`` (meter shape)."""
    for c in columns:
        u = c.strip().upper()
        if u.startswith("EXPORT") or u == "GENERATION":
            return c
    return None


def _declared_total_note(
    meta: dict[str, str], billed_kwh: float, export_kwh: float = 0.0
) -> str | None:
    """Cross-check the summed readings against the preamble's ``Total Usage``, if present.

    This is free validation that every row was read: the meter shape prints its own
    total, and on the one real export seen it matched the summed ``Consumption`` column
    to the digit (817.415 kWh).

    On a SOLAR account the declared total is the NET sum, not the consumption sum.
    Established on a real 15-minute NEM export whose Consumption summed to 7318.845 kWh
    against a declared 4373.935 — a shortfall of exactly the 2944.910 kWh Generation
    register. So a mismatch that equals the export total is the netted-total convention
    and is benign; only an unexplained one is worth a warning. Saying "rows may be
    missing" to a solar customer whose file is complete is a false alarm on every NEM
    export, which is the class of defect this parser is meant not to have.

    Deliberately a **note, never a rejection**. A file whose delivered rows have gaps
    could legitimately undershoot a total computed over the requested range. Turning one
    observation into a rejection rule is how a valid export gets refused, which is the
    failure mode HANDOFF.md warns against.
    """
    raw = meta.get("Total Usage")
    if not raw:
        return None
    try:
        declared = float(raw.replace(",", ""))
    except ValueError:
        return f"declared 'Total Usage' {raw!r} is not numeric; skipped the total cross-check"

    tol = max(_TOTAL_USAGE_ATOL, abs(declared) * 1e-6)
    diff = billed_kwh - declared
    if abs(diff) <= tol:
        return f"declared Total Usage {declared:g} kWh reconciles with the summed readings"
    if export_kwh > 0 and abs(diff - export_kwh) <= tol:
        return (
            f"declared Total Usage {declared:g} kWh is the NET sum (import {billed_kwh:.3f} "
            f"- export {export_kwh:.3f}); the summed import readings reconcile with it"
        )
    return (
        f"declared Total Usage {declared:g} kWh does NOT match the summed readings "
        f"({billed_kwh:.3f} kWh, difference {diff:+.3f}); rows may be missing or the "
        "declared total may cover a different register — check before pricing this file"
    )


def parse_sdge_interval_csv(
    path: str | Path,
    *,
    service_id: str | None = None,
) -> tuple[IntervalSeries, ParseReport]:
    """Parse an SDG&E interval CSV (either shape) into a canonical series and a report."""
    path = Path(path)
    lines = decode(path)
    meta, table_lines = split_header_and_table(lines)

    header = next(csv.reader([table_lines[0]]))
    header_upper = [h.strip().upper() for h in header]

    check_not_billing_summary(
        header_upper,
        path.name,
        "in SDG&E's Green Button tool choose the interval usage export (15-min or hourly), "
        "not the billing-history summary.",
    )
    for required in ("DATE", "START TIME"):
        if required not in header_upper:
            raise GreenButtonParseError(
                f"{path.name}: interval header missing {required!r}; got {header}"
            )
    if "END TIME" not in header_upper and "DURATION" not in header_upper:
        raise GreenButtonParseError(
            f"{path.name}: interval header has neither 'END TIME' (range shape) nor "
            f"'DURATION' (meter shape); got {header}"
        )

    df = pd.read_csv(io.StringIO("\n".join(table_lines)), dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    cols = {c.strip().upper(): c for c in df.columns}

    import_col = _find_import_col(list(df.columns))
    if import_col is None:
        raise GreenButtonParseError(
            f"{path.name}: no import/usage column found (looked for IMPORT/USAGE/CONSUMPTION); "
            f"got {list(df.columns)}"
        )

    def _numeric(col: str, *, allow_blank: bool = False) -> pd.Series:
        raw = df[col].str.replace(r"[$,]", "", regex=True).str.strip()
        if allow_blank:
            raw = raw.replace("", "0")
        vals = pd.to_numeric(raw, errors="coerce")
        if vals.isna().any():
            bad = df[col][vals.isna()].iloc[0]
            raise GreenButtonParseError(f"{path.name}: non-numeric value {bad!r} in {col!r}")
        return vals

    # --- timestamps (file order preserved for DST inference) ---
    # Built from date + minutes-since-midnight rather than concatenating strings, so one
    # time parser serves both the 24-hour and the 12-hour shape.
    start_time = df[cols["START TIME"]].str.strip()
    start_min = to_minutes(start_time)
    raw_date = df[cols["DATE"]].str.strip()
    naive_date = None
    for fmt in _SDGE_DATE_FORMATS:
        parsed = pd.to_datetime(raw_date, format=fmt, errors="coerce")
        if not parsed.isna().any():
            naive_date = parsed
            break
    if naive_date is None:
        first = pd.to_datetime(raw_date, format=_SDGE_DATE_FORMATS[0], errors="coerce")
        bad = raw_date[first.isna()].iloc[0] if first.isna().any() else raw_date.iloc[0]
        raise GreenButtonParseError(
            f"{path.name}: unparseable DATE {bad!r} "
            f"(expected SDG&E {' or '.join(_SDGE_DATE_FORMATS)}, e.g. '9/1/2025' or '9/1/25')"
        )
    naive_start = naive_date + pd.to_timedelta(start_min, unit="m")

    if "END TIME" in cols:
        end_min = to_minutes(df[cols["END TIME"]].str.strip())
    else:
        # Meter shape: reconstruct the inclusive last minute the shared interval
        # inference expects, so its span-vs-modal-step cross-check still applies.
        duration = _numeric(cols["DURATION"])
        if duration.le(0).any():
            bad = df[cols["DURATION"]][duration.le(0)].iloc[0]
            raise GreenButtonParseError(f"{path.name}: non-positive DURATION {bad!r}")
        end_min = start_min + duration.astype(int) - 1

    kwh = _numeric(import_col)

    notes_col = next((c for c in df.columns if c.strip().upper() == "NOTES"), None)
    if notes_col is not None:
        estimated = df[notes_col].str.contains("estimat", case=False, na=False)
    else:
        estimated = pd.Series(False, index=df.index)

    extra_notes: list[str] = []

    # Export register (NEM/solar): billed only from M3, but flag its presence now so a
    # solar account isn't silently treated as import-only without a trace. Blanks are
    # legitimate on the meter shape — a non-solar account leaves Generation empty.
    export_col = _find_export_col(list(df.columns))
    total_export = 0.0
    if export_col is not None:
        total_export = float(_numeric(export_col, allow_blank=True).sum())
        if total_export > 0:
            extra_notes.append(
                f"export register present ({export_col!r}, {total_export:.3f} kWh total); "
                "M1 bills grid import only — NEM export netting is M3"
            )

    total_note = _declared_total_note(meta, float(kwh.sum()), total_export)
    if total_note:
        extra_notes.append(total_note)

    return finalize(
        utility=Utility.SDGE,
        naive_start=naive_start,
        start_min=start_min,
        end_min=end_min,
        kwh=kwh,
        estimated=estimated,
        meta=meta,
        service_id=service_id,
        source_file=path.name,
        extra_notes=extra_notes,
    )
