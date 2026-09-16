"""The author-rate-spec extraction schema: does it accept ground truth and reject the gaps?

`.claude/skills/author-rate-spec/extraction-schema.json` is the JSON Schema the generator is
constrained by (CLI-PLAN.md phase B). It exists to close the three gaps CLI-PLAN measured in
`src/tariffs/schema.py` — pydantic enforces structure thoroughly and content not at all:

  1. any non-empty string passes as a `citation`                    -> D2 `evidence`
  2. seasons need not partition the year                            -> D3 `month_to_season`
  3. rates have no bounds, and a Rate with both halves null loads    -> D4

A schema that rejects real cited data is worse than no schema, so the first test here builds
an extraction object from a COMMITTED spec (the CEA generation layer, which has ground truth
and a fetched source) and asserts it validates. The rest assert that each gap is actually
closed, because a constraint nobody tested is a constraint that might not be there.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

REPO = Path(__file__).parents[2]
SCHEMA_PATH = REPO / ".claude/skills/author-rate-spec/extraction-schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def validator(schema) -> object:
    return jsonschema.Draft202012Validator(schema)


def _cite(what: str) -> str:
    return (
        f'Clean Energy Alliance "CEA Adopted Residential Rate Schedule, Effective June 1, '
        f'2026" (corrected 2026-06-30), RESIDENTIAL table, {what}; '
        f"thecleanenergyalliance.org, retrieved 2026-09-08."
    )


def _evidence(span: str) -> dict:
    return {"span": span, "locator": "RESIDENTIAL table, CEA RATE TOU-DR-1 row"}


def _rate(standard: float, span: str) -> dict:
    # CEA bills one generation rate regardless of CARE status, per its own mapping table,
    # so care == standard here. That is read off the sheet, not derived from a discount.
    return {
        "standard": standard,
        "care": standard,
        "citation": _cite("CEA RATE TOU-DR-1"),
        "evidence": _evidence(span),
    }


@pytest.fixture
def ground_truth() -> dict:
    """An extraction object for the committed CEA generation spec.

    Mirrors `src/tariffs/specs/cea_tou_dr1_generation_2026-06-01.yaml` field for field,
    including its negative Rate Relief Credit — the value a naive `exclusiveMinimum: 0`
    on adders would have rejected.
    """
    return {
        "schedule_id": "TOU-DR1",
        "name": "Clean Energy Alliance generation (Clean Impact) matched to SDG&E TOU-DR1",
        "provider": "CEA",
        "layer": "generation",
        "effective_date": "2026-06-01",
        "citation": _cite("CEA RATE TOU-DR-1, generation only"),
        "month_to_season": {
            "1": "winter",
            "2": "winter",
            "3": "winter",
            "4": "winter",
            "5": "winter",
            "6": "summer",
            "7": "summer",
            "8": "summer",
            "9": "summer",
            "10": "summer",
            "11": "winter",
            "12": "winter",
        },
        "season_evidence": _evidence("Summer June 1 - October 31; Winter November 1 - May 31"),
        "tou": {
            "rules": [
                {"period": "on_peak", "hours": [[16, 21]]},
                {"period": "super_off_peak", "hours": [[0, 6], [10, 14]], "days": "weekday"},
                {"period": "super_off_peak", "hours": [[0, 14]], "days": "weekend"},
            ],
            "default_period": "off_peak",
            "holiday_calendar": "sdge_residential",
            "labels": {
                "on_peak": "On-Peak",
                "off_peak": "Off-Peak",
                "super_off_peak": "Super Off-Peak",
            },
        },
        "tou_evidence": _evidence("Super Off-Peak   Midnight - 6am, 10am - 2pm"),
        "energy": {
            "on_peak": {
                "summer": _rate(0.55397, "TOU-DR-1    On-Peak    $0.55397    $0.19791"),
                "winter": _rate(0.19791, "TOU-DR-1    On-Peak    $0.55397    $0.19791"),
            },
            "off_peak": {
                "summer": _rate(0.22298, "TOU-DR-1    Off-Peak   $0.22298    $0.08433"),
                "winter": _rate(0.08433, "TOU-DR-1    Off-Peak   $0.22298    $0.08433"),
            },
            "super_off_peak": {
                "summer": _rate(0.04914, "TOU-DR-1    Super Off-Peak  $0.04914   $0.05138"),
                "winter": _rate(0.05138, "TOU-DR-1    Super Off-Peak  $0.04914   $0.05138"),
            },
        },
        "fixed_per_day": None,
        "adders": [
            {
                "name": "Clean Impact Residential Rate Relief Credit",
                "per_kwh": -0.03871,
                "applies_to": "all",
                "citation": _cite("CLEAN IMPACT RESIDENTIAL RATE RELIEF CREDIT (Per kWh)"),
                "evidence": _evidence(
                    "CLEAN IMPACT RESIDENTIAL RATE RELIEF CREDIT (Per kWh)  -$0.03871  -$0.03871"
                ),
            }
        ],
        "unverified": [],
        "notes": "Opt-up products (Clean Impact Plus, Green Impact) are premiums and are "
        "deliberately not modeled: a customer must actively elect them.",
    }


def test_the_schema_is_itself_a_valid_json_schema(schema):
    jsonschema.Draft202012Validator.check_schema(schema)


def test_it_accepts_a_committed_spec_re_expressed_as_an_extraction(validator, ground_truth):
    """The first thing to get right. A schema that rejects real cited data is worse than none.

    In particular this pins that the adder bound admits a NEGATIVE per-kWh value: CEA's Rate
    Relief Credit is -0.03871/kWh and more than offsets the PCIA an exit-fee-paying customer
    owes, so a bound of `exclusiveMinimum: 0` would have silently made the repo's own ground
    truth unrepresentable.
    """
    assert list(validator.iter_errors(ground_truth)) == []


# --- gap 2 (D3): seasons must partition the year ------------------------------------------


def test_a_month_in_no_season_is_unrepresentable(validator, ground_truth):
    """Under the old two-array shape this raised only at BILL time, and only if a billing
    period touched the missing month — so calibrating on a September bill with a hole in
    March passed clean."""
    broken = deepcopy(ground_truth)
    del broken["month_to_season"]["3"]
    assert list(validator.iter_errors(broken))


def test_a_month_cannot_be_in_both_seasons(validator, ground_truth):
    """The worse of the two: `season_for` tests summer first and returns, so a month in both
    prices at the expensive season with no exception, ever. A single scalar value per month
    makes it impossible to express."""
    broken = deepcopy(ground_truth)
    broken["month_to_season"]["3"] = ["summer", "winter"]
    assert list(validator.iter_errors(broken))


# --- gap 3 (D4): rate magnitude and the both-null Rate -------------------------------------


@pytest.mark.parametrize("shifted", [5.5397, 0.0005])
def test_a_decimal_shift_outside_the_bounds_is_rejected(validator, ground_truth, shifted):
    """Bounds are ~10x observed headroom, so they catch an order-of-magnitude error and
    nothing finer. That is the whole job: the check with teeth is D2's span check, since
    `5.5397` does not occur in a source row printing `$0.55397`."""
    broken = deepcopy(ground_truth)
    broken["energy"]["on_peak"]["summer"]["standard"] = shifted
    assert list(validator.iter_errors(broken))


def test_a_plausible_but_wrong_rate_is_accepted_and_that_is_the_point(validator, ground_truth):
    """⚠ Measured, so the schema is not mistaken for a correctness check.

    0.45397 is wrong by ten cents a kWh and passes every constraint here, because it is a
    perfectly ordinary California energy rate. Nothing structural can catch it. Only D2's
    span check (the digits must occur in the quoted source row) and, eventually, a real bill
    can. Tight bounds inferred from 2026 data would not fix this and would reject real
    tariffs as rates climb.
    """
    plausible = deepcopy(ground_truth)
    plausible["energy"]["on_peak"]["summer"]["standard"] = 0.45397
    assert list(validator.iter_errors(plausible)) == []


def test_a_rate_cell_with_neither_standard_nor_care_is_rejected(validator, ground_truth):
    """Same late-failure signature as D3's season hole: it loads clean and raises at bill
    time. Closed with `anyOf`."""
    broken = deepcopy(ground_truth)
    cell = broken["energy"]["off_peak"]["winter"]
    del cell["standard"]
    del cell["care"]
    assert list(validator.iter_errors(broken))


def test_a_period_missing_a_season_is_rejected(validator, ground_truth):
    """A dropped winter column is the commonest transcription loss from a two-column sheet."""
    broken = deepcopy(ground_truth)
    del broken["energy"]["off_peak"]["winter"]
    assert list(validator.iter_errors(broken))


# --- gap 1 (D2): provenance -----------------------------------------------------------------


def test_every_rate_cell_must_carry_both_a_citation_and_an_evidence_span(validator, ground_truth):
    """The gap with no downstream detector. A wrong rate fails reconciliation eventually; a
    wrong citation fails nothing, ever — and CLAUDE.md makes citation the validity condition
    for a spec existing at all."""
    for field in ("citation", "evidence"):
        broken = deepcopy(ground_truth)
        del broken["energy"]["on_peak"]["summer"][field]
        assert list(validator.iter_errors(broken)), field


def test_a_bare_number_is_too_short_to_be_an_evidence_span(validator, ground_truth):
    """`minLength` is a blunt instrument, but it rules out the specific failure D5 measured:
    raw `pdftotext` (without -layout) serialises the sheet into runs of bare numbers, and a
    span of `$0.55397` would satisfy a containment check while proving nothing about which
    schedule, period or season column it came from."""
    broken = deepcopy(ground_truth)
    broken["energy"]["on_peak"]["summer"]["evidence"]["span"] = "$0.55397"
    assert list(validator.iter_errors(broken))


def test_an_invented_namespaced_schedule_id_is_discouraged_but_not_blocked(validator, ground_truth):
    """⚠ Recorded as a known limit, not a passing constraint.

    D1 chose the bare `schedule_id` precisely because a namespaced one is a string the model
    must INVENT, with nothing to check it against. But `MCE-E-TOU-C` is a well-formed
    identifier, so no pattern can reject it without also rejecting real hyphenated schedule
    ids like `TOU-DR1` and `EV-TOU-5`. The constraint lives in the prompt and in the human
    diff, and this test says so out loud.
    """
    namespaced = deepcopy(ground_truth)
    namespaced["schedule_id"] = "CEA-TOU-DR1"
    assert list(validator.iter_errors(namespaced)) == []


def test_unknown_top_level_fields_are_rejected(validator, ground_truth):
    """`additionalProperties: false` throughout, mirroring the repo's own `extra="forbid"`."""
    broken = deepcopy(ground_truth)
    broken["monthly_charge"] = 12.0
    assert list(validator.iter_errors(broken))


def test_an_unknown_holiday_calendar_is_rejected(validator, ground_truth):
    """The loader raises on an unknown calendar name, so the enum just moves that failure
    from bill time to generation time."""
    broken = deepcopy(ground_truth)
    broken["tou"]["holiday_calendar"] = "ca_state_holidays"
    assert list(validator.iter_errors(broken))
