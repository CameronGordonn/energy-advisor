"""PG&E's ACC export tables: the import, its cross-check, and the vintage asymmetry.

Two things are pinned here that the SDG&E tests cannot pin.

**1. The import is cross-checked against a second, independent PG&E publication.**
The tables in ``src/nem3/acc_tables/pge_nbt*.csv.gz`` come from the MIDAS upload CSVs at
pge.com/eecvalues. PG&E *also* prints a customer-facing price sheet per vintage at
pge.com/energyexportcredit, showing one calendar year of the same data. Those printed
cells are transcribed into :data:`PRINTED_2026` below and compared against the imported
table. They agree everywhere except the daylight-saving folds — see
:data:`PRINTED_DST_DISAGREEMENTS`, which pins the disagreement rather than papering over
it.

**2. PG&E's vintages actually differ; SDG&E's do not.** This is the first evidence in this
repo that "lock in before the export rates drop" is a territory-specific claim rather than
an empty one everywhere — and, read carefully, PG&E's tables do not support the installer
version of it either. See :func:`test_pge_vintage_gap_is_structural_by_hour_of_day`.
"""

from __future__ import annotations

import numpy as np
import pytest

from nem3.acc import CURRENT, load_acc_table

PGE_VINTAGES = ("2023", "2024", "2025", "2026", CURRENT)

#: Cells transcribed by hand from PG&E's printed "Solar Billing Plan — Energy Export
#: Credit (EEC) Values" price sheets (pge.com/energyexportcredit, member files dated
#: 2024-12-18, retrieved 2026-09-09). Every one of those four sheets prints **calendar
#: year 2026** values for its own interconnection application year, so all of these are
#: year-2026 cells. Keyed vintage -> (month, day_type, hour) -> (delivery, generation).
#:
#: The sheet's column headings are "Energy Delivered" and "Energy **Produced**"; Produced
#: is the generation component, which its own footnote 2 limits to customers taking
#: bundled generation from PG&E. Getting that mapping backwards would swap a ~$0.09/kWh
#: number with a ~$0.0009/kWh one, so the mapping is pinned separately, on a cell where
#: the two components are orders of magnitude apart.
PRINTED_2026: dict[str, dict[tuple[int, str, int], tuple[float, float]]] = {
    "2023": {
        (1, "weekday", 0): (0.00395, 0.05555),
        (4, "weekday", 15): (0.00000, 0.00694),
        (7, "weekday", 17): (0.15572, 0.07614),
        (8, "weekend", 20): (0.12831, 0.54502),
        (9, "weekday", 19): (0.06685, 2.45454),
        (12, "weekend", 12): (0.00319, 0.05031),
    },
    "2024": {
        (1, "weekday", 0): (0.00395, 0.05555),
        (4, "weekday", 15): (0.00000, 0.00694),
        (7, "weekday", 17): (0.15572, 0.07614),
        (8, "weekend", 20): (0.12831, 0.54502),
        (9, "weekday", 19): (0.06685, 2.45454),
        (12, "weekend", 12): (0.00319, 0.05031),
    },
    "2025": {
        (1, "weekday", 0): (0.00089, 0.09342),
        (4, "weekday", 15): (0.00006, 0.00012),
        (7, "weekday", 17): (0.25932, 0.06615),
        (8, "weekend", 20): (0.00187, 1.04281),
        (9, "weekday", 19): (0.00193, 0.59312),
        (12, "weekend", 12): (0.00021, 0.02238),
    },
    "2026": {
        (1, "weekday", 0): (0.00089, 0.09342),
        (4, "weekday", 15): (0.00006, 0.00012),
        (7, "weekday", 17): (0.25932, 0.06615),
        (8, "weekend", 20): (0.00187, 1.04281),
        (9, "weekday", 19): (0.00193, 0.59312),
        (12, "weekend", 12): (0.00021, 0.02238),
    },
}

#: The top of the printed sheet's "Highest value for credits" band, per vintage:
#: (generation, delivery). This is the **weekday** table's maximum — in the 2025/2026
#: sheets the weekend table reaches 1.04281, above the printed 0.99821 ceiling — so it
#: doubles as a whole-table check on 288 of the 576 imported cells rather than a spot one.
PRINTED_WEEKDAY_MAX_2026: dict[str, tuple[float, float]] = {
    "2023": (2.45454, 0.33251),
    "2024": (2.45454, 0.33251),
    "2025": (0.99821, 0.35038),
    "2026": (0.99821, 0.35038),
}

