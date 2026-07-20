"""The reconciliation merge gate: every golden bill must model within its tolerance.

Golden fixtures are committed and anonymized. The real interval export is git-ignored;
these tests skip when it is absent (CI without data) but run locally and in any env
that has the customer's data.
"""

from __future__ import annotations

import glob
from pathlib import Path

import pytest

from report.reconcile import format_comparison, load_fixture, reconcile

GOLDEN = Path(__file__).parent
FIXTURES = sorted(GOLDEN.glob("*.yaml"))


def _interval_file() -> str | None:
    m = sorted(glob.glob("data/pge_electric_usage_interval_data*.csv"))
    return m[0] if m else None


def test_fixtures_exist():
    assert FIXTURES, "no golden-bill fixtures committed"


@pytest.mark.skipif(_interval_file() is None, reason="real PG&E interval export not present")
@pytest.mark.parametrize("fx_path", FIXTURES, ids=lambda p: p.stem)
def test_bill_reconciles(fx_path):
    from greenbutton import parse_pge_interval_csv

    series, _ = parse_pge_interval_csv(_interval_file())
    r = reconcile(load_fixture(fx_path), series)
    assert r.within_tolerance, "\n" + format_comparison(r)
