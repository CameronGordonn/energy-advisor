"""The California Climate Credit table, and the two cross-checks that make it evidence.

`src/tariffs/climate_credit.yaml` is a cited data table, not a tariff spec, and nothing in
the pricing path reads it yet. What earns it a place in the repo is that two independent
sources agree with it — a real utility bill, and SDG&E's own published rate alerts — and
those agreements are the kind of claim that goes stale silently unless a test holds them.

It also pins the fact that explains an apparent hole in the golden-bill corpus: eleven
consecutive statements contain exactly ONE climate credit, because the CPUC moved the
residential electric credit out of April/October and into August/September for 2026.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parents[2]
TABLE = REPO / "src/tariffs/climate_credit.yaml"
GOLDEN = REPO / "tests/golden_bills/pge_10-28-2025.yaml"
ALERTS = sorted((REPO / "tests/published_impacts").glob("sdge_*_tou_dr1.yaml"))


@pytest.fixture(scope="module")
def table() -> dict:
    return yaml.safe_load(TABLE.read_text())


def test_the_table_is_cited(table):
    """CLAUDE.md's rule for tariff data: a number without a citation is invalid. This file
    is not loaded by the spec loader, so nothing else would enforce it."""
    assert len(table["citation"]) > 200
    assert "cpuc.ca.gov" in table["citation"]
    assert "retrieved 2026-09-16" in table["citation"]


def test_the_2026_schedule_change_is_recorded(table):
    """⭐ The fact that makes a naive 'semi-annual' model wrong. Through 2025 the residential
    electric credit was paid in April and October; from 2026 it is paid in August and
    September. A model carrying the old months forward applies 2026's credit to the wrong
    bills entirely."""
    change = table["schedule_change"]
    assert change["effective_year"] == 2026
    assert change["months_through_2025"] == [4, 10]
    assert change["months_from_2026"] == [8, 9]
    for utility, years in table["electric"].items():
        for year, entry in years.items():
            expected = [4, 10] if year <= 2025 else [8, 9]
            assert set(entry["months"]) <= set(expected), (utility, year, entry)


# --- cross-check 1: a published program figure against a real bill -------------------------


def test_the_pge_2025_amount_matches_the_real_october_statement(table):
    """A published CPUC/PG&E figure and an anonymized real bill, from entirely different
    places, agreeing to the cent.

    This is the strongest check available on the table, and it is one data point: the credit
    appears on exactly one of the eleven golden bills.
    """
    published = table["electric"]["PG&E"][2025]["amount"]
    golden = yaml.safe_load(GOLDEN.read_text())
    observed = golden["expected"]["observed_adjustments"]["California Climate Credit (observed)"]
    assert observed == pytest.approx(-published, abs=0.005), (observed, published)


def test_the_credit_appears_on_exactly_one_golden_bill_and_that_is_correct(table):
    """⚠ What looked like missing data and is not.

    Under a semi-annual model a second credit should appear in spring 2026. None does. The
    reason is the schedule change: April 2026 had no electric credit, and the August and
    September 2026 payments fall after 2026-06-25, the last period in the corpus. Asserted
    so that adding a later bill — which SHOULD carry an August or September 2026 credit —
    fails here and forces the table to be revisited rather than quietly disagreed with.
    """
    credited = [
        path
        for path in sorted((REPO / "tests/golden_bills").glob("pge_*.yaml"))
        if "California Climate Credit (observed)"
        in yaml.safe_load(path.read_text())["expected"].get("observed_adjustments", {})
    ]
    assert [p.name for p in credited] == ["pge_10-28-2025.yaml"]

    latest = max(
        yaml.safe_load(p.read_text())["period_end"]
        for p in sorted((REPO / "tests/golden_bills").glob("pge_*.yaml"))
    )
    assert str(latest) < "2026-08-01", (
        f"a bill now runs to {latest}, into the Aug/Sep 2026 credit window — the corpus can "
        "now test the 2026 amount, and this test's premise has expired"
    )


# --- cross-check 2: the table against SDG&E's own published bill impacts --------------------


def test_the_sdge_2026_annual_credit_matches_what_the_rate_alerts_imply(table):
    """⭐ Outside corroboration of a figure the tier-2 corpus could only derive.

    SDG&E's rate alerts print a bundled bill excluding the climate credit and a second one
    including it, and never name the credit itself — footnote 3 says only that it is
    "a semi-annual credit applied to customers' bills". The difference is $8/month in all
    three 2026 quarters, on an annual-average basis.

    Two payments of $49.36 is $98.72/yr, or $8.23 per average month. That rounds to the
    published $8 and no other plausible amount does: a $33.50 payment (the figure this
    repo's notes carried until session 27) gives $5.58/month, which rounds to $6.
    """
    entry = table["electric"]["SDG&E"][2026]
    annual = entry["amount"] * len(entry["months"])
    per_month = annual / 12

    implied = set()
    for path in ALERTS:
        fixture = yaml.safe_load(path.read_text())
        derived = fixture["derived"]
        implied.add(derived["climate_credit_usd_non_care"])
        implied.add(derived["climate_credit_usd_care"])

    assert implied == {8}, implied
    assert round(per_month) == 8, per_month

    # And the stale figure would have failed this, which is why it is worth asserting.
    assert round(33.50 * 2 / 12) != 8


def test_every_utility_year_carries_an_amount_and_its_months(table):
    for utility, years in table["electric"].items():
        for year, entry in years.items():
            assert set(entry) == {"amount", "months"}, (utility, year)
            assert 0 < entry["amount"] < 200, (utility, year)
            assert entry["months"], (utility, year)


def test_absent_years_are_named_rather_than_guessed(table):
    """CLAUDE.md: never fabricate a rate; mark it unverified and raise rather than guess.
    An absent year is a loud failure, a wrong year is a silent one."""
    fields = {item["field"] for item in table["unverified"]}
    assert "electric.SDG&E.2025" in fields
    assert "electric.*.2027" in fields
    assert 2025 not in table["electric"]["SDG&E"]
    assert 2027 not in table["electric"]["PG&E"]
    for item in table["unverified"]:
        assert len(item["why"]) > 30, item


def test_the_table_is_not_in_the_specs_directory():
    """The loader globs `specs/*.yaml` and validates every file as a TariffSpec, so a data
    table living there would break spec loading outright."""
    assert TABLE.parent.name == "tariffs"
    assert not (REPO / "src/tariffs/specs/climate_credit.yaml").exists()