#: The **only** cells where the MIDAS CSV and the printed sheet disagree, as
#: (vintage, month, day_type, hour) -> (printed delivery, printed generation).
#:
#: Every one is a *weekend* cell in March or November — the two months holding a
#: daylight-saving transition, both of which fall on a Sunday. PG&E's readme says the
#: hour labels "have been adjusted to account for daylight savings time"; the 23-hour
#: spring day and 25-hour fall day evidently get averaged into the monthly weekend
#: figure slightly differently by the two publications. The imported table follows the
#: MIDAS CSV, because that is the machine-readable file PG&E uploads and the only one
#: carrying the full 20-year horizon.
#:
#: Worth at most $0.0005/kWh on two hours of ~9 weekend days a year, so it moves no
#: recommendation — but it is pinned as a known, bounded disagreement so that nobody
#: later "fixes" the importer to chase the printed number, and so a future import that
#: disagrees somewhere *else* is caught.
PRINTED_DST_DISAGREEMENTS: dict[tuple[str, int, str, int], tuple[float, float]] = {
    ("2023", 3, "weekend", 2): (0.00343, 0.05152),
    ("2023", 3, "weekend", 3): (0.00314, 0.04888),
    ("2023", 11, "weekend", 1): (0.00675, 0.05015),
    ("2023", 11, "weekend", 2): (0.00344, 0.04940),
    ("2023", 11, "weekend", 3): (0.00339, 0.04893),
    ("2024", 3, "weekend", 2): (0.00343, 0.05152),
    ("2024", 3, "weekend", 3): (0.00314, 0.04888),
    ("2024", 11, "weekend", 1): (0.00675, 0.05015),
    ("2024", 11, "weekend", 2): (0.00344, 0.04940),
    ("2024", 11, "weekend", 3): (0.00339, 0.04893),
    ("2025", 11, "weekend", 1): (0.00099, 0.07959),
    ("2025", 11, "weekend", 2): (0.00074, 0.07883),
    ("2026", 11, "weekend", 1): (0.00099, 0.07959),
    ("2026", 11, "weekend", 2): (0.00074, 0.07883),
}


def _cell(vintage: str, year: int, month: int, day_type: str, hour: int) -> tuple[float, float]:
    frame = load_acc_table("PG&E", vintage).frame
    row = frame.loc[(year, month, day_type, hour)]
    return float(row["delivery"]), float(row["generation"])


# --- the import ------------------------------------------------------------------------


@pytest.mark.parametrize("vintage", PGE_VINTAGES)
def test_every_pge_vintage_is_present_and_576_cells_per_year(vintage):
    table = load_acc_table("PG&E", vintage)
    for year in table.years:
        n = len(table.frame.xs(year, level="year"))
        assert n == 576, f"PG&E NBT{vintage} {year} has {n} cells, expected 576"


@pytest.mark.parametrize("vintage", PGE_VINTAGES)
def test_every_pge_table_carries_its_citation_and_a_20_year_horizon(vintage):
    table = load_acc_table("PG&E", vintage)
    assert "pge.com/eecvalues" in table.citation
    assert "E-5301" in table.citation  # the resolution that requires 20 years posted
    # CPUC Resolution E-5301 requires 20 years published, of which only 9 from PTO bind.
    assert len(table.years) == 20, f"NBT{vintage} covers {table.years}"


@pytest.mark.parametrize("vintage", PGE_VINTAGES)
def test_pge_export_rates_are_floored_at_zero(vintage):
    """Sheet 57352-E step 5 floors each component at $0/kWh before publication."""
    table = load_acc_table("PG&E", vintage)
    assert (table.frame[["delivery", "generation"]].to_numpy() >= 0).all()


# --- cross-check against the printed price sheets ----------------------------------------


@pytest.mark.parametrize("vintage", sorted(PRINTED_2026))
def test_imported_cells_match_the_printed_price_sheet(vintage):
    """Spot cells transcribed off PG&E's printed PDF must reproduce from the MIDAS import.

    A checksum would prove the file did not change; this proves the file says what PG&E
    printed. The two are separate publications from separate pipelines.
    """
    for (month, day_type, hour), (delivery, generation) in PRINTED_2026[vintage].items():
        got_delivery, got_generation = _cell(vintage, 2026, month, day_type, hour)
        where = f"NBT{vintage} 2026-{month:02d} {day_type} HS{hour}"
        assert got_delivery == pytest.approx(delivery, abs=1e-5), f"{where} delivery"
        assert got_generation == pytest.approx(generation, abs=1e-5), f"{where} generation"


