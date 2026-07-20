"""Extract anonymized golden-bill fixtures from real PG&E bill PDFs.

Dev tool, run manually. Reads the git-ignored `data/*.pdf` statements and writes
committable, PII-free fixtures to `tests/golden_bills/`. The fixtures are the
regression targets the reconciliation harness checks the engine against.

Anonymization: only statement date, billing period, per-line dollar amounts, and the
schedule identity survive. No name, address, account/meter number, or usage-by-day.

Usage:  python scripts/extract_golden_bills.py [--write]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pypdf
import yaml

DATA = Path("data")
OUT = Path("tests/golden_bills")

# Canonical line names — must match the names emitted by tariffs.bill.compute_layer.
PCIA = "Power Charge Indifference Adjustment (2018 vintage)"
GEN_CREDIT = "Generation Credit (PG&E generation not supplied)"
UUT = "City of Santa Cruz Utility Users' Tax"

_NUM = r"(-?\d+\.\d\d)"


def _text(pdf: Path) -> str:
    r = pypdf.PdfReader(str(pdf))
    return "\n".join((p.extract_text() or "") for p in r.pages)


def _sum(pattern: str, text: str) -> float | None:
    """Sum the trailing amount of every match (season-split bills repeat lines)."""
    vals = [float(m) for m in re.findall(pattern, text)]
    return round(sum(vals), 2) if vals else None


def _one(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def extract(pdf: Path) -> dict | None:
    t = _text(pdf)
    stmt = _one(r"Statement Date:\s*([\d/]+)", t)
    period = re.search(
        r"Details of PG&E Electric Delivery Charges\s+"
        r"(\d\d)/(\d\d)/(\d{4}) to (\d\d)/(\d\d)/(\d{4})",
        t,
    )
    if not stmt or not period:
        return None  # not machine-readable (earliest image-based statements)
    ms, ds, ys, me, de, ye = period.groups()

    # Scope amount patterns to their bill section so identical labels (UUT) don't cross.
    d0 = t.find("Details of PG&E Electric Delivery Charges")
    g0 = t.find("Details of Central Coast Community Energy")
    gas0 = t.find("Details of Gas Charges")
    gas0 = gas0 if gas0 >= 0 else len(t)
    deliv_sec = t[d0:g0] if g0 >= 0 else t[d0:gas0]
    gen_sec = t[g0:gas0] if g0 >= 0 else ""
    uut = rf"City of Santa Cruz Utility Users' Tax \(8\.500%\)\s+\$?{_NUM}"

    delivery = {
        "Base Services Charge": _sum(rf"Base Services Charge[^\n]*?@\$[\d.]+ \$?{_NUM}", deliv_sec),
        "Energy Peak": _sum(rf"Energy Charges Peak [\d.]+kWh@\$[\d.]+ {_NUM}", deliv_sec),
        "Energy Off Peak": _sum(rf"Off Peak [\d.]+kWh@\$[\d.]+ {_NUM}", deliv_sec),
        "Baseline Credit": _sum(rf"Baseline Credit\s+[\d.]+kWh@-?\$?[\d.]+ {_NUM}", deliv_sec),
        "CARE Discount": _sum(rf"CARE Discount\s+{_NUM}", deliv_sec),
        PCIA: _sum(rf"(?<!Vintaged )Power Charge Indifference Adjustment\s+{_NUM}", deliv_sec),
        GEN_CREDIT: _sum(rf"Generation Credit\s+{_NUM}", deliv_sec),
        "Franchise Fee Surcharge": _sum(rf"Franchise Fee Surcharge\s+{_NUM}", deliv_sec),
        UUT: _sum(uut, deliv_sec),
    }
    delivery_total = _one(rf"Total PG&E Electric Delivery Charges\s*\$?{_NUM}", t)

    generation = {
        "Energy Peak": _sum(rf"Generation - Peak - \w+\s+[\d.]+kWh@\$[\d.]+ \$?{_NUM}", gen_sec),
        "Energy Off Peak": _sum(
            rf"Generation - Off Peak - \w+\s+[\d.]+kWh@\$[\d.]+ \$?{_NUM}", gen_sec
        ),
        "Energy Commission Tax": _sum(rf"Energy Commission Tax\s+{_NUM}", gen_sec),
        UUT: _sum(uut, gen_sec),
    }
    generation_total = _one(
        rf"Total Central Coast Community Energy Electric Generation Charges\s*\$?{_NUM}", t
    )

    # Observed adjustments from the account summary.
    deliv_adj = _one(rf"Electric Adjustments\s*-?{_NUM}", t)
    gen_adj = _one(rf"Service Provider Electric Commodity Adjustments\s*-?{_NUM}", t)
    deliv_adj = -abs(float(deliv_adj)) if deliv_adj else None
    gen_adj = -abs(float(gen_adj)) if gen_adj else None

    dt = float(delivery_total) if delivery_total else 0.0
    gt = float(generation_total) if generation_total else 0.0
    net = round(dt + gt + (deliv_adj or 0) + (gen_adj or 0), 2)

    return {
        "statement_date": stmt.replace("/", "-"),
        "period_start": f"{ys}-{ms}-{ds}",
        "period_end": f"{ye}-{me}-{de}",
        "utility": "PG&E",
        "customer_class": "CARE",
        "specs": {"delivery": "E-TOU-C", "generation": "MBRETCH1"},
        "expected": {
            "delivery": {
                "line_items": {k: v for k, v in delivery.items() if v is not None},
                "total": round(dt, 2),
            },
            "generation": {
                "line_items": {k: v for k, v in generation.items() if v is not None},
                "total": round(gt, 2),
            },
            "observed_adjustments": {
                "UUT Adjustment (delivery, observed)": deliv_adj,
                "UUT Adjustment (generation, observed)": gen_adj,
            },
            "electric_net_total": net,
        },
        "tolerance_dollars": 2.00,
        "source": f"PG&E statement {stmt} (anonymized; no PII).",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write fixtures (else dry-run)")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for pdf in sorted(DATA.glob("*.pdf")):
        fx = extract(pdf)
        if not fx:
            print(f"skip (unreadable): {pdf.name}")
            continue
        # self-check: extracted line items must sum to the extracted layer total,
        # else the parse is unreliable (pre-March-2026 bills have a different
        # structure and need their own spec version — skip until then).
        ok = True
        for layer in ("delivery", "generation"):
            li = fx["expected"][layer]["line_items"]
            tot = fx["expected"][layer]["total"]
            s = round(sum(li.values()), 2)
            bad = abs(s - tot) >= 0.03
            ok = ok and not bad
            print(
                f"  {fx['statement_date']} {layer:<10} lines={len(li)} sum={s} total={tot}"
                + ("  <<< MISMATCH" if bad else "")
            )
        if not ok:
            print(f"    -> SKIP {fx['statement_date']} (parse self-check failed; likely pre-IGFC)")
            continue
        name = f"pge_{fx['statement_date']}.yaml"
        if args.write:
            (OUT / name).write_text(yaml.safe_dump(fx, sort_keys=False))
        n += 1
    print(f"\n{'wrote' if args.write else 'previewed'} {n} fixtures to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
