"""ACC export tables, the 9-year lock-in, and ACC Plus."""

from __future__ import annotations

from datetime import date

import pytest
import yaml

from greenbutton.models import Utility
from nem3.acc import (
    CURRENT,
    ExportRateSchedule,
    MissingAccTableError,
    Vintage,
    acc_plus_table,
    available_vintages,
    carry_forward_verifications,
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


@pytest.mark.parametrize("utility", ["SDG&E", "PG&E"])
def test_the_2027_vintage_still_has_no_published_table(utility):
    """⭐ The one vintage the "when to install" question can still turn on, and nobody has
    published it. Asserted so the re-check is not a chore someone has to remember.

    2027 is the LAST application year that earns a nine-year lock-in, so it is the last
    vintage on which "apply this year or next?" can ever have a dollar answer. Raising is
    the correct behaviour, not a bug: inventing an avoided-cost forecast is the one thing
    this repo never does.

    **When this test fails, that is the signal to act**, not to delete it. A utility has
    published, and the answer to a product question this tool is built to answer has just
    become computable — import the table with `scripts/build_acc_tables.py`.

    Re-checked 2026-09-16: `sdge.com/solar/solar-billing-plan/export-pricing` offers 2023,
    2024, 2025 and 2026 only. ⚠ Note the CPUC adopted the 2026 ACC update on 2026-09-03
    (D.26-09-007), which is the input a 2027 vintage is built from — so this is likelier to
    change soon than it has been at any previous re-check.
    """
    with pytest.raises(MissingAccTableError):
        load_acc_table(utility, 2027)


#: How many calendar years of each utility's **floating** (NBT00) table are *effective*
#: rather than illustrative, counted from the first year of that table's horizon. Both
#: numbers are quoted from the "Solar Billing Plan Export Rates Readme.txt" shipped inside
#: the download the table was imported from:
#:
#: * SDG&E — "For NBT00 customers, only those rates for Pacific Standard Time for the
#:   current year are actual effective rates, and all rates after that are for
#:   illustrative purposes only." Its horizon starts 2026, so: one year.
#: * PG&E — "For NBT00 customers, only those rates for Pacific Standard Time calendar year
#:   2025 and 2026 are actual effective rates, and all rates after that are for
#:   illustrative purposes only." Its horizon starts 2025, so: two years.
#:
#: Counted from the horizon rather than written as a year so that a re-import moves the
#: window by itself. Edit these counts only if a future readme changes the grant.
FLOATING_EFFECTIVE_YEARS = {"SDG&E": 1, "PG&E": 2}


@pytest.mark.parametrize("utility", sorted(FLOATING_EFFECTIVE_YEARS))
def test_the_floating_table_has_not_outlived_its_own_effective_window(utility):
    """⭐ The floating (NBT00) table expires by its own readme, and both utilities' expire
    on the same date: 2026-12-31.

    This is the gate the repo did not have. Every "the lock-in is worth $0" finding —
    SDG&E's NBT25/NBT26/NBT00 being one table wearing three labels, PG&E's NBT26 equalling
    NBT00 cell for cell — is a statement about the *currently published* floating table.
    The vintage tables are frozen by the lock-in; the floating one is not, and when it
    moves those findings change without any file in this repo changing.

    Both readmes date that move. SDG&E's current-year file is effective for the current
    calendar year only, PG&E's for 2025 and 2026, so on **2027-01-01 neither committed
    table carries an effective rate for the year being priced** and this test fails.

    Re-verified 2026-09-16, after the CPUC adopted the 2026 ACC update on 2026-09-03
    (D.26-09-007): every one of the eight committed tables' source files is still
    **byte-identical** to the one it was imported from (SDG&E's three CSVs and PG&E's
    36 MB zip, sha256 unchanged). The adoption has not yet reached either utility's
    published export pricing. The republish is due before the window above closes.

    **When this fails, re-download and re-import both utilities** with
    ``scripts/build_acc_tables.py``, then re-run this file and ``test_acc_pge.py``: if the
    new floating table differs from NBT26, the nine-year lock-in has an observable dollar
    value for the first time and several findings need restating.
    """
    table = load_acc_table(utility, CURRENT)
    effective_through = table.years[0] + FLOATING_EFFECTIVE_YEARS[utility] - 1
    assert date.today().year <= effective_through, (
        f"{utility}'s floating table (imported {table.retrieved}, horizon from "
        f"{table.years[0]}) carries effective rates only through {effective_through}; "
        f"it is now {date.today().year}. Re-download and re-import it — every rate it "
        "prices for the current year is illustrative, not effective."
    )


def test_a_verification_date_does_not_survive_the_file_it_described(tmp_path):
    """The invalidation rule for the re-check dates, which is the whole point of them.

    A date saying "the publisher still served these exact bytes" is evidence only about
    the bytes it was measured against. When the utility reissues the file, the new table
    starts with one date, not an inherited history — the repo's recurring failure is a
    cached value that outlives what it described.
    """
    manifest = tmp_path / "sdge_nbtcurrent.yaml"
    manifest.write_text(
        yaml.safe_dump({"source_sha256": "abc", "verified": ["2026-07-23", "2026-09-16"]})
    )
    same = carry_forward_verifications(manifest, "abc", date(2026, 12, 1))
    assert same == ["2026-07-23", "2026-09-16", "2026-12-01"]

    reissued = carry_forward_verifications(manifest, "def", date(2026, 12, 1))
    assert reissued == ["2026-12-01"]

    fresh = carry_forward_verifications(tmp_path / "nope.yaml", "abc", date(2026, 12, 1))
    assert fresh == ["2026-12-01"]


@pytest.mark.parametrize("utility", ["SDG&E", "PG&E"])
def test_every_acc_table_records_when_its_source_was_last_re_checked(utility):
    """``retrieved`` is when the bytes were fetched; it cannot say whether they are stale.

    Only a re-check can, so the re-check carries its own date in the manifest and the
    importer keeps it only while the source sha256 is unchanged. Without this, "imported
    2026-07-23" and "confirmed unchanged 2026-09-16" are indistinguishable, and the second
    is the one that answers "is this still what the utility publishes?".
    """
    for vintage in available_vintages(utility):
        table = load_acc_table(utility, vintage)
        assert table.verified, f"{utility} NBT{vintage} records no re-check date"
        assert max(table.verified) >= table.retrieved


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


def test_sdge_vintages_are_one_table_wearing_three_labels():
    """NBT25, NBT26 and NBT00 are identical on every overlapping year, so SDG&E's
    nine-year lock-in is currently worth exactly $0.

    Stated in HANDOFF and relied on by ``test_payback.py``, but it was never asserted
    directly — and it is the kind of fact that stops being true at the next ACC adoption
    without anything else in the repo noticing. PG&E is the contrast: its vintages fork
    into two genuinely different schedules (``test_acc_pge.py``), which is why "lock in
    before rates drop" has to be answered per territory rather than once.
    """
    frames = {v: load_acc_table("SDG&E", v).frame.sort_index() for v in ("2025", "2026", CURRENT)}
    for a, b in (("2025", "2026"), ("2026", CURRENT)):
        years = sorted(
            set(frames[a].index.get_level_values("year"))
            & set(frames[b].index.get_level_values("year"))
        )
        left = frames[a][frames[a].index.get_level_values("year").isin(years)]
        right = frames[b][frames[b].index.get_level_values("year").isin(years)]
        assert left.equals(right), f"SDG&E NBT{a} and NBT{b} have diverged — re-check"
