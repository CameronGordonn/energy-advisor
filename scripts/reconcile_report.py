"""Print the golden-bill line-item comparisons and regenerate the README table.

Run manually (needs the git-ignored interval export in data/):
    python scripts/reconcile_report.py [--write-readme]
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

from greenbutton import parse_pge_interval_csv
from report.reconcile import GOLDEN_DIR, format_comparison, load_fixture, reconcile

README = Path("README.md")
START = "<!-- RECONCILIATION-TABLE:START -->"
END = "<!-- RECONCILIATION-TABLE:END -->"


def _interval_file() -> str | None:
    m = sorted(glob.glob("data/pge_electric_usage_interval_data*.csv"))
    return m[0] if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-readme", action="store_true")
    args = ap.parse_args()

    f = _interval_file()
    if not f:
        print("no interval export in data/ — cannot reconcile", file=sys.stderr)
        return 1
    series, _ = parse_pge_interval_csv(f)

    results = []
    for fx_path in sorted(GOLDEN_DIR.glob("*.yaml")):
        r = reconcile(load_fixture(fx_path), series)
        results.append(r)
        print(format_comparison(r))
        print()

    n_pass = sum(r.within_tolerance for r in results)
    print(f"{n_pass}/{len(results)} bills within tolerance")

    rows = [
        "| Utility | Schedule | Bill period | Actual $ | Modeled $ | Δ $ | Within ±$2 |",
        "|---------|----------|-------------|---------:|----------:|----:|:----------:|",
    ]
    for r in sorted(results, key=lambda x: x.period_start):
        mark = "✅" if r.within_tolerance else "❌"
        rows.append(
            f"| PG&E | E-TOU-C + 3CE (CARE) | {r.period_start} → {r.period_end} "
            f"| {r.net_bill:.2f} | {r.net_modeled:.2f} | {r.delta:+.2f} | {mark} |"
        )
    table = "\n".join(rows)
    print("\n" + table)

    if args.write_readme:
        text = README.read_text()
        pre, rest = text.split(START)
        _, post = rest.split(END)
        README.write_text(f"{pre}{START}\n{table}\n{END}{post}")
        print(f"\nupdated {README}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
