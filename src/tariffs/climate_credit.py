"""California Climate Credit: the cited table, and the one rule it does not come with.

The amounts and their distribution months are published (see ``climate_credit.yaml``).
What no source states is *which statement* receives a credit "applied in October", and that
is the whole of the modeling here. The rule is named, not buried — see
:data:`CREDITED_STATEMENT_ENDS_IN_THE_CREDIT_MONTH`.

The credit is a flat per-household amount: it does not vary with usage, rate schedule, CARE
status or climate zone. So it can never reorder a rate comparison; it moves an absolute
annual figure and nothing else.
"""

from __future__ import annotations

import functools
from datetime import date
from pathlib import Path

import yaml

TABLE_PATH = Path(__file__).parent / "climate_credit.yaml"

#: **The inference.** A credit is published as "applied in August and September"; a statement
#: spans two calendar months, so the two do not map one-to-one. This repo bills the credit on
#: the statement whose billing period **ends** in a credited month, which is the statement a
#: customer would call their "October bill".
#:
#: Evidence: exactly one credited bill exists — PG&E's 10/28/2025 statement, covering
#: 2025-09-25..2025-10-26, carrying -$58.23 against a published 2025 credit of $58.23. That
#: period ends in October and begins in September, so it is consistent with this rule and
#: **also** with "the statement issued in that month". One observation cannot separate them.
#: It is NOT consistent with "the period that begins in the credit month".
#:
#: `test_the_credited_statement_rule_is_load_bearing` pins how much rides on this: under the
#: begins-in rule the same bill moves by the full $58.23, far outside the ±$2 gate. A second
#: credited bill would settle it; until then this is an inference, deliberately named.
CREDITED_STATEMENT_ENDS_IN_THE_CREDIT_MONTH = True


class MissingClimateCreditError(LookupError):
    """No published credit for that utility and year.

    Raised rather than defaulting to zero: a silently-absent credit understates nothing and
    overstates a bill by $36-$99 a year, and CLAUDE.md's rule is to refuse rather than guess.
    """


@functools.lru_cache(maxsize=1)
def _table() -> dict:
    return yaml.safe_load(TABLE_PATH.read_text())


def published_years(utility: str) -> list[int]:
    return sorted(_table()["electric"].get(utility, {}))


def credit_for(utility: str, period_start: date, period_end: date) -> float | None:
    """The climate credit (a negative dollar amount) for one statement, or ``None``.

    ``None`` means "this statement is not a credited one" — the ordinary case, since a
    credit lands on two statements a year at most. A utility/year with no published table
    raises instead, because that is a gap in our data rather than a fact about the bill.
    """
    utilities = _table()["electric"]
    if utility not in utilities:
        raise MissingClimateCreditError(
            f"no climate credit table for {utility!r} (have: {sorted(utilities)}). "
            f"Amounts are published per utility per year at cpuc.ca.gov/ClimateCredit/."
        )
    by_year = utilities[utility]
    year = period_end.year if CREDITED_STATEMENT_ENDS_IN_THE_CREDIT_MONTH else period_start.year
    if year not in by_year:
        raise MissingClimateCreditError(
            f"no {year} climate credit published for {utility} (have: {sorted(by_year)}). "
            f"The CPUC sets amounts annually; see {TABLE_PATH.name}'s `unverified` block."
        )
    entry = by_year[year]
    month = period_end.month if CREDITED_STATEMENT_ENDS_IN_THE_CREDIT_MONTH else period_start.month
    if month not in entry["months"]:
        return None
    return -float(entry["amount"])
