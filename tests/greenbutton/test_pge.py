"""Tests for the PG&E Green Button interval parser."""

from __future__ import annotations

import glob

import pandas as pd
import pytest

from greenbutton import (
    BillingSummaryError,
    Direction,
    GreenButtonParseError,
    IntervalSeries,
    MeterMeta,
    Utility,
    parse_pge_interval_csv,
)
from greenbutton.models import COL_ESTIMATED, COL_KWH, LOCAL_TZ

from .conftest import billing_csv, hourly_day, interval_csv, write

# --- happy path ------------------------------------------------------------


def test_basic_hourly_parse(tmp_path):
    rows = hourly_day("2025-08-02", usage=0.25)
    series, report = parse_pge_interval_csv(write(tmp_path, interval_csv(rows)))

    assert series.utility is Utility.PGE
    assert series.direction is Direction.IMPORT
    assert series.interval == pd.Timedelta(hours=1).to_pytimedelta()
    assert report.interval_minutes == 60
    assert report.n_intervals == 24
    assert report.n_gaps == 0
    assert report.coverage == 1.0
    assert series.total_kwh == pytest.approx(24 * 0.25)

    idx = series.frame.index
    assert str(idx.tz) == LOCAL_TZ
    assert idx.is_monotonic_increasing and idx.is_unique
    assert idx[0] == pd.Timestamp("2025-08-02 00:00", tz=LOCAL_TZ)


def test_fifteen_minute_interval(tmp_path):
    rows = []
    for h in range(2):
        for m in range(0, 60, 15):
            start = f"{h:02d}:{m:02d}"
            end = f"{h:02d}:{m + 14:02d}"
            rows.append(("2025-08-02", start, end, 0.05, ""))
    _, report = parse_pge_interval_csv(write(tmp_path, interval_csv(rows)))
    assert report.interval_minutes == 15
    assert report.n_intervals == 8


def test_pii_is_stripped(tmp_path):
    series, _ = parse_pge_interval_csv(write(tmp_path, interval_csv(hourly_day("2025-08-02"))))
    dumped = series.meta.model_dump_json()
    assert "TEST CUSTOMER" not in dumped
    assert "1 TEST ST" not in dumped
    assert "7355849999" not in dumped
    assert series.meta.account_tail == "9999"
    assert series.meta.address_zip == "95060"
    assert series.meta.service_id == "Service 1"


# --- wrong file ------------------------------------------------------------


def test_billing_summary_rejected(tmp_path):
    with pytest.raises(BillingSummaryError, match="range of days"):
        parse_pge_interval_csv(write(tmp_path, billing_csv(), name="billing.csv"))


def test_no_table_rejected(tmp_path):
    with pytest.raises(GreenButtonParseError, match="no interval table"):
        parse_pge_interval_csv(write(tmp_path, "Name,X\nAddress,Y\n", name="junk.csv"))


# --- DST -------------------------------------------------------------------


def test_fall_back_day(tmp_path):
    """25-hour day exported as 24 nominal rows: lone 01:00 -> PDT, one grid gap."""
    rows = hourly_day("2025-11-01") + hourly_day("2025-11-02") + hourly_day("2025-11-03")
    series, report = parse_pge_interval_csv(write(tmp_path, interval_csv(rows)))

    assert report.dst_fall_back_days == ["2025-11-02"]
    assert report.dst_spring_forward_days == []

    day = series.frame.loc["2025-11-02"]
    assert len(day) == 24
    one_am = day.index[day.index.strftime("%H:%M") == "01:00"][0]
    assert one_am.utcoffset() == pd.Timedelta(hours=-7)  # PDT fold

    # the folded second 01:00 (PST, = 09:00 UTC) shows as exactly one grid gap
    gaps = series.gaps()
    assert len(gaps) == 1
    expected_gap = pd.Timestamp("2025-11-02 09:00", tz="UTC").tz_convert(LOCAL_TZ)
    assert gaps[0] == expected_gap
    assert gaps[0].strftime("%H:%M") == "01:00"
    assert gaps[0].utcoffset() == pd.Timedelta(hours=-8)  # PST


