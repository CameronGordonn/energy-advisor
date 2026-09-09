"""Tests for the SDG&E Green Button interval parser.

SDG&E emits two CSV shapes and both are covered here:

* **range shape** — the documented Opower "Download My Data" table (M/D/YYYY unpadded
  dates, 24-hour ``H:MM``, ``END TIME``, optional IMPORT/EXPORT split);
* **meter shape** — what a real export was observed to use (``Duration`` in minutes,
  12-hour ``h:MM AM/PM``, ``Consumption``/``Generation``/``Net``, a ``Total Usage``
  checksum in the preamble, and a **true 25-hour DST fall-back day**).

All fixtures are hand-authored to the observed shapes, so they are committable. The real
export they were written from is not vendored — it lives in a repo with no LICENSE; see
the ``greenbutton/sdge.py`` docstring for provenance and for what is still unverified
(the 15-minute meter-shape variant, and spring-forward on either shape).
"""

from __future__ import annotations

from datetime import date as _date

import pandas as pd
import pytest

from greenbutton import (
    AmbiguousDSTError,
    BillingSummaryError,
    Direction,
    GreenButtonParseError,
    Utility,
    parse_sdge_interval_csv,
)
from greenbutton.models import COL_ESTIMATED, LOCAL_TZ

from .conftest import write

BOM = "﻿"

_META = [
    "",
    "Name,TEST CUSTOMER",
    'Address,"1 TEST ST, SAN DIEGO CA 921011234"',
    "Account Number,7355849999",
    "Service,Service 1",
    "",
]


def _mdY(iso: str) -> str:
    """'2025-09-01' -> '9/1/2025' (SDG&E's unpadded M/D/YYYY)."""
    d = _date.fromisoformat(iso)
    return f"{d.month}/{d.day}/{d.year}"


def sdge_interval_csv(
    rows: list[tuple],
    *,
    columns: tuple[str, ...] = ("IMPORT (kWh)",),
    type_label: str = "Electric usage",
    with_notes: bool = True,
) -> str:
    """Build an SDG&E interval CSV.

    ``rows`` are ``(iso_date, start_hhmm, end_hhmm, *values, notes)`` where ``*values``
    lines up with ``columns`` (one energy column by default, two for an import/export
    split). ``notes`` is the trailing NOTES cell (present iff ``with_notes``).
    """
    header = ["TYPE", "DATE", "START TIME", "END TIME", *columns, "COST"]
    if with_notes:
        header.append("NOTES")
    out = [BOM.rstrip("\n"), *_META, ",".join(header)]
    for row in rows:
        iso, start, end = row[0], row[1], row[2]
        values = row[3 : 3 + len(columns)]
        notes = row[-1] if with_notes else None
        cells = [type_label, _mdY(iso), start, end, *(str(v) for v in values), "$0.00"]
        if with_notes:
            cells.append(notes)
        out.append(",".join(cells))
    return "\n".join(out) + "\n"


def hourly_day(
    iso: str,
    *,
    usage: float = 0.10,
    export: float | None = None,
    skip: set[str] | None = None,
    notes: dict[str, str] | None = None,
) -> list[tuple]:
    """24 hourly rows (inclusive-minute END, unpadded H:00-H:59).

    With ``export`` set, each row carries a second (export) value; the fixture must then
    be built with ``columns=("IMPORT (kWh)", "EXPORT (kWh)")``.
    """
    skip = skip or set()
    notes = notes or {}
    rows: list[tuple] = []
    for h in range(24):
        start = f"{h}:00"
        if start in skip:
            continue
        end = f"{h}:59"
        if export is None:
            rows.append((iso, start, end, usage, notes.get(start, "")))
        else:
            rows.append((iso, start, end, usage, export, notes.get(start, "")))
    return rows


# --- happy path ------------------------------------------------------------


def test_basic_hourly_parse(tmp_path):
    rows = hourly_day("2025-09-01", usage=0.25)
    series, report = parse_sdge_interval_csv(write(tmp_path, sdge_interval_csv(rows)))

    assert series.utility is Utility.SDGE
    assert series.direction is Direction.IMPORT
    assert report.utility is Utility.SDGE
    assert series.interval == pd.Timedelta(hours=1).to_pytimedelta()
    assert report.interval_minutes == 60
    assert report.n_intervals == 24
    assert report.n_gaps == 0
    assert report.coverage == 1.0
    assert series.total_kwh == pytest.approx(24 * 0.25)

    idx = series.frame.index
    assert str(idx.tz) == LOCAL_TZ
    assert idx.is_monotonic_increasing and idx.is_unique
    assert idx[0] == pd.Timestamp("2025-09-01 00:00", tz=LOCAL_TZ)