@pytest.mark.parametrize("vintage", sorted(PRINTED_2026))
def test_produced_is_generation_and_delivered_is_delivery(vintage):
    """The printed sheet's "Produced" column is the generation component, not delivery.

    Pinned separately from the cell values because swapping the two columns would still
    "match a printed number" — just the wrong one. The September 7 p.m. weekday cell is
    used because generation runs 37x delivery there on the older vintages and 300x on the
    newer ones, so a swap cannot hide. Note that the ordering is *not* universal — in the
    July 5 p.m. cell of the 2023 sheet delivery is the larger of the two — which is
    exactly why the check names a cell rather than asserting a rule.
    """
    delivery, generation = PRINTED_2026[vintage][(9, "weekday", 19)]
    assert generation > 10 * delivery
    got_delivery, got_generation = _cell(vintage, 2026, 9, "weekday", 19)
    assert got_generation == pytest.approx(generation, abs=1e-5)
    assert got_delivery == pytest.approx(delivery, abs=1e-5)


@pytest.mark.parametrize("vintage", sorted(PRINTED_WEEKDAY_MAX_2026))
def test_printed_highest_value_band_matches_the_imported_weekday_table(vintage):
    """The sheet's printed "Highest value" ceiling is the weekday maximum, and only that.

    Checks all 288 weekday cells of calendar 2026 at once, and pins the fact that the
    printed band ignores the weekend table — in 2025/2026 the weekend maximum (1.04281)
    is above the printed ceiling, so a reader taking the band as a whole-sheet range
    would be wrong.
    """
    printed_generation, printed_delivery = PRINTED_WEEKDAY_MAX_2026[vintage]
    year_2026 = load_acc_table("PG&E", vintage).frame.xs(2026, level="year")
    weekday = year_2026.xs("weekday", level="day_type")
    assert weekday["generation"].max() == pytest.approx(printed_generation, abs=1e-5)
    assert weekday["delivery"].max() == pytest.approx(printed_delivery, abs=1e-5)

    weekend_max = year_2026.xs("weekend", level="day_type")["generation"].max()
    if vintage in ("2025", "2026"):
        assert weekend_max > printed_generation
    else:
        assert weekend_max <= printed_generation


def test_the_only_printed_disagreements_are_dst_weekend_cells():
    """The CSV/PDF gap is confined to DST-transition weekend cells, and is bounded.

    Both directions matter. Each listed cell must still *disagree* — if a re-import
    silently started matching the printed sheet, the importer's DST handling changed and
    that should be noticed. And each must disagree only slightly.
    """
    for (vintage, month, day_type, hour), printed in PRINTED_DST_DISAGREEMENTS.items():
        assert month in (3, 11), "a DST transition only happens in March or November"
        assert day_type == "weekend", "both 2026 transitions fall on a Sunday"
        got = _cell(vintage, 2026, month, day_type, hour)
        gaps = [abs(g - p) for g, p in zip(got, printed, strict=True)]
        where = f"NBT{vintage} 2026-{month:02d} {day_type} HS{hour}"
        assert max(gaps) > 1e-5, f"{where}: expected a known disagreement, tables now agree"
        assert max(gaps) < 1e-3, f"{where}: disagreement grew to {max(gaps)}"


# --- the vintage asymmetry ---------------------------------------------------------------


def _overlapping(a: str, b: str):
    fa, fb = (load_acc_table("PG&E", v).frame.sort_index() for v in (a, b))
    years = sorted(set(fa.index.get_level_values("year")) & set(fb.index.get_level_values("year")))
    sa = fa[fa.index.get_level_values("year").isin(years)]
    sb = fb[fb.index.get_level_values("year").isin(years)]
    return sa, sb


@pytest.mark.parametrize(("a", "b"), [("2023", "2024"), ("2025", "2026"), ("2026", CURRENT)])
def test_pge_vintages_that_collapse_into_one_table(a, b):
    """PG&E publishes five files but only **two** distinct rate schedules.

    NBT23 == NBT24, and NBT25 == NBT26 == NBT00, cell for cell on every overlapping year.
    Consequences worth stating out loud: a 2023 applicant and a 2024 applicant hold the
    same schedule, and — the one that matters to someone deciding today — locking in the
    2026 vintage buys exactly the floating NBT00 table, so the lock-in confers no
    *observable* advantage over not having one.
    """
    sa, sb = _overlapping(a, b)
    assert sa.equals(sb), f"NBT{a} and NBT{b} were expected to be identical"


