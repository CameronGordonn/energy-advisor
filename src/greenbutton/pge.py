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
count, and DST transitions actually seen in the data. Everything utility-neutral (DST
folding, interval inference, PII masking, the canonical assembly) lives in
:mod:`greenbutton._common`; only PG&E's cell-level details are here.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd

from ._common import (
    AmbiguousDSTError,
    BillingSummaryError,
    GreenButtonParseError,
    check_not_billing_summary,
    decode,
    finalize,
    split_header_and_table,
    to_minutes,
)
from .models import IntervalSeries, ParseReport, Utility

__all__ = [
    "AmbiguousDSTError",
    "BillingSummaryError",
    "GreenButtonParseError",
    "parse_pge_interval_csv",
]


def parse_pge_interval_csv(
    path: str | Path,
    *,
    service_id: str | None = None,
) -> tuple[IntervalSeries, ParseReport]:
    """Parse a PG&E interval CSV into a canonical series and a parse report."""
    path = Path(path)
    lines = decode(path)
    meta, table_lines = split_header_and_table(lines)

    header = next(csv.reader([table_lines[0]]))
    header_upper = [h.strip().upper() for h in header]

    check_not_billing_summary(
        header_upper,
        path.name,
        "on the Energy Usage Details page, Green Button -> 'Export usage for a range of days'.",
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

    return finalize(
        utility=Utility.PGE,
        naive_start=naive_start,
        start_min=to_minutes(start_time),
        end_min=to_minutes(end_time),
        kwh=kwh,
        estimated=estimated,
        meta=meta,
        service_id=service_id,
        source_file=path.name,
    )
