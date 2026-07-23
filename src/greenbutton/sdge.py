"""Parser for SDG&E Green Button "Download My Data" interval CSV exports.

SDG&E's usage portal runs on the same Opower platform as PG&E, so the file skeleton is
the same (``Name``/``Address``/``Account Number`` metadata rows, then a
``TYPE,DATE,START TIME,END TIME,...`` interval table) and the tz/DST/gap/PII handling is
shared verbatim via :mod:`greenbutton._common`. Two SDG&E-specific differences are
handled here:

* **Date format.** SDG&E writes ``M/D/YYYY`` (e.g. ``9/1/2025``), not PG&E's ISO
  ``YYYY-MM-DD``. Times are 24-hour ``H:MM``/``HH:MM``.
* **Import vs export columns.** For a non-solar account there is a single usage column
  (``USAGE (kWh)`` / ``Consumption``). For an NEM/solar account SDG&E splits the register
  into ``IMPORT (kWh)`` and ``EXPORT (kWh)``. The canonical import series is what M1 bills,
  so this parser reads the import register; if an export column carries energy it is
  surfaced in the report notes (export/NEM netting is the M3 milestone, not M1).

Expected input shape (residential 15-min meter)::

    <BOM>
    Name,JANE DOE
    Address,"123 EXAMPLE ST, SAN DIEGO CA 92101"
    Account Number,0000000000
    Service,Service 1
    <blank>
    TYPE,DATE,START TIME,END TIME,IMPORT (kWh),EXPORT (kWh),COST,NOTES
    Electric usage,9/1/2025,0:00,0:14,0.12,0,$0.03,
    ...

No real SDG&E export is on hand yet, so this parser is built to SDG&E's documented Opower
format and unit-tested against it; validate against the first real file when it lands.
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

# SDG&E writes M/D/YYYY (unpadded); strptime %m/%d accept 1-2 digits, %H accepts 1-2.
_SDGE_DATETIME_FORMAT = "%m/%d/%Y %H:%M"


def _find_import_col(columns: list[str]) -> str | None:
    """The column holding grid import (billed usage), by SDG&E naming priority."""
    upper = {c: c.strip().upper() for c in columns}
    # IMPORT wins when present (solar/NEM split); else the single usage/consumption column.
    for c, u in upper.items():
        if u.startswith("IMPORT"):
            return c
    for c, u in upper.items():
        if u.startswith("USAGE") or u == "CONSUMPTION":
            return c
    return None


def _find_export_col(columns: list[str]) -> str | None:
    for c in columns:
        if c.strip().upper().startswith("EXPORT"):
            return c
    return None


def parse_sdge_interval_csv(
    path: str | Path,
    *,
    service_id: str | None = None,
) -> tuple[IntervalSeries, ParseReport]:
    """Parse an SDG&E interval CSV into a canonical series and a parse report."""
    path = Path(path)
    lines = decode(path)
    meta, table_lines = split_header_and_table(lines)

    header = next(csv.reader([table_lines[0]]))
    header_upper = [h.strip().upper() for h in header]

    check_not_billing_summary(
        header_upper,
        path.name,
        "in SDG&E's Green Button tool choose the interval usage export (15-min), not the "
        "billing-history summary.",
    )
    for required in ("DATE", "START TIME", "END TIME"):
        if required not in header_upper:
            raise GreenButtonParseError(
                f"{path.name}: interval header missing {required!r}; got {header}"
            )

    df = pd.read_csv(io.StringIO("\n".join(table_lines)), dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]

    import_col = _find_import_col(list(df.columns))
    if import_col is None:
        raise GreenButtonParseError(
            f"{path.name}: no import/usage column found (looked for IMPORT/USAGE/CONSUMPTION); "
            f"got {list(df.columns)}"
        )

    # --- timestamps (file order preserved for DST inference) ---
    start_time = df["START TIME"].str.strip()
    end_time = df["END TIME"].str.strip()
    naive_start = pd.to_datetime(
        df["DATE"].str.strip() + " " + start_time,
        format=_SDGE_DATETIME_FORMAT,
        errors="coerce",
    )
    if naive_start.isna().any():
        bad = df["DATE"][naive_start.isna()].iloc[0]
        raise GreenButtonParseError(
            f"{path.name}: unparseable DATE/START TIME near {bad!r} "
            f"(expected SDG&E {_SDGE_DATETIME_FORMAT!r}, e.g. '9/1/2025 0:00')"
        )

    def _numeric(col: str) -> pd.Series:
        vals = pd.to_numeric(df[col].str.replace(r"[$,]", "", regex=True), errors="coerce")
        if vals.isna().any():
            bad = df[col][vals.isna()].iloc[0]
            raise GreenButtonParseError(f"{path.name}: non-numeric value {bad!r} in {col!r}")
        return vals

    kwh = _numeric(import_col)

    notes_col = next((c for c in df.columns if c.strip().upper() == "NOTES"), None)
    if notes_col is not None:
        estimated = df[notes_col].str.contains("estimat", case=False, na=False)
    else:
        estimated = pd.Series(False, index=df.index)

    # Export register (NEM/solar): billed only from M3, but flag its presence now so a
    # solar account isn't silently treated as import-only without a trace.
    extra_notes: list[str] = []
    export_col = _find_export_col(list(df.columns))
    if export_col is not None:
        export = _numeric(export_col)
        total_export = float(export.sum())
        if total_export > 0:
            extra_notes.append(
                f"export register present ({export_col!r}, {total_export:.3f} kWh total); "
                "M1 bills grid import only — NEM export netting is M3"
            )

    return finalize(
        utility=Utility.SDGE,
        naive_start=naive_start,
        start_min=to_minutes(start_time),
        end_min=to_minutes(end_time),
        kwh=kwh,
        estimated=estimated,
        meta=meta,
        service_id=service_id,
        source_file=path.name,
        extra_notes=extra_notes,
    )
