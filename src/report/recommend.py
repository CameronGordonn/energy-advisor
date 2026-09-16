"""Whether this household can be given a dollar figure at all — and if so, which plan.

The tool has always stopped at load shape. The reason usually given is invariant 1
(reconciliation-gated), and that reason is **incomplete**: the PG&E path *is* reconciled,
11 of 11 real statements within ±$2. If invariant 1 were the only obstacle, a PG&E visitor
could be ranked today.

The real obstacle is narrower and shows up in the spec files themselves. The PG&E delivery
specs are **one household's** specs:

* ``baseline.territory: T`` with the all-electric allowance — Santa Cruz, Heat Source H.
  A PG&E customer in Territory X or R has a different allowance and a different credit, so
  the same YAML priced against their file produces a confident number that is wrong.
* the PCIA adder is a single vintage (2018), *derived from one household's statements*.
* the CCA half of every candidate is 3CE, which serves Monterey Bay. A visitor on MCE, Ava,
  SVCE, Peninsula or SJCE has no authored generation layer at all.
* the Utility Users' Tax adjustment is fitted to Santa Cruz bills and its mechanism is
  UNVERIFIED (HANDOFF open decision 5).

So the honest statement is not "we don't price anything", it is **"we can price the
households the specs actually describe, and we can say precisely why yours is not one of
them"**. That is what this module computes: a scope read *out of the spec files* rather
than written down here, the list of reasons a given household falls outside it, and — when
it falls inside — the ranking, the verdict, the component-level why, and the shift that
would overturn it.

Nothing here invents a rate. A household outside the scope gets blockers and no numbers,
which is the honest-broker invariant (2) applied to the visitor rather than to the
recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from greenbutton.models import IntervalSeries, Utility
from scenarios.rate_optimizer import (
    ALL_PGE_CANDIDATES,
    EVENING_HOURS,
    Candidate,
    PlanCost,
    eligible_candidates,
    explain,
    flip_factor,
    periods_from_series,
    rank,
)

#: Utilities whose bill engine has met the ±$2 reconciliation gate against real statements.
#: **Not a preference — a measurement.** ``tests/report/test_recommend.py`` ties this to the
#: golden-bill corpus: a utility may appear here only if it has at least three committed
#: fixtures, and a utility with none may not appear at all. Adding SDG&E by editing this
#: line fails that test rather than quietly switching dollars on for San Diego.
RECONCILED_UTILITIES = frozenset({Utility.PGE})

#: The minimum number of reconciled statements behind a utility before it earns dollars.
#: Matches M0's DoD ("last 3 actual bills") and M1a's.
RECONCILED_BILL_MINIMUM = 3


class Blocker(BaseModel):
    """One reason this household cannot be shown a dollar figure.

    ``code`` is stable and testable; ``detail`` is what the page shows a human. Both are
    required — a blocker that cannot be explained to the visitor is not honest, and one
    that cannot be asserted in a test rots.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    detail: str


@dataclass(frozen=True)
class AuthoredScope:
    """The households the committed specs actually describe, read from the specs.

    Derived rather than declared, so that authoring a second baseline territory or a new
    CCA widens the tool's reach the moment the YAML lands — and so this module cannot
    claim coverage the spec files do not have.
    """

    utility: Utility
    territories: frozenset[str]
    all_electric: bool
    suppliers: frozenset[str]
    pcia_vintages: frozenset[str]

    def describes(self, facts: HouseholdFacts) -> bool:
        return not scope_blockers(facts, self)


class HouseholdFacts(BaseModel):
    """What the tariff specs demand and a Green Button file cannot tell you.

    The file carries usage, not tariff status. Every field here is something only the
    customer (or their bill) knows, and each one changes the dollars. They are asked for
    rather than defaulted, which is the same raise-don't-default rule the bill engine
    applies to ``territory``, ``vintage``, ``service`` and ``event_days``.
    """

    model_config = ConfigDict(frozen=True)

    care: bool
    """CARE/FERA discount status. Worth ~35% of the bill, so a wrong default is not small."""

    supplier: str
    """Generation supplier as the customer's bill names it — ``3CE``, ``PG&E``, ``MCE``…"""

    baseline_territory: str
    """PG&E/SDG&E baseline territory letter, off the bill. Sets the allowance and credit."""

    all_electric: bool
    """Whether the account takes the all-electric (Heat Source H) baseline."""

    has_ev: bool = False
    """EV2-A is only available with a plug-in EV; ranking it for a household without one
    would put an ineligible plan at the top, which invariant 2 exists to prevent."""

    current_plan: str | None = None
    """The plan they are on now, if they know it. Without it there is a ranking but no
    savings claim — a delta against an unknown baseline is a number with no meaning."""


class RankedPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    annual: float
    delta_vs_current: float | None = None
    eligibility: str | None = None
    is_current: bool = False


