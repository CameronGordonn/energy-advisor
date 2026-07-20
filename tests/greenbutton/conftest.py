"""Fixture builders that emit PG&E-format Green Button CSV text.

All synthetic — no real usage data, so these fixtures are committable. The real
export lives in the git-ignored ``data/`` and is exercised separately by a
skip-if-absent smoke test.
"""

from __future__ import annotations

BOM = "﻿"

_META = [
    "",
    "Name,TEST CUSTOMER",
    'Address,"1 TEST ST APT A, SANTA CRUZ CA 950601234"',
    "Account Number,7355849999",
    "Service,Service 1",
    "",
]


def interval_csv(
    rows: list[tuple[str, str, str, float, str]],
    *,
    usage_header: str = "USAGE (kWh)",
    type_label: str = "Electric usage",
    with_notes: bool = True,
) -> str:
    """rows: (date, start_hhmm, end_hhmm, usage, notes)."""
    header = ["TYPE", "DATE", "START TIME", "END TIME", usage_header, "COST"]
    if with_notes:
        header.append("NOTES")
    out = [BOM.rstrip("\n"), *(_META), ",".join(header)]
    for date, start, end, usage, notes in rows:
        cells = [type_label, date, start, end, f"{usage}", "$0.00"]
        if with_notes:
            cells.append(notes)
        out.append(",".join(cells))
    return "\n".join(out) + "\n"


def billing_csv() -> str:
    """The *wrong* file: a billing-history export the parser must reject."""
    return (
        BOM
        + "\n".join(
            [
                "",
                "Name,TEST CUSTOMER",
                'Address,"1 TEST ST, SANTA CRUZ CA 95060"',
                "Account Number,7355849999",
                "Service,Service 1",
                "",
                "TYPE,START DATE,END DATE,USAGE (kWh),COST,NOTES",
                "Electric billing,2025-08-02,2025-08-25,241.47,$35.51,",
            ]
        )
        + "\n"
    )


def hourly_day(
    date: str,
    *,
    usage: float = 0.10,
    skip: set[str] | None = None,
    notes: dict[str, str] | None = None,
) -> list[tuple[str, str, str, float, str]]:
    """24 hourly rows (PG&E inclusive-minute END, e.g. 00:00-00:59).

    ``skip`` drops rows by their START hour ("HH:00"); ``notes`` sets NOTES text
    per START hour.
    """
    skip = skip or set()
    notes = notes or {}
    rows = []
    for h in range(24):
        start = f"{h:02d}:00"
        if start in skip:
            continue
        rows.append((date, start, f"{h:02d}:59", usage, notes.get(start, "")))
    return rows


def write(tmp_path, text: str, name: str = "usage.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p
