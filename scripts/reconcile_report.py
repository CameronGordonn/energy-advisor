"""Print the golden-bill line-item comparisons and regenerate the README table.

Run manually (needs the git-ignored interval export in data/):
    python scripts/reconcile_report.py [--write-readme]

Utility-general: each fixture names its own utility, and the interval export and parser
are selected from that. A utility whose export is not in data/ is skipped with a note
rather than failing the run, so one missing file cannot hide another utility's results.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from greenbutton.models import IntervalSeries
from report.reconcile import (
    GOLDEN_DIR,
    fixture_utility,
    format_comparison,
    interval_file_for,
    load_fixture,
    parse_interval_file,
    reconcile,
)

README = Path("README.md")
START = "<!-- RECONCILIATION-TABLE:START -->"
END = "<!-- RECONCILIATION-TABLE:END -->"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-readme", action="store_true")
    args = ap.parse_args()

    fixtures = [(p, load_fixture(p)) for p in sorted(GOLDEN_DIR.glob("*.yaml"))]
    series_by_utility: dict[str, IntervalSeries | None] = {}
    results = []
    skipped: dict[str, int] = {}

    for path, fixture in fixtures:
        utility = fixture_utility(fixture)
        if utility not in series_by_utility:
            f = interval_file_for(utility)
            series_by_utility[utility] = parse_interval_file(utility, f)[0] if f else None
        series = series_by_utility[utility]
        if series is None:
            skipped[utility.value] = skipped.get(utility.value, 0) + 1
            continue
        r = reconcile(fixture, series, name=path.name)
        results.append(r)
        print(format_comparison(r))
        print()

    for utility, n in sorted(skipped.items()):
        print(f"skipped {n} {utility} fixture(s): no {utility} interval export in data/")
    if not results:
        print("no interval export in data/ — cannot reconcile", file=sys.stderr)
        return 1

    n_pass = sum(r.within_tolerance for r in results)
    print(f"{n_pass}/{len(results)} bills within tolerance")

    rows = [
        "| Utility | Schedule | Bill period | Actual $ | Modeled $ | Δ $ | Within ±$2 |",
        "|---------|----------|-------------|---------:|----------:|----:|:----------:|",
    ]
    for r in sorted(results, key=lambda x: (x.utility, x.period_start)):
        mark = "✅" if r.within_tolerance else "❌"
        rows.append(
            f"| {r.utility} | {r.schedule_label} | {r.period_start} → {r.period_end} "
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