def test_spring_forward_day(tmp_path):
    """PG&E labels the transition slot 02:00 and omits 03:00; 02:00 -> 03:00."""
    rows = (
        hourly_day("2026-03-07")
        + hourly_day("2026-03-08", skip={"03:00"})  # mirrors the real file
        + hourly_day("2026-03-09")
    )
    series, report = parse_pge_interval_csv(write(tmp_path, interval_csv(rows)))

    assert report.dst_spring_forward_days == ["2026-03-08"]
    assert report.dst_fall_back_days == []

    day = series.frame.loc["2026-03-08"]
    assert len(day) == 23
    local_hours = [t.strftime("%H:%M") for t in day.index]
    assert "02:00" not in local_hours  # nonexistent, shifted away
    assert "03:00" in local_hours
    assert series.gaps().empty  # contiguous after shift


# --- gaps & estimated ------------------------------------------------------


def test_gap_detection(tmp_path):
    rows = hourly_day("2025-08-02", skip={"05:00", "06:00"})
    series, report = parse_pge_interval_csv(write(tmp_path, interval_csv(rows)))
    assert report.n_gaps == 2
    assert report.coverage == pytest.approx(22 / 24)
    gap_hours = {t.strftime("%H:%M") for t in series.gaps()}
    assert gap_hours == {"05:00", "06:00"}


def test_estimated_flag(tmp_path):
    rows = hourly_day("2025-08-02", notes={"03:00": "Estimated", "04:00": "estimated read"})
    series, report = parse_pge_interval_csv(write(tmp_path, interval_csv(rows)))
    assert report.n_estimated == 2
    est = series.frame[series.frame[COL_ESTIMATED]]
    assert {t.strftime("%H:%M") for t in est.index} == {"03:00", "04:00"}


# --- malformed inputs ------------------------------------------------------


def test_mixed_granularity_rejected(tmp_path):
    rows = [
        ("2025-08-02", "00:00", "00:59", 0.1, ""),  # 60 min
        ("2025-08-02", "01:00", "01:14", 0.1, ""),  # 15 min
    ]
    with pytest.raises(GreenButtonParseError, match=r"inconsistent interval|interval mismatch"):
        parse_pge_interval_csv(write(tmp_path, interval_csv(rows)))


def test_nonnumeric_usage_rejected(tmp_path):
    rows = [("2025-08-02", "00:00", "00:59", 0.1, ""), ("2025-08-02", "01:00", "01:59", 0.1, "")]
    text = interval_csv(rows).replace("0.1", "oops", 1)
    with pytest.raises(GreenButtonParseError, match="non-numeric usage"):
        parse_pge_interval_csv(write(tmp_path, text))


def test_negative_import_rejected():
    idx = pd.date_range("2025-08-02", periods=3, freq="h", tz=LOCAL_TZ)
    frame = pd.DataFrame({COL_KWH: [0.1, -0.2, 0.3], COL_ESTIMATED: False}, index=idx)
    with pytest.raises(ValueError, match="negative kwh"):
        IntervalSeries(
            utility=Utility.PGE,
            interval=pd.Timedelta(hours=1).to_pytimedelta(),
            meta=MeterMeta(utility=Utility.PGE),
            frame=frame,
        )


# --- real file smoke test (skipped if the git-ignored export is absent) -----


def _real_file() -> str | None:
    matches = glob.glob("data/pge_electric_usage_interval_data*.csv")
    return matches[0] if matches else None


@pytest.mark.skipif(_real_file() is None, reason="real PG&E export not present in data/")
def test_real_export_smoke():
    series, report = parse_pge_interval_csv(_real_file())
    assert report.interval_minutes == 60
    assert report.coverage > 0.99
    assert report.total_kwh > 0
    assert (series.frame[COL_KWH] >= 0).all()
    # one fall-back and one spring-forward transition over ~a year
    assert len(report.dst_fall_back_days) == 1
    assert len(report.dst_spring_forward_days) == 1