def test_unpadded_mdy_dates_parse(tmp_path):
    # single-digit month/day/hour must parse (SDG&E's '9/1/2025 0:00' shape)
    rows = hourly_day("2025-09-01")
    series, _ = parse_sdge_interval_csv(write(tmp_path, sdge_interval_csv(rows)))
    assert series.frame.index[0] == pd.Timestamp("2025-09-01 00:00", tz=LOCAL_TZ)


def test_fifteen_minute_interval(tmp_path):
    rows = []
    for h in range(2):
        for m in range(0, 60, 15):
            rows.append(("2025-09-01", f"{h}:{m:02d}", f"{h}:{m + 14:02d}", 0.05, ""))
    _, report = parse_sdge_interval_csv(write(tmp_path, sdge_interval_csv(rows)))
    assert report.interval_minutes == 15
    assert report.n_intervals == 8


def test_pii_is_stripped(tmp_path):
    series, _ = parse_sdge_interval_csv(
        write(tmp_path, sdge_interval_csv(hourly_day("2025-09-01")))
    )
    dumped = series.meta.model_dump_json()
    assert "TEST CUSTOMER" not in dumped
    assert "1 TEST ST" not in dumped
    assert "7355849999" not in dumped
    assert series.meta.account_tail == "9999"
    assert series.meta.address_zip == "92101"
    assert series.meta.service_id == "Service 1"


# --- single-column vs import/export ---------------------------------------


def test_single_usage_column(tmp_path):
    rows = hourly_day("2025-09-01", usage=0.2)
    csv_text = sdge_interval_csv(rows, columns=("USAGE (kWh)",))
    series, report = parse_sdge_interval_csv(write(tmp_path, csv_text))
    assert series.total_kwh == pytest.approx(24 * 0.2)
    assert report.notes == []  # no export register


def test_import_export_split_bills_import_and_notes_export(tmp_path):
    # solar account: IMPORT billed, EXPORT surfaced in notes but not billed (M1).
    rows = hourly_day("2025-09-01", usage=0.3, export=0.5)
    csv_text = sdge_interval_csv(rows, columns=("IMPORT (kWh)", "EXPORT (kWh)"))
    series, report = parse_sdge_interval_csv(write(tmp_path, csv_text))
    assert series.direction is Direction.IMPORT
    assert series.total_kwh == pytest.approx(24 * 0.3)  # import only
    assert any("export register present" in n for n in report.notes)
    assert any("12.000 kWh" in n for n in report.notes)  # 24 * 0.5


def test_zero_export_not_noted(tmp_path):
    rows = hourly_day("2025-09-01", usage=0.3, export=0.0)
    csv_text = sdge_interval_csv(rows, columns=("IMPORT (kWh)", "EXPORT (kWh)"))
    _, report = parse_sdge_interval_csv(write(tmp_path, csv_text))
    assert not any("export register" in n for n in report.notes)


# --- wrong / malformed inputs ---------------------------------------------


def test_billing_summary_rejected(tmp_path):
    text = (
        BOM
        + "\n".join(
            [
                *_META,
                "TYPE,START DATE,END DATE,USAGE (kWh),COST,NOTES",
                "Electric billing,9/1/2025,9/30/2025,241.47,$35.51,",
            ]
        )
        + "\n"
    )
    with pytest.raises(BillingSummaryError, match="billing-history"):
        parse_sdge_interval_csv(write(tmp_path, text, name="billing.csv"))


def test_no_table_rejected(tmp_path):
    with pytest.raises(GreenButtonParseError, match="no interval table"):
        parse_sdge_interval_csv(write(tmp_path, "Name,X\nAddress,Y\n", name="junk.csv"))


def test_no_usage_column_rejected(tmp_path):
    rows = hourly_day("2025-09-01")
    text = sdge_interval_csv(rows, columns=("SOMETHING ELSE",))
    with pytest.raises(GreenButtonParseError, match="no import/usage column"):
        parse_sdge_interval_csv(write(tmp_path, text))


def test_nonnumeric_usage_rejected(tmp_path):
    rows = [("2025-09-01", "0:00", "0:59", 0.1, ""), ("2025-09-01", "1:00", "1:59", 0.1, "")]
    text = sdge_interval_csv(rows).replace("0.1", "oops", 1)
    with pytest.raises(GreenButtonParseError, match="non-numeric"):
        parse_sdge_interval_csv(write(tmp_path, text))


