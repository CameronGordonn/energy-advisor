#!/usr/bin/env python
"""Generate the SYNTHETIC sample export the public tool offers as a demo.

    python scripts/make_sample_export.py

Most visitors to the site will not have a Green Button file to hand, so the tool offers a
sample. That sample must be **fabricated**, not a real household's meter data — publishing
someone's minute-by-minute occupancy pattern is exactly the privacy line this project does
not cross (CLAUDE.md: real exports live in the git-ignored ``data/``).

It is committed alongside this generator so anyone can see precisely how it was made, and
the tool labels every result computed from it as a demonstration. Nothing in the repo draws
an analytical conclusion from it — differentiation invariant 6 (real interval data, never
modeled load profiles) governs *analysis*, and this file exists only to demonstrate the
interface.

Shape: an evening-peaked all-electric household, 13 months of hourly readings, with a
summer cooling bump and a winter heating bump, mild weekend/weekday variation, and
deterministic pseudo-random jitter so it does not look machine-flat.
"""

from __future__ import annotations

import datetime as dt
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "sample-usage.csv"
START = dt.date(2025, 7, 1)
END = dt.date(2026, 7, 31)
SEED = 20260908

# Hour-of-day multipliers: overnight trough, small morning bump, strong 5-9 p.m. evening.
SHAPE = [
    0.55,
    0.48,
    0.44,
    0.42,
    0.42,
    0.50,  # 00-05
    0.70,
    0.95,
    0.85,
    0.65,
    0.58,
    0.56,  # 06-11
    0.58,
    0.62,
    0.68,
    0.80,
    1.05,
    1.55,  # 12-17
    1.85,
    1.80,
    1.45,
    1.10,
    0.85,
    0.65,  # 18-23
]


def _is_spring_forward(d: dt.date) -> bool:
    """Second Sunday in March: the local day with only 23 hours."""
    return d.month == 3 and d.weekday() == 6 and 8 <= d.day <= 14


def _seasonal(d: dt.date) -> float:
    """Cooling peak in late summer, heating bump in winter, mild shoulders."""
    doy = d.timetuple().tm_yday
    cooling = 0.45 * max(0.0, math.sin((doy - 100) / 365 * 2 * math.pi))
    heating = 0.30 * max(0.0, math.cos(doy / 365 * 2 * math.pi))
    return 1.0 + cooling + heating


def main() -> int:
    rng = random.Random(SEED)
    lines = [
        "﻿",
        "",
        "Name,SAMPLE HOUSEHOLD (SYNTHETIC - NOT REAL METER DATA)",
        'Address,"1 EXAMPLE ST, ANYTOWN CA 900000000"',
        "Account Number,0000000000",
        "Service,Service 1",
        "",
        "TYPE,DATE,START TIME,END TIME,USAGE (kWh),COST,NOTES",
    ]

    d = START
    total = 0.0
    while d <= END:
        season = _seasonal(d)
        weekend = 1.12 if d.weekday() >= 5 else 1.0
        for h in range(24):
            # PG&E's real export carries 02:00 and omits 03:00 on the spring-forward day.
            if _is_spring_forward(d) and h == 3:
                continue
            kwh = 0.42 * SHAPE[h] * season * weekend * rng.uniform(0.82, 1.18)
            total += kwh
            lines.append(f"Electric usage,{d.isoformat()},{h:02d}:00,{h:02d}:59,{kwh:.3f},$0.00,")
        d += dt.timedelta(days=1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    days = (END - START).days + 1
    print(
        f"wrote {OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT} "
        f"— {days} days, {total:,.0f} kWh, {total / days:.1f} kWh/day"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