class Recommendation(BaseModel):
    """The answer, or the reason there isn't one. JSON-serializable for any front end."""

    model_config = ConfigDict(frozen=True)

    available: bool
    blockers: list[Blocker] = Field(default_factory=list)

    utility: Utility | None = None
    days_modeled: int = 0
    as_of: str | None = None

    verdict: str = ""
    """One sentence, and it must be capable of saying "stay where you are"."""

    plans: list[RankedPlan] = Field(default_factory=list)
    why: list[tuple[str, float]] = Field(default_factory=list)
    """Component-level attribution of the winner's margin over the runner-up."""

    flip_factor_evening: float | None = None
    """Multiplier on 16:00-21:00 usage at which the runner-up overtakes the winner.
    ``None`` means the ranking does not flip on evening usage alone, which is a result."""

    assumptions: list[str] = Field(default_factory=list)


# --- what the specs actually cover -------------------------------------------------------


def authored_scope(
    utility: Utility = Utility.PGE, *, specs_dir: str | Path = "src/tariffs/specs"
) -> AuthoredScope:
    """Read the coverage of the committed delivery specs off the YAML.

    Deliberately not a constant. The whole point is that the scope widens when specs are
    authored, and a hand-maintained copy of it would be a cached value with no
    invalidation — the failure this repo keeps correcting.
    """
    prefix = "pge_" if utility is Utility.PGE else "sdge_"
    territories: set[str] = set()
    vintages: set[str] = set()
    all_electric = False
    suppliers: set[str] = set()

    for path in sorted(Path(specs_dir).glob(f"{prefix}*.yaml")):
        doc = yaml.safe_load(path.read_text()) or {}
        baseline = doc.get("baseline") or {}
        if "territory" in baseline:
            territories.add(str(baseline["territory"]))
            # ⚠ SCHEMA GAP, surfaced rather than papered over: the baseline block records
            # the TERRITORY as data but the HEAT SOURCE only as a YAML comment
            # ("Territory T, all-electric (Heat Source H)"). Nothing in the loaded spec can
            # be gated on it, so this reads the raw text. A spec that stops mentioning its
            # heat source silently widens the claimed scope, which is why the test suite
            # pins the value this returns today.
            all_electric = all_electric or "all-electric" in path.read_text().lower()
        for adder in doc.get("adders") or []:
            name = str(adder.get("name", ""))
            if "Power Charge Indifference" in name:
                digits = "".join(ch for ch in name if ch.isdigit())
                if digits:
                    vintages.add(digits)

    for candidate in ALL_PGE_CANDIDATES if utility is Utility.PGE else ():
        suppliers.add("PG&E" if candidate.generation.startswith("PGE-BUNDLED") else "3CE")

    return AuthoredScope(
        utility=utility,
        territories=frozenset(territories),
        all_electric=all_electric,
        suppliers=frozenset(suppliers),
        pcia_vintages=frozenset(vintages),
    )


def scope_blockers(facts: HouseholdFacts, scope: AuthoredScope) -> list[Blocker]:
    """Why these specs do not describe this household. Empty means they do."""
    out: list[Blocker] = []

    if facts.baseline_territory not in scope.territories:
        out.append(
            Blocker(
                code="TERRITORY_NOT_AUTHORED",
                detail=(
                    f"The committed {scope.utility.value} specs carry the baseline allowance "
                    f"for territory {', '.join(sorted(scope.territories)) or 'none'} only, and "
                    f"this account is in territory {facts.baseline_territory}. The allowance "
                    "and the baseline credit both change with territory, so pricing it "
                    "against the wrong one would be wrong by real money rather than "
                    "approximately right."
                ),
            )
        )
    elif scope.all_electric and not facts.all_electric:
        out.append(
            Blocker(
                code="HEAT_SOURCE_NOT_AUTHORED",
                detail=(
                    "The authored baseline is the all-electric (Heat Source H) allowance. "
                    "A basic-allowance household gets a different quantity of baseline kWh "
                    "at a different credit, and that difference is not modelled."
                ),
            )
        )

    if facts.supplier not in scope.suppliers:
        out.append(
            Blocker(
                code="SUPPLIER_NOT_AUTHORED",
                detail=(
                    f"Generation layers exist for {', '.join(sorted(scope.suppliers))}. "
                    f"{facts.supplier} has none, and a CCA's generation rates are its own "
                    "published schedule — they cannot be inferred from the utility's."
                ),
            )
        )

    return out


def utility_blocker(utility: Utility) -> Blocker | None:
    """The reconciliation gate alone, answerable before any household fact is known.

    Separate from :func:`blockers_for` because a front end must be able to refuse an
    SDG&E visitor *without first asking them for their tariff status* — collecting
    answers it has already decided not to use would be a worse kind of dishonest than
    showing the wrong number.
    """
    if utility in RECONCILED_UTILITIES:
        return None
    return Blocker(
        code="UTILITY_NOT_RECONCILED",
        detail=(
            f"The bill engine has never reproduced a real {utility.value} statement "
            "within ±$2, because no such statement has ever been available to test "
            "it against. Until one is, this tool shows "
            f"{utility.value} customers no dollar figure at all — not a hedged one, "
            "not a range. The rates are transcribed and tested against the "
            "utility's own published figures; that is corroboration, not proof."
        ),
    )


