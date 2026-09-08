"""Tests for the Green Button export inspector.

The inspector is the first thing run against a file from a utility the billing engine has
never seen, and it is also the engine behind the public browser tool — so its guarantees
matter twice over:

* it must **auto-detect** the utility rather than being told,
* it must **refuse** a file it cannot read, with guidance, instead of returning plausible
  zeros,
* it must produce **no dollar figures** (the reconciliation gate does not cover pricing for
  an unvalidated utility), and
* its usage arithmetic must **conserve energy** — the shares and monthly totals have to add
  back up to the parsed total, or every number shown to a visitor is quietly wrong.
"""

from __future__ import annotations

import pytest

from greenbutton import GreenButtonParseError, Utility
from report.inspect import Inspection, inspect_export

from ..greenbutton.conftest import billing_csv, hourly_day, interval_csv, write
from ..greenbutton.test_sdge import sdge_interval_csv


def _is_spring_forward(d) -> bool:
    """Second Sunday in March — the 23-hour local day."""
    return d.month == 3 and d.weekday() == 6 and 8 <= d.day <= 14


def _pge_year(tmp_path, days: int = 40, usage: float = 0.5):
    """A PG&E file spanning `days` consecutive days of flat hourly usage.

    Mirrors what PG&E's real export does across DST rather than emitting a naive 24 rows
    every day: on the spring-forward day the file carries 02:00 (a wall-clock time that
    does not exist locally) and OMITS 03:00, giving 23 rows. Emitting both would make
    02:00 shift onto 03:00 and collide, which is a fixture bug, not a parser bug.
    """
    import datetime as dt

    rows = []
    d = dt.date(2026, 1, 1)
    for _ in range(days):
        skip = {"03:00"} if _is_spring_forward(d) else None
        rows += hourly_day(d.isoformat(), usage=usage, skip=skip)
        d += dt.timedelta(days=1)
    return write(tmp_path, interval_csv(rows), "pge.csv")


def test_detects_pge_without_being_told(tmp_path):
    i = inspect_export(_pge_year(tmp_path))
    assert i.utility is Utility.PGE
    assert i.interval_minutes == 60
    assert i.source_name == "pge.csv"


def test_detects_sdge_without_being_told(tmp_path):
    """The path that matters tomorrow: an SDG&E file must not be misread as PG&E."""
    rows = [("2026-01-01", f"{h}:00", f"{h}:59", 0.5, "") for h in range(24)]
    p = write(tmp_path, sdge_interval_csv(rows), "sdge.csv")
    i = inspect_export(p)
    assert i.utility is Utility.SDGE
    assert i.total_kwh == pytest.approx(12.0)


def test_energy_is_conserved_across_every_breakdown(tmp_path):
    """Monthly totals, the hour-of-day profile and the weekday/weekend split must each sum
    back to the parsed total. A visitor sees all three; they cannot disagree."""
    i = inspect_export(_pge_year(tmp_path, days=40, usage=0.5))
    assert sum(m.kwh for m in i.by_month) == pytest.approx(i.total_kwh, abs=0.05)
    assert sum(i.by_hour_kwh) == pytest.approx(i.total_kwh, abs=0.05)
    assert i.weekday_kwh + i.weekend_kwh == pytest.approx(i.total_kwh, abs=0.05)


def test_shares_are_fractions_of_the_right_windows(tmp_path):
    """Flat usage means each window's share is exactly its width over 24 hours."""
    i = inspect_export(_pge_year(tmp_path, days=28, usage=1.0))
    assert i.peak_share == pytest.approx(5 / 24, abs=1e-3)  # 16:00-21:00
    assert i.overnight_share == pytest.approx(6 / 24, abs=1e-3)  # 00:00-06:00
    assert i.solar_window_share == pytest.approx(4 / 24, abs=1e-3)  # 10:00-14:00


def test_peak_share_tracks_a_genuinely_evening_heavy_load(tmp_path):
    """The headline number has to move with the load, not just be arithmetically valid."""
    import datetime as dt

    rows = []
    d = dt.date(2026, 1, 1)
    for _ in range(28):
        for h in range(24):
            rows.append(
                (d.isoformat(), f"{h:02d}:00", f"{h:02d}:59", 4.0 if 16 <= h < 21 else 0.1, "")
            )
        d += dt.timedelta(days=1)
    i = inspect_export(write(tmp_path, interval_csv(rows), "evening.csv"))
    assert i.peak_share > 0.90
    assert i.busiest_hour_of_day in range(16, 21)


def test_a_billing_summary_is_refused_with_guidance(tmp_path):
    """The single most likely user error: downloading the cost summary, not the intervals.
    It must fail loudly rather than produce an empty-looking analysis."""
    p = write(tmp_path, billing_csv(), "billing.csv")
    with pytest.raises(GreenButtonParseError) as exc:
        inspect_export(p)
    assert "interval" in str(exc.value).lower()


def test_an_unreadable_file_names_both_parsers_it_tried(tmp_path):
    p = write(tmp_path, "not,a,green,button,file\n1,2,3,4,5\n", "junk.csv")
    with pytest.raises(GreenButtonParseError) as exc:
        inspect_export(p)
    msg = str(exc.value)
    assert "PG&E" in msg and "SDG&E" in msg


def test_short_span_is_warned_about_not_silently_extrapolated(tmp_path):
    i = inspect_export(_pge_year(tmp_path, days=20))
    assert any("seasonal cycle" in w for w in i.warnings)