def test_wrong_date_format_rejected(tmp_path):
    # an ISO date (PG&E shape) fed to the SDG&E parser must be rejected clearly
    rows = [("2025-09-01", "0:00", "0:59", 0.1, "")]
    text = sdge_interval_csv(rows).replace("9/1/2025", "2025-09-01")
    with pytest.raises(GreenButtonParseError, match="unparseable DATE"):
        parse_sdge_interval_csv(write(tmp_path, text))


# --- DST (shared engine, exercised through the SDG&E path) -----------------


def test_fall_back_day(tmp_path):
    rows = hourly_day("2025-11-01") + hourly_day("2025-11-02") + hourly_day("2025-11-03")
    series, report = parse_sdge_interval_csv(write(tmp_path, sdge_interval_csv(rows)))
    assert report.dst_fall_back_days == ["2025-11-02"]
    assert report.dst_spring_forward_days == []

    day = series.frame.loc["2025-11-02"]
    assert len(day) == 24
    one_am = day.index[day.index.strftime("%H:%M") == "01:00"][0]
    assert one_am.utcoffset() == pd.Timedelta(hours=-7)  # PDT fold
    gaps = series.gaps()
    assert len(gaps) == 1
    assert gaps[0].strftime("%H:%M") == "01:00"
    assert gaps[0].utcoffset() == pd.Timedelta(hours=-8)  # PST


def test_spring_forward_day(tmp_path):
    rows = (
        hourly_day("2026-03-07")
        + hourly_day("2026-03-08", skip={"3:00"})  # file labels 2:00, omits 3:00
        + hourly_day("2026-03-09")
    )
    series, report = parse_sdge_interval_csv(write(tmp_path, sdge_interval_csv(rows)))
    assert report.dst_spring_forward_days == ["2026-03-08"]
    assert report.dst_fall_back_days == []

    day = series.frame.loc["2026-03-08"]
    assert len(day) == 23
    local_hours = [t.strftime("%H:%M") for t in day.index]
    assert "02:00" not in local_hours
    assert "03:00" in local_hours
    assert series.gaps().empty


# --- gaps & estimated ------------------------------------------------------


def test_gap_detection(tmp_path):
    rows = hourly_day("2025-09-01", skip={"5:00", "6:00"})
    series, report = parse_sdge_interval_csv(write(tmp_path, sdge_interval_csv(rows)))
    assert report.n_gaps == 2
    assert report.coverage == pytest.approx(22 / 24)
    assert {t.strftime("%H:%M") for t in series.gaps()} == {"05:00", "06:00"}


def test_estimated_flag(tmp_path):
    rows = hourly_day("2025-09-01", notes={"3:00": "Estimated", "4:00": "estimated read"})
    series, report = parse_sdge_interval_csv(write(tmp_path, sdge_interval_csv(rows)))
    assert report.n_estimated == 2
    est = series.frame[series.frame[COL_ESTIMATED]]
    assert {t.strftime("%H:%M") for t in est.index} == {"03:00", "04:00"}


# ===========================================================================
# The meter shape — what a real SDG&E export actually looks like.
# Every fixture below is hand-authored to the format observed on 2026-09-08;
# see greenbutton/sdge.py for provenance.
# ===========================================================================

_METER_META = [
    "Name,TEST CUSTOMER",
    "Address,1 TEST AVENUE  San Diego CA 92101",
    "Account Number,7355849999",
    (
        "Disclaimer,The information contained in this file is intended for the personal "
        "and confidential use of the recipient(s) named above.  Any unauthorized use is "
        "prohibited."
    ),
    "Title,CSV Export Electric Meter(s)",
    "Resource,Electric",
    # NOTE: this preamble row begins with the same token as the table header below.
    # A leading-literal header test would stop here and read the file as headerless.
    "Meter Number,00000000",
    "Interval UOM,Minute(s)",
    "Reading Start,11/1/2022 00:00",
    "Reading End,11/30/2022 23:00",
    "Total Duration,30 Days",
]


def ampm(minutes: int) -> str:
    """Minutes since midnight -> SDG&E's 12-hour label ('12:00 AM', '1:30 PM')."""
    h, m = divmod(minutes, 60)
    suffix = "AM" if h < 12 else "PM"
    return f"{h % 12 or 12}:{m:02d} {suffix}"


