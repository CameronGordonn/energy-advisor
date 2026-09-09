"""ACC export tables, the 9-year lock-in, and ACC Plus."""

from __future__ import annotations

from datetime import date

import pytest

from greenbutton.models import Utility
from nem3.acc import (
    CURRENT,
    ExportRateSchedule,
    Vintage,
    acc_plus_table,
    available_vintages,
    load_acc_table,
    table_stem,
)


def test_table_stem_normalizes_utility():
    assert table_stem("SDG&E", 2026) == "sdge_nbt2026"
    assert table_stem(Utility.SDGE, "current") == "sdge_nbtcurrent"


def test_real_sdge_tables_are_present_and_576_per_year():
    for vintage in ("2025", "2026", CURRENT):
        table = load_acc_table("SDG&E", vintage)
        for year in table.years:
            n = len(table.frame.xs(year, level="year"))
            assert n == 576, f"{vintage} {year} has {n} cells, expected 576"


def test_available_vintages_lists_the_committed_files():
    assert set(available_vintages("SDG&E")) >= {"2025", "2026", "current"}


def test_lookup_shape_and_floor():
    table = load_acc_table("SDG&E", 2026)
    grid = table.lookup(2026, "delivery")
    assert grid.shape == (2, 12, 24)  # day_type, month, hour
    assert (grid >= 0).all()  # $0/kWh floor per Sheet 57352-E step 5


def test_lookup_out_of_horizon_raises_not_extrapolates():
    table = load_acc_table("SDG&E", 2026)
    with pytest.raises(ValueError, match="no published export rates"):
        table.lookup(2099, "generation")


def test_citation_present_on_every_table():
    for vintage in ("2025", "2026", CURRENT):
        assert load_acc_table("SDG&E", vintage).citation.strip()


# --- vintage / lock-in ------------------------------------------------------------------


def test_vintage_before_nbt_rejected():
    with pytest.raises(ValueError, match="applications from"):
        Vintage(application_year=2020, pto_date=date(2020, 1, 1))


def test_lock_in_uses_application_year_but_clock_from_pto():
    # Apply in 2026, energise in 2027: the 2026 schedule applies, for nine years from PTO.
    v = Vintage(application_year=2026, pto_date=date(2027, 3, 1))
    assert v.has_lock_in
    assert v.lock_in_through == date(2036, 3, 1)
    assert v.table_vintage(2030) == "2026"  # inside the lock-in -> application vintage
    assert v.table_vintage(2037) == CURRENT  # past it -> current-year table


def test_post_2027_application_has_no_lock_in():
    v = Vintage(application_year=2028, pto_date=date(2028, 6, 1))
    assert not v.has_lock_in
    assert v.lock_in_through is None
    assert v.table_vintage(2028) == CURRENT


def test_locked_vintage_is_a_schedule_not_a_constant(year_index):
    # The whole reason to model the table as 576-per-year: a locked vintage still changes
    # year to year. Mean export rate must differ across calendar years within one vintage.
    table = load_acc_table("SDG&E", 2026)
    means = [
        float((table.lookup(y, "delivery") + table.lookup(y, "generation")).mean())
        for y in (2026, 2030, 2035)
    ]
    assert len({round(m, 4) for m in means}) == 3


# --- ACC Plus ---------------------------------------------------------------------------


def test_pge_acc_plus_matches_sheet_57353e():
    t = acc_plus_table(Utility.PGE)
    assert t.rate(2023, low_income=False) == pytest.approx(0.02200)
    assert t.rate(2026, low_income=False) == pytest.approx(0.00880)
    assert t.rate(2026, low_income=True) == pytest.approx(0.03600)
    # Past the five-year window the adder is zero, not an error.
    assert t.rate(2030, low_income=False) == 0.0


def test_sdge_acc_plus_is_zero_for_every_residential_segment():
    """D.22-12-056 Table 7 adopted $0.000/kWh for SDG&E; Table 11 gives its low-income row
    as "-". Encoded as a positive fact, so nobody "fixes" it by copying PG&E's table."""
    t = acc_plus_table(Utility.SDGE)
    for year in range(2023, 2028):
        assert t.rate(year, low_income=False) == 0.0
        assert t.rate(year, low_income=True) == 0.0
    # The low-income tier is where PG&E/SCE pay the most and SDG&E still pays nothing.
    assert acc_plus_table(Utility.PGE).rate(2026, low_income=True) > 0.0
    assert "22-12-056" in t.citation and "500043682" in t.citation


def test_sdge_acc_plus_zeros_are_cited_not_a_placeholder():
    assert acc_plus_table(Utility.SDGE).citation != acc_plus_table(Utility.PGE).citation
    with pytest.raises(ValueError, match="NOT safe to reuse"):
        acc_plus_table("SCE")


# --- rate resolution --------------------------------------------------------------------


def test_export_rates_are_per_component_and_time_varying(year_index):
    sched = ExportRateSchedule("SDG&E", Vintage(application_year=2026, pto_date=date(2026, 6, 1)))
    rates = sched.rates(year_index)
    assert set(rates.columns) == {"delivery", "generation"}
    # A September 6 p.m. weekday export is worth far more than April noon.
    sep_peak = rates.loc[(year_index.month == 9) & (year_index.hour == 18)].mean().sum()
    apr_noon = rates.loc[(year_index.month == 4) & (year_index.hour == 12)].mean().sum()
    assert sep_peak > apr_noon * 3


def test_acc_plus_active_tracks_nine_years_from_pto():
    sched = ExportRateSchedule("SDG&E", Vintage(application_year=2026, pto_date=date(2026, 6, 1)))
    assert sched.acc_plus_active(date(2030, 1, 1))
    assert not sched.acc_plus_active(date(2036, 1, 1))