def test_pge_vintages_are_not_all_identical_unlike_sdge():
    """The headline asymmetry: on PG&E the vintage is a real fork, on SDG&E it is not.

    SDG&E's NBT25/NBT26/NBT00 are one table wearing three labels, so its nine-year
    lock-in is worth exactly $0. PG&E's two clusters are far apart — dollars per kWh
    apart in the extreme cells — so "which vintage" is a real question in PG&E territory
    and a non-question in SDG&E's. Any tool that answers it the same way in both is
    wrong in one of them.
    """
    early, late = _overlapping("2024", "2026")
    gap = (early - late).abs()
    assert gap["generation"].max() > 1.0
    assert gap["delivery"].max() > 0.4

    sdge_a, sdge_b = (load_acc_table("SDG&E", v).frame.sort_index() for v in ("2025", "2026"))
    common = sorted(
        set(sdge_a.index.get_level_values("year")) & set(sdge_b.index.get_level_values("year"))
    )
    left = sdge_a[sdge_a.index.get_level_values("year").isin(common)]
    right = sdge_b[sdge_b.index.get_level_values("year").isin(common)]
    assert left.equals(right), "SDG&E's vintages have stopped being identical — re-check"


def _weekday_band_mean(vintage: str, year: int, hours: range) -> float:
    table = load_acc_table("PG&E", vintage)
    total = table.lookup(year, "delivery") + table.lookup(year, "generation")
    return float(total[0][:, list(hours)].mean())  # [0] = weekday


@pytest.mark.parametrize("year", [2026, 2028, 2030, 2032, 2034])
def test_pge_vintage_gap_is_structural_by_hour_of_day(year):
    """The older vintage wins midday; the newer wins overnight, by far more.

    This is the substance behind "lock in before rates drop", and it does not support
    the pitch:

    * **Midday (09-15), where a solar-only array actually exports** — NBT23/24 is ahead
      in every published year, but only by $0.005-0.020/kWh. Close to a wash.
    * **Overnight (00-06), reachable only with a battery** — NBT25/26 is ahead in every
      year, and by 2030 it is ahead by more than $0.10/kWh, an order of magnitude more
      than the midday gap runs the other way.

    So the vintage question in PG&E territory is really a *battery* question. For a
    solar-only customer it is nearly immaterial; for a customer who can shift the export
    hour, the newer vintage is the better one — the reverse of "get in before the rates
    drop". Held as a parametrised test rather than prose because a future re-import that
    inverted either band would be a genuinely different recommendation.
    """
    midday_early = _weekday_band_mean("2024", year, range(9, 16))
    midday_late = _weekday_band_mean("2026", year, range(9, 16))
    assert midday_early > midday_late
    assert midday_early - midday_late < 0.025

    overnight_early = _weekday_band_mean("2024", year, range(0, 7))
    overnight_late = _weekday_band_mean("2026", year, range(0, 7))
    assert overnight_late > overnight_early
    if year >= 2030:
        assert overnight_late - overnight_early > 0.10


def test_pge_evening_advantage_flips_vintage_partway_through_the_lock_in():
    """The 5-9 p.m. band is the one place the older vintage's edge is large — and it dies.

    NBT23/24 pays more in the evening peak through 2029 and less from 2030 onward. A
    nine-year lock-in taken in 2023 therefore spans the flip, which is exactly why a
    single-year comparison — the only thing PG&E's printed price sheet supports, since it
    prints one calendar year — cannot answer the timing question. The 20-year MIDAS
    horizon can.
    """
    evening = range(17, 22)
    early_wins = [
        y
        for y in range(2026, 2035)
        if _weekday_band_mean("2024", y, evening) > _weekday_band_mean("2026", y, evening)
    ]
    assert early_wins == [2026, 2027, 2028, 2029]


def test_a_locked_vintage_still_varies_year_to_year_on_pge():
    """Same invariant the SDG&E tests pin: a vintage fixes the forecast, not the rate."""
    means = [
        float(np.mean(load_acc_table("PG&E", "2026").lookup(y, "generation")))
        for y in (2026, 2030, 2035)
    ]
    assert len({round(m, 4) for m in means}) == 3