def sdge_meter_csv(
    rows: list[tuple],
    *,
    total_usage: float | None = None,
    columns: tuple[str, ...] = ("Consumption", "Generation", "Net"),
    meter: str = "00000000",
) -> str:
    """Build a meter-shape CSV.

    ``rows`` are ``(iso_date, start_minutes, duration_minutes, *values)`` with ``*values``
    lining up with ``columns``. Every cell is quoted, as in the real export.
    """
    meta = list(_METER_META)
    if total_usage is not None:
        meta.append(f"Total Usage,{total_usage}")
    meta.append("UOM,kWh")
    header = ["Meter Number", "Date", "Start Time", "Duration", *columns]
    out = [BOM.rstrip("\n"), *meta, ",".join(header)]
    for row in rows:
        iso, start_min, duration = row[0], row[1], row[2]
        values = row[3 : 3 + len(columns)]
        cells = [meter, _mdY(iso), ampm(start_min), str(duration), *(str(v) for v in values)]
        out.append(",".join(f'"{c}"' for c in cells))
    return "\n".join(out) + "\n"


def meter_hourly_day(
    iso: str,
    *,
    usage: float = 0.25,
    generation: str = "",
    repeat_hour: int | None = None,
) -> list[tuple]:
    """24 hourly meter-shape rows; ``repeat_hour`` duplicates one hour (the DST fold)."""
    rows: list[tuple] = []
    for h in range(24):
        net = usage if generation == "" else round(usage - float(generation), 6)
        rows.append((iso, h * 60, 60, usage, generation, net))
        if repeat_hour is not None and h == repeat_hour:
            rows.append((iso, h * 60, 60, usage, generation, net))
    return rows


# --- happy path ------------------------------------------------------------


def test_meter_shape_parses(tmp_path):
    rows = meter_hourly_day("2022-11-01", usage=0.25)
    text = sdge_meter_csv(rows, total_usage=24 * 0.25)
    series, report = parse_sdge_interval_csv(write(tmp_path, text))

    assert series.utility is Utility.SDGE
    assert report.interval_minutes == 60  # derived from Duration, not an END TIME
    assert report.n_intervals == 24
    assert report.n_gaps == 0
    assert series.total_kwh == pytest.approx(6.0)
    assert series.frame.index[0] == pd.Timestamp("2022-11-01 00:00", tz=LOCAL_TZ)


def test_twelve_hour_times_map_to_the_right_hours(tmp_path):
    # The three cases a 12-hour clock gets wrong: midnight, noon, and late evening.
    rows = meter_hourly_day("2022-11-01")
    text = sdge_meter_csv(rows)
    assert '"12:00 AM"' in text and '"12:00 PM"' in text and '"11:00 PM"' in text

    series, _ = parse_sdge_interval_csv(write(tmp_path, text))
    hours = [t.strftime("%H:%M") for t in series.frame.index]
    assert hours[0] == "00:00"
    assert hours[12] == "12:00"
    assert hours[23] == "23:00"


def test_meter_shape_fifteen_minute(tmp_path):
    rows = [("2022-11-01", m, 15, 0.05, "", 0.05) for m in range(0, 120, 15)]
    _, report = parse_sdge_interval_csv(write(tmp_path, sdge_meter_csv(rows)))
    assert report.interval_minutes == 15
    assert report.n_intervals == 8


def test_meter_shape_pii_is_stripped(tmp_path):
    text = sdge_meter_csv(meter_hourly_day("2022-11-01"))
    series, _ = parse_sdge_interval_csv(write(tmp_path, text))
    dumped = series.meta.model_dump_json()
    assert "TEST CUSTOMER" not in dumped
    assert "1 TEST AVENUE" not in dumped
    assert "7355849999" not in dumped
    assert series.meta.account_tail == "9999"
    assert series.meta.address_zip == "92101"  # unquoted address, no comma before the ZIP


def test_preamble_meter_number_row_is_not_mistaken_for_the_header(tmp_path):
    # Regression: the header is found by signature, not by a leading 'Meter Number,'.
    text = sdge_meter_csv(meter_hourly_day("2022-11-01"))
    assert text.index("Meter Number,00000000") < text.index("Meter Number,Date,Start Time")
    _, report = parse_sdge_interval_csv(write(tmp_path, text))
    assert report.n_intervals == 24


# --- the true 25-hour fall-back day ----------------------------------------


