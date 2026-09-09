"""Convert a utility's published NBT export-pricing file into a compact ACC table.

The utilities publish the CPUC Avoided Cost Calculator export rates as ~40 MB MIDAS
upload files: one row per *actual hour* of a 20-year horizon (350,640 rows), even though
the underlying tariff data is only 576 distinct values per year per component
(12 months x weekday/weekend x 24 hours, per Schedule NBT's own methodology).

This script collapses that redundancy into the repo's storage format — one gzipped CSV
per (utility, vintage) plus a mandatory citation manifest — and *verifies* the collapse
rather than assuming it: if any (year, component, ValueName) cell carries more than one
distinct value, the file does not have the structure the tariff describes and the script
raises instead of silently averaging.

Both California IOUs modelled here publish this same MIDAS shape, so one parser serves
both — only the RateLookupID prefix and the capitalisation of the unit differ. PG&E also
publishes a per-vintage *printed* price sheet (pge.com/energyexportcredit), but that sheet
carries a single calendar year of the horizon, so it is used as an independent
cross-check on the import rather than as the source; see tests/nem3/test_acc_pge.py.

Usage:
    PYTHONPATH=src python scripts/build_acc_tables.py \
        --utility SDG&E --vintage 2026 \
        --source "LY2026 NBT Pricing Upload MIDAS.csv" \
        --citation "SDG&E ... retrieved 2026-07-23"

The source files are downloaded by hand (they are large and public):
    SDG&E: https://www.sdge.com/solar/solar-billing-plan/export-pricing
           -> one zip per vintage, "LY<year> NBT Pricing Upload MIDAS.zip"
    PG&E:  https://www.pge.com/eecvalues
           -> ONE 36 MB zip holding all five vintages as
              "PG&E NBT EEC Values <2023|2024|2025|2026|Floating> Vintage.csv".
           pge.com/energyexportcredit is a *different* zip — the printed PDF price
           sheets. It is not the import source.
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from greenbutton.models import LOCAL_TZ
from nem3.acc import (
    COMPONENTS,
    DAY_TYPES,
    MONTH_ABBR,
    TABLES_DIR,
    table_stem,
)

# RateLookupID prefixes, from the readmes shipped inside each utility's MIDAS zip. Both
# utilities use the same convention: the letters in positions 6-7 name the delivery
# issuer and positions 8-9 the generation issuer, with "XX" for the one this row is not
# about. So "USCA-PGXX" is PG&E delivery and "USCA-XXPG" is PG&E generation. Prefixes are
# matched, never derived, so an unrecognised utility raises instead of being guessed at.
RIN_COMPONENT = {
    "USCA-SDXX": "delivery",
    "USCA-XXSD": "generation",
    "USCA-PGXX": "delivery",
    "USCA-XXPG": "generation",
}

#: Both utilities publish the same unit with different capitalisation: SDG&E writes
#: "export $/kWh", PG&E "Export $/kWh". The unit is still *checked* — a file priced in
#: $/MWh would misprice every export by 1000x — just not case-sensitively.
EXPECTED_UNIT = "export $/kwh"


def parse_midas(path: Path) -> pd.DataFrame:
    """MIDAS upload CSV -> tidy (year, month, day_type, hour, delivery, generation).

    ``DateStart``/``TimeStart`` are UTC; ``ValueName`` ("Jan Weekday HS17") is Pacific
    Prevailing Time. The calendar year a row belongs to is therefore the year of its
    *local* timestamp, not of the UTC one — the two differ for the first eight hours of
    every January, which is exactly the boundary the 20-year horizon starts on.
    """
    raw = pd.read_csv(path, usecols=["RIN", "DateStart", "TimeStart", "ValueName", "Value", "Unit"])
    units = set(raw["Unit"].unique())
    if {u.strip().lower() for u in units} != {EXPECTED_UNIT}:
        raise ValueError(f"{path.name}: unexpected Unit value(s) {sorted(units)}; expected $/kWh")

    comp = raw["RIN"].str[:9].map(RIN_COMPONENT)
    if comp.isna().any():
        unknown = sorted(raw.loc[comp.isna(), "RIN"].str[:9].unique())
        raise ValueError(f"{path.name}: unknown RateLookupID prefix(es) {unknown}")

    utc = pd.to_datetime(raw["DateStart"] + " " + raw["TimeStart"], format="%m/%d/%Y %H:%M:%S")
    local = utc.dt.tz_localize("UTC").dt.tz_convert(LOCAL_TZ)

    name = raw["ValueName"].str.extract(r"^(\w{3}) (Weekday|Weekend) HS(\d{1,2})$")
    if name.isna().any().any():
        bad = raw.loc[name.isna().any(axis=1), "ValueName"].iloc[0]
        raise ValueError(f"{path.name}: ValueName {bad!r} does not match '<Mon> <DayType> HS<h>'")

    tidy = pd.DataFrame(
        {
            "year": local.dt.year,
            "month": name[0].map({m: i + 1 for i, m in enumerate(MONTH_ABBR)}),
            "day_type": name[1].str.lower(),
            "hour": name[2].astype(int),
            "component": comp,
            "value": raw["Value"].astype(float),
        }
    )

    key = ["year", "month", "day_type", "hour", "component"]
    spread = tidy.groupby(key)["value"].nunique()
    if (spread > 1).any():
        n = int((spread > 1).sum())
        raise ValueError(
            f"{path.name}: {n} (year, month, day-type, hour, component) cell(s) carry more "
            "than one distinct rate. Schedule NBT's methodology produces exactly one value "
            "per cell, so this file does not have the documented structure — inspect it "
            "rather than collapsing it."
        )

    wide = (
        tidy.groupby(key)["value"]
        .first()
        .unstack("component")
        .reset_index()
        .sort_values(["year", "month", "day_type", "hour"])
    )
    missing = [c for c in COMPONENTS if c not in wide.columns]
    if missing:
        raise ValueError(f"{path.name}: no rows for component(s) {missing}")
    return wide[["year", "month", "day_type", "hour", *COMPONENTS]].reset_index(drop=True)


def _check_complete(table: pd.DataFrame, source: Path) -> list[int]:
    """Years whose 576 cells are all present; raises if a year is partial."""
    counts = table.groupby("year").size()
    full = counts[counts == 576].index.tolist()
    partial = counts[counts != 576]
    # The first and last calendar years of the horizon are legitimately clipped: the file
    # starts at midnight PST on Jan 1 and the UTC tail spills into the following year.
    interior = [y for y in partial.index if full and full[0] < y < full[-1]]
    if interior:
        raise ValueError(
            f"{source.name}: year(s) {interior} have fewer than 576 rate cells but are not "
            "at the edge of the horizon — the file is incomplete, refusing to publish it"
        )
    if not full:
        raise ValueError(f"{source.name}: no complete year found (need 576 cells)")
    return full


def build(
    *,
    utility: str,
    vintage: str,
    source: Path,
    citation: str,
    retrieved: date,
    out_dir: Path = TABLES_DIR,
) -> Path:
    table = parse_midas(source)
    years = _check_complete(table, source)
    table = table[table["year"].isin(years)].reset_index(drop=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = table_stem(utility, vintage)
    csv_path = out_dir / f"{stem}.csv.gz"
    table.to_csv(csv_path, index=False, float_format="%.6f", compression="gzip")

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {
        "utility": utility,
        "vintage": vintage,
        "citation": citation,
        "retrieved": retrieved.isoformat(),
        "source_file": source.name,
        "source_sha256": digest,
        "years": [int(min(years)), int(max(years))],
        "components": list(COMPONENTS),
        "day_types": list(DAY_TYPES),
        "rows": len(table),
    }
    (out_dir / f"{stem}.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return csv_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--utility", required=True, help="SDG&E | PG&E")
    ap.add_argument("--vintage", required=True, help="application year, or 'current' for NBT00")
    ap.add_argument("--source", required=True, type=Path, help="MIDAS upload CSV")
    ap.add_argument("--citation", required=True, help="URL + retrieval date + document title")
    ap.add_argument("--retrieved", default=date.today().isoformat())
    args = ap.parse_args()

    path = build(
        utility=args.utility,
        vintage=args.vintage,
        source=args.source,
        citation=args.citation,
        retrieved=date.fromisoformat(args.retrieved),
    )
    print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KiB)")


if __name__ == "__main__":
    main()
