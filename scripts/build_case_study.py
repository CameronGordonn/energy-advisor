#!/usr/bin/env python
"""Generate the worked example the public tool shows — from the real reconciled household.

    PYTHONPATH=src python scripts/build_case_study.py

The site used to demonstrate itself with an invented load profile and no dollar figures,
which made the tool look like a chart viewer. It is not: the PG&E path reproduces 11 of 11
real statements within ±$2, so there is exactly one household on earth whose dollars this
project has earned the right to publish — the author's own, already published in full on
the methodology page by the session-7 self-attribution decision.

So the example is that household, run through the same engine a visitor's file goes
through, and the output is committed as ``docs/case-study.json``. The raw export stays in
``data/`` and is never committed (privacy); what ships is the *derived* analysis, at the
same granularity `docs/METHODOLOGY.md` already prints.

**The invalidation problem this file creates, and what handles it.** A committed artifact
generated from gitignored data cannot be rebuilt in CI, so it is the classic cached value
with nothing to notice it going stale. Two hooks, both in `tests/report/test_case_study.py`:
the JSON records the engine bundle's digest, and a test fails when the bundle moves without
the case study being regenerated; and the numbers are checked for internal consistency
(ranking ordered, deltas arithmetic, the verdict naming the plans it compares).
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from datetime import date
from pathlib import Path

from greenbutton.models import Utility
from greenbutton.pge import parse_pge_interval_csv
from report.inspect import inspect_export
from report.recommend import HouseholdFacts, recommend

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "case-study.json"

#: The household, stated rather than guessed — every one of these is off his own bills.
#: Santa Cruz, PG&E delivery, 3CE generation, CARE, baseline territory T all-electric.
FACTS = HouseholdFacts(
    care=True,
    supplier="3CE",
    baseline_territory="T",
    all_electric=True,
    has_ev=False,
    current_plan="E-TOU-C + 3CE",
)

AS_OF = date(2026, 7, 1)


def engine_digest() -> str:
    """The digest ``scripts/build_web_engine.py`` stamped into the shipped bundle."""
    text = (ROOT / "docs" / "engine.js").read_text(encoding="utf-8")
    match = re.search(r'window\.ENERGY_ENGINE_DIGEST = "([0-9a-f]+)"', text)
    if not match:
        raise SystemExit("could not read the engine digest from docs/engine.js")
    return match.group(1)


def build(export: Path, *, as_of: date = AS_OF) -> dict:
    series, _report = parse_pge_interval_csv(export)
    inspection = inspect_export(export)
    rec = recommend(series, FACTS, utility=Utility.PGE, as_of=as_of)
    if not rec.available:
        raise SystemExit(
            "the case-study household is outside the authored scope: "
            + "; ".join(b.code for b in rec.blockers)
        )
    return {
        "provenance": {
            "household": (
                "The author's own PG&E account in Santa Cruz — the household the "
                "reconciliation table is built from. Self-attributed by decision; the raw "
                "export is never committed, this derived analysis is."
            ),
            "reconciliation": "11 of 11 real statements within ±$2, worst +$0.22",
            "generated": date.today().isoformat(),
            "engine_digest": engine_digest(),
            "as_of": as_of.isoformat(),
            "facts": FACTS.model_dump(),
        },
        "inspection": json.loads(inspection.model_dump_json()),
        "recommendation": json.loads(rec.model_dump_json()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export", nargs="?", help="PG&E interval CSV (default: newest in data/)")
    args = ap.parse_args()

    path = Path(args.export) if args.export else None
    if path is None:
        found = sorted(glob.glob(str(ROOT / "data" / "pge_electric_usage_interval_data_*.csv")))
        if not found:
            raise SystemExit("no PG&E export in data/ — pass one explicitly")
        path = Path(found[-1])

    OUT.write_text(json.dumps(build(path), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KiB) from {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