def test_meter_shape_writes_a_true_25_hour_fall_back_day(tmp_path):
    """SDG&E repeats 1:00 AM rather than summing both physical hours as PG&E does.

    The two readings must land on distinct instants (PDT then PST, in file order), the
    day must hold 25 readings, and — unlike the PG&E path — there must be no gap.
    """
    rows = (
        meter_hourly_day("2022-11-05")
        + meter_hourly_day("2022-11-06", repeat_hour=1)
        + meter_hourly_day("2022-11-07")
    )
    series, report = parse_sdge_interval_csv(write(tmp_path, sdge_meter_csv(rows)))

    assert report.dst_fall_back_days == ["2022-11-06"]
    assert report.n_gaps == 0
    assert series.gaps().empty

    day = series.frame.loc["2022-11-06"]
    assert len(day) == 25
    one_am = day.index[day.index.strftime("%H:%M") == "01:00"]
    assert len(one_am) == 2
    assert one_am[0].utcoffset() == pd.Timedelta(hours=-7)  # PDT, first in the file
    assert one_am[1].utcoffset() == pd.Timedelta(hours=-8)  # PST, second in the file


def test_a_label_repeated_three_times_is_not_a_fold(tmp_path):
    rows = meter_hourly_day("2022-11-06", repeat_hour=1)
    rows.insert(3, rows[1])  # a third 1:00 AM
    with pytest.raises(AmbiguousDSTError, match="more than twice"):
        parse_sdge_interval_csv(write(tmp_path, sdge_meter_csv(rows)))


# --- Consumption / Generation registers ------------------------------------


def test_blank_generation_column_is_not_an_export_register(tmp_path):
    # A non-solar meter leaves Generation empty on every row; blanks are not an error.
    text = sdge_meter_csv(meter_hourly_day("2022-11-01", generation=""))
    _, report = parse_sdge_interval_csv(write(tmp_path, text))
    assert not any("export register" in n for n in report.notes)


def test_generation_column_is_surfaced_as_an_export_register(tmp_path):
    text = sdge_meter_csv(meter_hourly_day("2022-11-01", usage=0.3, generation="0.5"))
    series, report = parse_sdge_interval_csv(write(tmp_path, text))
    assert series.total_kwh == pytest.approx(24 * 0.3)  # Consumption billed, not Net
    assert any("export register present" in n and "'Generation'" in n for n in report.notes)
    assert any("12.000 kWh" in n for n in report.notes)


# --- the Total Usage checksum ----------------------------------------------


def test_declared_total_usage_reconciles(tmp_path):
    text = sdge_meter_csv(meter_hourly_day("2022-11-01", usage=0.25), total_usage=6.0)
    _, report = parse_sdge_interval_csv(write(tmp_path, text))
    assert any("reconciles with the summed readings" in n for n in report.notes)


def test_declared_total_usage_mismatch_warns_but_does_not_reject(tmp_path):
    # Deliberately a note, not a rejection: refusing a valid export is the worse failure.
    text = sdge_meter_csv(meter_hourly_day("2022-11-01", usage=0.25), total_usage=999.0)
    series, report = parse_sdge_interval_csv(write(tmp_path, text))
    assert series.total_kwh == pytest.approx(6.0)
    assert any("does NOT match" in n for n in report.notes)


def test_no_declared_total_is_not_an_error(tmp_path):
    text = sdge_meter_csv(meter_hourly_day("2022-11-01"), total_usage=None)
    _, report = parse_sdge_interval_csv(write(tmp_path, text))
    assert not any("Total Usage" in n for n in report.notes)


# --- malformed meter-shape input -------------------------------------------


def test_header_with_neither_end_time_nor_duration_rejected(tmp_path):
    # target the header column, not the preamble's 'Total Duration' row
    text = sdge_meter_csv(meter_hourly_day("2022-11-01")).replace(
        "Start Time,Duration,", "Start Time,Span,", 1
    )
    with pytest.raises(GreenButtonParseError, match=r"neither 'END TIME'.*nor"):
        parse_sdge_interval_csv(write(tmp_path, text))


def test_non_positive_duration_rejected(tmp_path):
    rows = meter_hourly_day("2022-11-01")
    rows[3] = (rows[3][0], rows[3][1], 0, *rows[3][3:])
    with pytest.raises(GreenButtonParseError, match="non-positive DURATION"):
        parse_sdge_interval_csv(write(tmp_path, sdge_meter_csv(rows)))


def test_unparseable_clock_time_rejected(tmp_path):
    text = sdge_meter_csv(meter_hourly_day("2022-11-01")).replace('"3:00 AM"', '"quarter past"')
    with pytest.raises(GreenButtonParseError, match="unparseable clock time"):
        parse_sdge_interval_csv(write(tmp_path, text))


def test_hour_out_of_range_rejected(tmp_path):
    text = sdge_meter_csv(meter_hourly_day("2022-11-01")).replace('"3:00 AM"', '"13:00 AM"')
    with pytest.raises(GreenButtonParseError, match="hour out of range"):
        parse_sdge_interval_csv(write(tmp_path, text))
