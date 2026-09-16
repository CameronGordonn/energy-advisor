"""The worked example the site ships, and the two hooks that stop it going stale.

`docs/case-study.json` is generated from the author's real PG&E export, which lives in
gitignored `data/` and can never be in CI. That makes it the repo's classic hazard: a
committed artifact nothing can rebuild, and therefore nothing can notice ageing. The
mitigations are here rather than in a comment, because a comment is not a gate.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "docs" / "case-study.json"
BUNDLE = ROOT / "docs" / "engine.js"


@pytest.fixture(scope="module")
def case() -> dict:
    return json.loads(CASE.read_text(encoding="utf-8"))


def test_the_case_study_was_built_by_the_engine_the_site_now_ships(case):
    """⭐ The invalidation hook. The example is generated from data CI cannot see, so the
    only thing that can catch it drifting is the digest of the engine that produced it.

    When this fails, the shipped bundle has moved and the published example was computed by
    an older one — i.e. the site would be showing numbers its own engine no longer produces.
    Regenerate it:  PYTHONPATH=src python scripts/build_case_study.py
    """
    shipped = re.search(r'window\.ENERGY_ENGINE_DIGEST = "([0-9a-f]+)"', BUNDLE.read_text())
    assert shipped, "no digest in docs/engine.js"
    assert case["provenance"]["engine_digest"] == shipped.group(1), (
        "docs/case-study.json was built by a different engine than docs/engine.js ships. "
        "Rebuild it: PYTHONPATH=src python scripts/build_case_study.py"
    )


def test_the_published_example_is_the_reconciled_household_and_says_so(case):
    prov = case["provenance"]
    assert "±$2" in prov["reconciliation"]
    assert "11 of 11" in prov["reconciliation"]
    # The facts are the ones the specs actually describe; if they ever drift out of the
    # authored scope the build script refuses, but pin the household here too.
    assert prov["facts"]["baseline_territory"] == "T"
    assert prov["facts"]["supplier"] == "3CE"


def test_the_example_recommendation_is_internally_consistent(case):
    """Arithmetic the file must satisfy on its own terms, with no access to the raw export."""
    rec = case["recommendation"]
    assert rec["available"] is True and not rec["blockers"]

    totals = [p["annual"] for p in rec["plans"]]
    assert totals == sorted(totals), "the ranking is not ordered cheapest-first"

    current = [p for p in rec["plans"] if p["is_current"]]
    assert len(current) == 1, "the example household must be on exactly one of the plans"
    base = current[0]["annual"]
    for plan in rec["plans"]:
        assert plan["delta_vs_current"] == pytest.approx(round(plan["annual"] - base, 2), abs=0.01)


def test_the_example_carries_its_own_caveats(case):
    """A published dollar figure without its assumptions is the thing this project is against."""
    rec = case["recommendation"]
    assert len(rec["assumptions"]) >= 3
    assert any("UNVERIFIED" in a for a in rec["assumptions"])
    assert rec["why"], "no component-level explanation of the winner"
    assert rec["verdict"].strip()


def test_the_example_publishes_no_identifying_field(case):
    """`data/` never enters git; the derived analysis must not smuggle the household in.

    The parser deliberately keeps a masked account tail and the ZIP (the ZIP changes the
    baseline arithmetic). Neither belongs in a file served to the public.
    """
    blob = json.dumps(case)
    assert "account_tail" not in blob
    assert "address_zip" not in blob
    assert not re.search(r"\b\d{5}(-\d{4})?\b", case["inspection"].get("source_name", ""))