def test_a_full_year_is_not_warned_about(tmp_path):
    i = inspect_export(_pge_year(tmp_path, days=365))
    assert not any("seasonal cycle" in w for w in i.warnings)
    assert i.looks_billable


def test_gaps_are_surfaced_and_block_bill_comparison(tmp_path):
    """Coverage below the threshold means totals understate reality; say so."""
    import datetime as dt

    rows = []
    d = dt.date(2026, 1, 1)
    for _ in range(30):
        # drop a third of each day's readings
        skip = {f"{h:02d}:00" for h in range(0, 24, 3)}
        rows += hourly_day(d.isoformat(), usage=0.5, skip=skip)
        d += dt.timedelta(days=1)
    i = inspect_export(write(tmp_path, interval_csv(rows), "gappy.csv"))
    assert i.n_gaps > 0
    assert i.coverage < 0.98
    assert not i.looks_billable
    assert any("not suitable for a bill comparison" in w for w in i.warnings)


def test_solar_export_register_is_surfaced_with_its_energy(tmp_path):
    """An SDG&E NEM account: the export register presence changes which questions are worth
    asking, so it must reach the front end rather than being dropped."""
    rows = [
        ("2026-01-01", f"{h}:00", f"{h}:59", 0.5, 2.0 if 10 <= h < 14 else 0.0, "")
        for h in range(24)
    ]
    p = write(
        tmp_path,
        sdge_interval_csv(rows, columns=("IMPORT (kWh)", "EXPORT (kWh)")),
        "solar.csv",
    )
    i = inspect_export(p)
    assert i.has_export_register
    assert i.export_kwh == pytest.approx(8.0, abs=0.01)


def test_the_inspection_carries_no_dollar_figures(tmp_path):
    """Invariant 1 made structural: pricing may not ship for an unvalidated utility, so the
    inspector must have no money-shaped field at all for one to leak through."""
    i = inspect_export(_pge_year(tmp_path))
    fields = set(Inspection.model_fields) | {"month", "kwh", "days"}
    money = ("cost", "dollar", "usd", "price", "rate", "charge", "bill", "tariff", "amount")
    leaked = [f for f in fields for m in money if m in f.lower()]
    assert not leaked, f"inspection exposes pricing field(s): {leaked}"
    # and nothing numeric in the payload is denominated in anything but kWh / days / shares
    assert "$" not in i.model_dump_json()


def test_inspection_round_trips_through_json(tmp_path):
    """The browser tool hands this across the Python/JS boundary as JSON."""
    i = inspect_export(_pge_year(tmp_path))
    assert Inspection.model_validate_json(i.model_dump_json()) == i


# --- plain-English findings -------------------------------------------------------------
# These are what a non-technical visitor actually reads, so they are held to the same
# standard as the numbers: they must track the data, and must never state a price.


def _findings_for(tmp_path, kwh_at_hour):
    import datetime as dt

    rows = []
    d = dt.date(2026, 1, 1)
    for _ in range(28):
        for h in range(24):
            rows.append((d.isoformat(), f"{h:02d}:00", f"{h:02d}:59", kwh_at_hour(h), ""))
        d += dt.timedelta(days=1)
    return inspect_export(write(tmp_path, interval_csv(rows), "f.csv")).findings


def test_an_evening_heavy_household_is_told_tou_works_against_it(tmp_path):
    fs = _findings_for(tmp_path, lambda h: 4.0 if 16 <= h < 21 else 0.1)
    peak = next(f for f in fs if "peak hours" in f.title)
    assert peak.kind == "watch"
    assert "works against you" in peak.detail


def test_a_peak_avoiding_household_is_told_tou_favours_it(tmp_path):
    fs = _findings_for(tmp_path, lambda h: 0.05 if 16 <= h < 21 else 1.0)
    peak = next(f for f in fs if "peak hours" in f.title)
    assert peak.kind == "good"
    assert "favours" in peak.detail


def test_a_flat_household_is_told_it_is_neither(tmp_path):
    """A featureless load sits at 5/24 = 21%, and must not be spun either way."""
    fs = _findings_for(tmp_path, lambda h: 1.0)
    peak = next(f for f in fs if "peak hours" in f.title)
    assert peak.kind == "info"
    assert "neither" in peak.detail


def test_overnight_heavy_usage_is_recognised(tmp_path):
    fs = _findings_for(tmp_path, lambda h: 5.0 if h < 6 else 0.1)
    assert any("overnight" in f.title for f in fs)


def test_findings_never_quote_a_price(tmp_path):
    """The reconciliation gate covers dollars; findings describe load shape only."""
    for shape in (
        lambda h: 1.0,
        lambda h: 4.0 if 16 <= h < 21 else 0.1,
        lambda h: 5.0 if h < 6 else 0.1,
    ):
        for f in _findings_for(tmp_path, shape):
            text = f"{f.title} {f.detail}"
            assert "$" not in text
            assert "¢" not in text
            assert "/kWh" not in text


def test_every_finding_has_a_known_kind(tmp_path):
    fs = _findings_for(tmp_path, lambda h: 1.0)
    assert fs, "a valid file should always produce at least one finding"
    assert {f.kind for f in fs} <= {"good", "watch", "info"}


def test_a_short_file_is_told_it_is_not_a_full_year(tmp_path):
    i = inspect_export(_pge_year(tmp_path, days=20))
    assert any("not a full year" in f.title for f in i.findings)