def blockers_for(
    utility: Utility, facts: HouseholdFacts, scope: AuthoredScope | None = None, **kw
) -> list[Blocker]:
    """Every reason this household cannot be shown dollars, gate first."""
    gate = utility_blocker(utility)
    if gate is not None:
        return [gate]
    return scope_blockers(facts, scope or authored_scope(utility, **kw))


# --- the recommendation ------------------------------------------------------------------


def _verdict(plans: list[PlanCost], facts: HouseholdFacts) -> str:
    winner, runner_up = plans[0], plans[1]
    margin = round(runner_up.total - winner.total, 2)
    if facts.current_plan is None:
        return (
            f"{winner.name} is the cheapest of the {len(plans)} plans modelled on your own "
            f"usage, by ${margin:,.2f}/yr over {runner_up.name}. You have not said which "
            "plan you are on, so this is a ranking, not a saving."
        )
    current = next((p for p in plans if p.name == facts.current_plan), None)
    if current is None:
        return (
            f"{winner.name} is the cheapest of the {len(plans)} plans modelled. Your current "
            f"plan ({facts.current_plan}) is not among them, so no saving is claimed."
        )
    if current.name == winner.name:
        return (
            f"Stay where you are. {winner.name} is already the cheapest of the "
            f"{len(plans)} plans modelled on your usage — the nearest alternative "
            f"({runner_up.name}) costs ${margin:,.2f}/yr more."
        )
    saving = round(current.total - winner.total, 2)
    return (
        f"Switching from {current.name} to {winner.name} would have cost ${saving:,.2f} less "
        f"over the {current.days} days modelled, on your own usage."
    )


def _compare_against(plans: list[PlanCost], facts: HouseholdFacts) -> PlanCost:
    """The plan the winner should be explained against: theirs if known, else the runner-up."""
    current = next((p for p in plans if p.name == facts.current_plan), None)
    if current is not None and current.name != plans[0].name:
        return current
    return plans[1]


def recommend(
    series: IntervalSeries,
    facts: HouseholdFacts,
    *,
    utility: Utility,
    as_of: date,
    specs_dir: str | Path = "src/tariffs/specs",
    candidates: tuple[Candidate, ...] = ALL_PGE_CANDIDATES,
    with_sensitivity: bool = True,
) -> Recommendation:
    """Rank every eligible plan on this household's own intervals, or say why not.

    Returns a :class:`Recommendation` with ``available=False`` and populated ``blockers``
    rather than raising, because the refusal is the product: a visitor the engine cannot
    price is owed the reason, not an exception.
    """
    scope = authored_scope(utility, specs_dir=specs_dir)
    found = blockers_for(utility, facts, scope)
    if found:
        return Recommendation(available=False, blockers=found, utility=utility)

    periods = periods_from_series(series)
    pool = eligible_candidates(candidates, has_ev=facts.has_ev)
    plans = rank(
        series,
        periods,
        care=facts.care,
        as_of=as_of,
        candidates=pool,
        specs_dir=str(specs_dir),
    )

    by_name = {c.name: c for c in pool}
    flip = None
    if with_sensitivity and len(plans) > 1:
        flip = flip_factor(
            series,
            periods,
            by_name[plans[0].name],
            by_name[plans[1].name],
            care=facts.care,
            as_of=as_of,
            hours=EVENING_HOURS,
            specs_dir=str(specs_dir),
        )

    current_total = next((p.total for p in plans if p.name == facts.current_plan), None)
    ranked = [
        RankedPlan(
            name=p.name,
            annual=p.total,
            delta_vs_current=(None if current_total is None else round(p.total - current_total, 2)),
            eligibility=p.eligibility,
            is_current=p.name == facts.current_plan,
        )
        for p in plans
    ]

    assumptions = [
        "Every plan is billed at the rates in effect on "
        f"{as_of.isoformat()}, not at the rates each month actually saw — the question is "
        "what to be on going forward.",
        "Billing periods are modelled as fixed 30-day windows unless real meter-read dates "
        "were supplied; per-day fixed charges shift slightly with the real ones.",
        "The Santa Cruz Utility Users' Tax adjustment is a fitted per-day credit whose "
        "mechanism is UNVERIFIED. It is schedule-independent, so it moves every plan's "
        "total by the same amount and cannot reorder this ranking.",
    ]
    if any(p.eligibility for p in plans):
        assumptions.append(
            "Plans with an eligibility condition are ranked only because you said the "
            "condition applies to you."
        )

    return Recommendation(
        available=True,
        utility=utility,
        days_modeled=plans[0].days,
        as_of=as_of.isoformat(),
        verdict=_verdict(plans, facts),
        plans=ranked,
        # Explain the winner against the plan they are ON where that is known: "why is
        # this cheaper than what I have" is the question, and the runner-up is only the
        # right comparison when there is nothing to compare against.
        why=(explain(plans[0], _compare_against(plans, facts)) if len(plans) > 1 else []),
        flip_factor_evening=flip,
        assumptions=assumptions,
    )
