"""The recommendation gate: who gets a dollar figure, who gets a reason instead.

This tier exists because the interesting behaviour of the recommender is what it
*refuses*. A ranking that appears for a household the specs do not describe is worse than
no ranking at all — it is a confident wrong number, which is the failure invariants 1 and 2
exist to prevent — so the refusals are tested first and hardest.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml

from greenbutton.models import Utility
from report.recommend import (
    RECONCILED_BILL_MINIMUM,
    RECONCILED_UTILITIES,
    HouseholdFacts,
    authored_scope,
    blockers_for,
    recommend,
)

from ..tariffs.test_bill import make_series

AS_OF = date(2026, 7, 1)
GOLDEN = Path(__file__).resolve().parents[1] / "golden_bills"

#: The case-study household — the one the committed specs actually describe.
IN_SCOPE = HouseholdFacts(
    care=True,
    supplier="3CE",
    baseline_territory="T",
    all_electric=True,
    current_plan="E-TOU-C + 3CE",
)


# --- the gate ----------------------------------------------------------------------------


def test_reconciled_utilities_is_backed_by_the_golden_bill_corpus():
    """⭐ The list of utilities allowed to show dollars must be a measurement, not an edit.

    Turning dollars on for San Diego is one word in `RECONCILED_UTILITIES`. This is what
    makes that word insufficient: every listed utility has to have at least
    ``RECONCILED_BILL_MINIMUM`` committed golden-bill fixtures, and a utility with none may
    not be listed at all. Someone who adds SDG&E to ship a feature fails here, by name,
    with the reason.
    """
    counts: dict[str, int] = {}
    for fixture in GOLDEN.glob("*.yaml"):
        doc = yaml.safe_load(fixture.read_text()) or {}
        utility = str(doc.get("utility", "")).strip()
        if utility:
            counts[utility] = counts.get(utility, 0) + 1

    for utility in RECONCILED_UTILITIES:
        got = counts.get(utility.value, 0)
        assert got >= RECONCILED_BILL_MINIMUM, (
            f"{utility.value} is listed as reconciled but has {got} golden-bill fixture(s); "
            f"{RECONCILED_BILL_MINIMUM} is the minimum. Reconcile real statements or remove it."
        )

    for utility in Utility:
        if counts.get(utility.value, 0) == 0:
            assert utility not in RECONCILED_UTILITIES, (
                f"{utility.value} has no golden-bill fixture and must not be allowed to "
                "produce a dollar figure (invariant 1)."
            )


def test_sdge_is_refused_and_the_refusal_names_the_gate_not_the_roadmap():
    blockers = blockers_for(Utility.SDGE, IN_SCOPE)
    assert [b.code for b in blockers] == ["UTILITY_NOT_RECONCILED"]
    assert "±$2" in blockers[0].detail
    # The refusal must not read as "coming soon". It states what has not been proved.
    assert "no dollar figure" in blockers[0].detail


def test_a_blocked_recommendation_carries_no_numbers_at_all():
    """Not "hedged numbers" — none. The payload the page renders must be empty of them."""
    rec = recommend(make_series("2026-01-01", 40), IN_SCOPE, utility=Utility.SDGE, as_of=AS_OF)
    assert rec.available is False
    assert rec.plans == [] and rec.why == [] and rec.verdict == ""
    assert rec.flip_factor_evening is None
    dumped = rec.model_dump_json()
    assert "$" not in dumped.replace("±$2", "")


# --- the scope is read from the specs, not declared ---------------------------------------


def test_the_authored_scope_is_what_the_spec_files_say_today():
    scope = authored_scope(Utility.PGE)
    assert scope.territories == frozenset({"T"}), (
        "The PG&E delivery specs carry one baseline territory. If this changed, the tool's "
        "reach changed with it — update the site copy that states the limitation."
    )
    assert scope.all_electric is True
    assert scope.suppliers == frozenset({"3CE", "PG&E"})
    assert scope.pcia_vintages == frozenset({"2018"})


def test_authoring_a_second_territory_widens_the_scope_by_itself(tmp_path):
    """⭐ The scope is derived, so a spec is all it takes to widen it.

    Asserted by building a second specs directory rather than by reading the code: this is
    the difference between a scope that tracks the data and a hand-maintained constant that
    goes stale the first time someone authors a file.
    """
    specs = tmp_path / "specs"
    shutil.copytree("src/tariffs/specs", specs)
    src = specs / "pge_etou_c_delivery_2026-03-01.yaml"
    doc = yaml.safe_load(src.read_text())
    doc["baseline"]["territory"] = "X"
    (specs / "pge_etou_c_delivery_2099-01-01.yaml").write_text(yaml.safe_dump(doc))

    widened = authored_scope(Utility.PGE, specs_dir=specs)
    assert widened.territories == frozenset({"T", "X"})
    assert not blockers_for(
        Utility.PGE,
        IN_SCOPE.model_copy(update={"baseline_territory": "X"}),
        widened,
    )


# --- refusals a visitor will actually hit -------------------------------------------------


@pytest.mark.parametrize(
    ("update", "code"),
    [
        ({"baseline_territory": "X"}, "TERRITORY_NOT_AUTHORED"),
        ({"all_electric": False}, "HEAT_SOURCE_NOT_AUTHORED"),
        ({"supplier": "MCE"}, "SUPPLIER_NOT_AUTHORED"),
    ],
)
def test_a_pge_household_the_specs_do_not_describe_is_refused_by_name(update, code):
    facts = IN_SCOPE.model_copy(update=update)
    rec = recommend(make_series("2026-01-01", 40), facts, utility=Utility.PGE, as_of=AS_OF)
    assert rec.available is False
    assert code in [b.code for b in rec.blockers]
    assert rec.plans == []


def test_the_refusal_explains_the_consequence_not_just_the_gap():
    """A visitor is owed *why it would be wrong*, not "unsupported"."""
    facts = IN_SCOPE.model_copy(update={"baseline_territory": "X"})
    detail = blockers_for(Utility.PGE, facts)[0].detail
    assert "territory X" in detail
    assert "allowance" in detail and "credit" in detail


# --- the answer, when there is one --------------------------------------------------------


def test_an_in_scope_household_gets_a_ranking_a_why_and_the_assumptions():
    rec = recommend(
        make_series("2026-01-01", 62),
        IN_SCOPE,
        utility=Utility.PGE,
        as_of=AS_OF,
        with_sensitivity=False,
    )
    assert rec.available is True and rec.blockers == []
    assert [p.annual for p in rec.plans] == sorted(p.annual for p in rec.plans)
    assert rec.why, "a ranking without a component-level explanation is a number, not advice"
    assert any("UNVERIFIED" in a for a in rec.assumptions)
    assert rec.days_modeled > 0


def test_an_ineligible_plan_is_never_ranked():
    """EV2-A can beat everything on price and still be unavailable. Invariant 2."""
    without_ev = recommend(
        make_series("2026-01-01", 62),
        IN_SCOPE,
        utility=Utility.PGE,
        as_of=AS_OF,
        with_sensitivity=False,
    )
    assert not any("EV2-A" in p.name for p in without_ev.plans)

    with_ev = recommend(
        make_series("2026-01-01", 62),
        IN_SCOPE.model_copy(update={"has_ev": True}),
        utility=Utility.PGE,
        as_of=AS_OF,
        with_sensitivity=False,
    )
    assert any("EV2-A" in p.name for p in with_ev.plans)
    assert any(p.eligibility for p in with_ev.plans)


def test_the_verdict_is_capable_of_saying_stay_where_you_are():
    """⭐ Invariant 2, as an assertion: the tool must be able to answer "do nothing".

    Run once with the cheapest plan named as the household's current one. A recommender
    that cannot produce this sentence is a sales funnel.
    """
    rec = recommend(
        make_series("2026-01-01", 62),
        IN_SCOPE.model_copy(update={"current_plan": None}),
        utility=Utility.PGE,
        as_of=AS_OF,
        with_sensitivity=False,
    )
    cheapest = rec.plans[0].name
    staying = recommend(
        make_series("2026-01-01", 62),
        IN_SCOPE.model_copy(update={"current_plan": cheapest}),
        utility=Utility.PGE,
        as_of=AS_OF,
        with_sensitivity=False,
    )
    assert "Stay where you are" in staying.verdict
    assert staying.plans[0].is_current is True


def test_without_a_current_plan_there_is_a_ranking_but_no_saving_claimed():
    rec = recommend(
        make_series("2026-01-01", 62),
        IN_SCOPE.model_copy(update={"current_plan": None}),
        utility=Utility.PGE,
        as_of=AS_OF,
        with_sensitivity=False,
    )
    assert "not a saving" in rec.verdict
    assert all(p.delta_vs_current is None for p in rec.plans)
