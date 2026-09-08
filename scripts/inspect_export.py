#!/usr/bin/env python
"""Inspect a Green Button interval export — the first command to run on a new file.

    PYTHONPATH=src python scripts/inspect_export.py FILE.csv
    PYTHONPATH=src python scripts/inspect_export.py FILE.csv --json

Answers "did we read this correctly, and what does the usage look like" without pricing
anything. Deliberately produces no dollar figures: pricing needs a tariff spec, and per
CLAUDE.md's reconciliation gate may only ship for a utility whose bills the engine has been
shown to reproduce. Usage arithmetic on the customer's own meter carries no such gate, so
this runs against any export — including from a utility the biller has never seen.

This is also the browser tool's engine (see docs/tool.html), which runs this exact module
under Pyodide so the analysis a visitor gets is the analysis the tests cover.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from greenbutton._common import GreenButtonParseError
from report.inspect import Inspection, inspect_export

BAR = "─" * 78


def _bar(frac: float, width: int = 28) -> str:
    filled = max(0, min(width, round(frac * width)))
    return "█" * filled + "·" * (width - filled)


def render(i: Inspection) -> str:
    out: list[str] = []
    a = out.append
    a(BAR)
    a(f"  {i.source_name}  —  read as {i.utility}")
    a(BAR)

    a("")
    a("  DID WE READ IT CORRECTLY?")
    a(f"    Utility            {i.utility}")
    a(f"    Reading interval   {i.interval_minutes} minutes")
    a(f"    Covers             {i.first_start[:10]} to {i.last_start[:10]}  ({i.span_days} days)")
    a(f"    Readings           {i.n_intervals:,}   coverage {i.coverage:.4%}   gaps {i.n_gaps}")
    if i.n_estimated:
        a(f"    Estimated          {i.n_estimated} reading(s) flagged by the utility")
    if i.dst_fall_back_days or i.dst_spring_forward_days:
        a(
            f"    DST handled        fall-back {i.dst_fall_back_days or '—'}   "
            f"spring-forward {i.dst_spring_forward_days or '—'}"
        )
    if i.has_export_register:
        a(f"    Solar export       PRESENT — {i.export_kwh:,.1f} kWh exported to the grid")
    a(f"    Bill-comparable    {'yes' if i.looks_billable else 'NO — see warnings'}")

    a("")
    a("  WHAT DID YOU USE?")
    a(f"    Total              {i.total_kwh:,.1f} kWh over {i.span_days} days")
    a(f"    Average            {i.avg_kwh_per_day:,.2f} kWh/day")
    a(f"    Weekday / weekend  {i.weekday_kwh:,.1f} / {i.weekend_kwh:,.1f} kWh")
    if i.busiest_day:
        a(f"    Busiest day        {i.busiest_day}  ({i.busiest_day_kwh:,.1f} kWh)")
    if i.busiest_hour_of_day is not None:
        h = i.busiest_hour_of_day
        a(f"    Busiest hour       {h:02d}:00-{(h + 1) % 24:02d}:00 across the whole period")

    a("")
    a("  WHEN DID YOU USE IT?   (the shares that decide whether a TOU rate helps)")
    a(f"    4-9 p.m. peak      {_bar(i.peak_share)}  {i.peak_share:6.1%}")
    a(f"      ...on weekdays   {_bar(i.peak_share_weekday)}  {i.peak_share_weekday:6.1%}")
    a(f"    Midnight-6 a.m.    {_bar(i.overnight_share)}  {i.overnight_share:6.1%}")
    a(f"    10 a.m.-2 p.m.     {_bar(i.solar_window_share)}  {i.solar_window_share:6.1%}")
    a("    (4-9 p.m. is the on-peak window of both PG&E E-TOU-C and SDG&E TOU-DR1.)")

    if i.by_hour_kwh and i.total_kwh:
        a("")
        a("  HOUR-OF-DAY PROFILE   (share of total usage)")
        peak_h = max(i.by_hour_kwh)
        for h in range(24):
            share = i.by_hour_kwh[h] / i.total_kwh
            marker = " <- peak window" if 16 <= h < 21 else ""
            rel = i.by_hour_kwh[h] / peak_h if peak_h else 0
            a(f"    {h:02d}  {_bar(rel, 34)} {share:5.1%}{marker}")

    if i.by_month:
        a("")
        a("  BY MONTH")
        mx = max(m.kwh for m in i.by_month)
        for m in i.by_month:
            a(f"    {m.month}  {_bar(m.kwh / mx if mx else 0, 30)} {m.kwh:8,.1f} kWh  ({m.days}d)")

    if i.warnings:
        a("")
        a("  ⚠ WARNINGS")
        for w in i.warnings:
            a(f"    - {w}")

    if i.notes:
        a("")
        a("  NOTES FROM THE PARSER")
        for n in i.notes:
            a(f"    - {n}")

    a("")
    a(BAR)
    a("  No dollar figures here by design — pricing requires a tariff spec, and only")
    a("  ships for a utility whose real bills this engine reproduces within $2.")
    a(BAR)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("file", help="Green Button interval CSV (PG&E or SDG&E)")
    ap.add_argument("--json", action="store_true", help="emit the inspection as JSON")
    args = ap.parse_args(argv)

    try:
        result = inspect_export(args.file)
    except GreenButtonParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print(f"error: no such file: {args.file}", file=sys.stderr)
        return 2

    print(result.model_dump_json(indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
