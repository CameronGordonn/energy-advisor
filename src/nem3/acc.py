"""ACC export compensation rates: vintage tables, the 9-year lock-in, and ACC Plus.

Under the Net Billing Tariff (NBT, "Solar Billing Plan"), exported kWh are not netted
against imports; they earn an **Export Compensation Rate** taken from the CPUC Avoided
Cost Calculator. Schedule NBT's own methodology (PG&E Sheet 57352-E) reduces the ACC's
8760 hourly, climate-zone-specific values to a table of 576 per year:

    12 months x {weekday, weekend/holiday} x 24 hours

published separately for a **delivery** and a **generation** component, with a $0/kWh
floor on each. This module is the data layer for that table plus the two time rules that
make "should I install this year or next?" answerable:

**Vintage selection is by APPLICATION year; the clock runs from PTO.** These are two
different dates and conflating them is the classic modeling error. Sheet 57352-E:
Export Compensation Rates are "based on a 'locked-in' nine-year schedule of values for
each hour from the most recent CPUC Avoided Cost Calculator, adopted as of January 1 of
the calendar year of the customer's completed interconnection application date. After the
nine-year lock-in period, **measured from the date of issuance of PTO**, the Export
Compensation Rates will be based on ... the most recent Avoided Cost Calculator."

So an application filed in December 2026 that reaches PTO in March 2027 gets the *2026*
rate schedule for *nine years starting March 2027*. Both halves matter to the answer.

**A locked-in vintage is a schedule, not a constant.** The published tables carry a
different 576-value set for each calendar year of the horizon; locking in fixes *which
forecast* applies, not the rate. Code that treats the vintage as one flat number will
misprice every year after the first.

**ACC Plus** is a separate per-kWh export adder that decays 20%/yr for new applicants and
then holds constant for nine years from PTO. Unlike the Export Compensation Rate it may
offset *any* charge, including non-bypassable charges (Sheet 57359-E, SC 2.c).
"""

from __future__ import annotations

import functools
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from greenbutton.models import LOCAL_TZ, Utility
from tariffs.holidays import holiday_dates
from tariffs.schema import UNVERIFIED

TABLES_DIR = Path(__file__).parent / "acc_tables"

MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DAY_TYPES = ("weekday", "weekend")
COMPONENTS = ("delivery", "generation")

Component = Literal["delivery", "generation"]

#: Vintage label for the non-locked-in ("current year") table — SDG&E's NBT00.
CURRENT = "current"

#: Length of the NBT legacy/lock-in period, from PTO. Schedule NBT Special Condition 7.a:
#: customers "are eligible to continuously stay enrolled on the NBT Schedule for a period
#: of up to 9 years from the original permission to operate (PTO) date."
LOCK_IN_YEARS = 9

#: Last application year that qualifies for a locked-in schedule at all. Sheet 57352-E
#: scopes the lock-in to applications "on or after April 15, 2023 and no later than
#: December 31, 2027"; later applicants take the current-year table every year.
LAST_LOCK_IN_APPLICATION_YEAR = 2027
FIRST_NBT_APPLICATION_YEAR = 2023

#: The utility whose registered holiday calendar sets the weekend/holiday day type for
#: export pricing. SDG&E's "Understanding Solar Billing Plan Export Pricing" lists the
#: same eight days its Electric Rule 1 does, and marks them "Weekend" in ValueName.
_HOLIDAY_CALENDAR = {Utility.SDGE: "sdge_residential", Utility.PGE: "pge_residential"}


class MissingAccTableError(FileNotFoundError):
    """No published ACC export table for this utility/vintage has been imported yet."""


def table_stem(utility: str | Utility, vintage: str | int) -> str:
    """Canonical file stem, e.g. ``sdge_nbt2026`` / ``pge_nbtcurrent``."""
    u = "".join(ch for ch in str(utility).lower() if ch.isalnum())  # "SDG&E" -> "sdge"
    return f"{u}_nbt{vintage}"


class AccTable(BaseModel):
    """One published export-rate table: 576 cells per calendar year, per component.

    Values are $/kWh at the meter, already floored at $0/kWh by the utility per the
    Sheet 57352-E methodology (step 5). ``frame`` is indexed by
    (year, month, day_type, hour) with one column per component.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    utility: str
    vintage: str
    citation: str = Field(min_length=1)
    retrieved: date
    source_file: str
    frame: pd.DataFrame

    @field_validator("citation")
    @classmethod
    def _cited(cls, v: str) -> str:
        if v.strip().upper() == UNVERIFIED or not v.strip():
            raise ValueError("ACC table citation is mandatory and must not be UNVERIFIED")
        return v

    @property
    def years(self) -> list[int]:
        return sorted({int(y) for y in self.frame.index.get_level_values("year")})

    def lookup(self, year: int, component: Component) -> np.ndarray:
        """(2, 12, 24) array of $/kWh for ``year``: [day_type, month-1, hour].

        Day-type axis matches :data:`DAY_TYPES` — 0 = weekday, 1 = weekend/holiday.
        Raises on a year outside the published horizon rather than extrapolating.
        """
        if year not in self.years:
            raise ValueError(
                f"{self.utility} NBT{self.vintage}: no published export rates for {year} "
                f"(table covers {self.years[0]}-{self.years[-1]}). Import a newer file "
                "rather than extrapolating an avoided-cost forecast."
            )
        out = np.empty((2, 12, 24), dtype=float)
        sub = self.frame.xs(year, level="year")[component]
        for di, dt in enumerate(DAY_TYPES):
            block = sub.xs(dt, level="day_type")
            out[di] = block.unstack("hour").to_numpy()
        return out


@functools.lru_cache(maxsize=16)
def load_acc_table(
    utility: str | Utility, vintage: str | int, *, tables_dir: str | Path = TABLES_DIR
) -> AccTable:
    """Load a published ACC export table + its mandatory citation manifest.

    Raises :class:`MissingAccTableError` with the download instructions when the table has
    not been imported — the alternative would be inventing an avoided-cost forecast, which
    is the one thing this repo never does.
    """
    d = Path(tables_dir)
    stem = table_stem(utility, vintage)
    csv, manifest = d / f"{stem}.csv.gz", d / f"{stem}.yaml"
    if not csv.exists() or not manifest.exists():
        raise MissingAccTableError(
            f"no ACC export table for {utility} vintage {vintage!r} (looked for "
            f"{csv.name} + {manifest.name} in {d}). Download the utility's NBT export "
            "pricing file and import it with scripts/build_acc_tables.py; SDG&E publishes "
            "at sdge.com/solar/solar-billing-plan/export-pricing, PG&E at "
            "pge.com/energyexportcredit."
        )
    meta = yaml.safe_load(manifest.read_text())
    frame = pd.read_csv(csv).set_index(["year", "month", "day_type", "hour"]).sort_index()
    return AccTable(
        utility=meta["utility"],
        vintage=str(meta["vintage"]),
        citation=meta["citation"],
        retrieved=date.fromisoformat(str(meta["retrieved"])),
        source_file=meta["source_file"],
        frame=frame,
    )


def available_vintages(utility: str | Utility, *, tables_dir: str | Path = TABLES_DIR) -> list[str]:
    prefix = table_stem(utility, "")
    return sorted(p.stem.removeprefix(prefix) for p in Path(tables_dir).glob(f"{prefix}*.yaml"))


# --- ACC Plus --------------------------------------------------------------------------


class AccPlusTable(BaseModel):
    """The ACC Plus (Energy Export Bonus Credit) adder, $/kWh exported, by application year.

    Sheet 57353-E: "The ACC Plus applicable to a given customer will be based on the
    customer's calendar year of completed interconnection application date. ... The
    applicable ACC Plus adder will remain constant for a customer for nine years from the
    customer's Permission to Operate (PTO) date."

    Not available to NEM/NEM2 transition customers, change-of-party customers,
    non-residential customers, or systems required by building code — so a caller that
    cannot assert eligibility must pass ``eligible=False`` rather than take the default.
    """

    model_config = ConfigDict(frozen=True)

    citation: str = Field(min_length=1)
    residential: dict[int, float]
    residential_low_income: dict[int, float]

    def rate(self, application_year: int, *, low_income: bool) -> float:
        table = self.residential_low_income if low_income else self.residential
        if application_year not in table:
            # Past the five-year window the adder is zero by construction ("will decrease
            # by 20 percent annually ... until the adder reaches zero"), but before the
            # tariff existed there is no rate at all.
            if application_year < FIRST_NBT_APPLICATION_YEAR:
                raise ValueError(
                    f"application year {application_year} predates the NBT (first year "
                    f"{FIRST_NBT_APPLICATION_YEAR})"
                )
            return 0.0
        return table[application_year]


#: PG&E Schedule NBT, "Adopted Avoided Cost Calculator Plus Adder (ACC Plus)" table,
#: Cal. P.U.C. Sheet 57353-E (Advice 7174-E, D.23-11-068, effective 2024-02-15). The adder
#: is set by CPUC decision D.22-12-056 rather than by each utility, but only PG&E's sheet
#: has been read here — see the note in :func:`acc_plus_table`.
PGE_ACC_PLUS = AccPlusTable(
    citation=(
        "PG&E Schedule NBT (Net Billing Tariff), RATES section D, 'Adopted Avoided Cost "
        "Calculator Plus Adder (ACC Plus)', Cal. P.U.C. Sheet 57353-E, Advice 7174-E, "
        "D.23-11-068, effective 2024-02-15; retrieved 2026-07-23."
    ),
    residential={2023: 0.02200, 2024: 0.01760, 2025: 0.01320, 2026: 0.00880, 2027: 0.00440},
    residential_low_income={
        2023: 0.09000,
        2024: 0.07200,
        2025: 0.05400,
        2026: 0.03600,
        2027: 0.01800,
    },
)


def acc_plus_table(utility: str | Utility) -> AccPlusTable:
    """ACC Plus adder table for a utility.

    Only PG&E's sheet has been read. The adder values are set statewide by D.22-12-056,
    so SDG&E's are very likely identical — but "very likely" is not a citation, so this
    raises for SDG&E rather than reusing PG&E's numbers under SDG&E's name.
    """
    if Utility(utility) is Utility.PGE:
        return PGE_ACC_PLUS
    raise ValueError(
        f"no ACC Plus table confirmed for {utility}. It is NOT safe to reuse PG&E's values: "
        "although D.22-12-056 framed the adder statewide, secondary sources report SDG&E "
        "residential customers may not receive ACC Plus at all. Confirm from the "
        f"{utility} Schedule NBT sheet before pricing it; until then settle with "
        "acc_plus_eligible=False (no adder), which is the conservative assumption."
    )


# --- vintage / lock-in -----------------------------------------------------------------


class Vintage(BaseModel):
    """A customer's NBT vintage: which ACC forecast applies, and until when.

    ``application_year`` selects the rate schedule; ``pto_date`` starts the nine-year
    clock. Keeping them separate is what lets the report answer "apply this year, energise
    next year" — the case where the two dates fall in different vintages.
    """

    model_config = ConfigDict(frozen=True)

    application_year: int
    pto_date: date

    @field_validator("application_year")
    @classmethod
    def _plausible(cls, v: int) -> int:
        if v < FIRST_NBT_APPLICATION_YEAR:
            raise ValueError(
                f"NBT applies to interconnection applications from "
                f"{FIRST_NBT_APPLICATION_YEAR} (April 15) onward; got {v}"
            )
        return v

    @property
    def has_lock_in(self) -> bool:
        """Whether this customer gets a locked-in nine-year schedule at all."""
        return self.application_year <= LAST_LOCK_IN_APPLICATION_YEAR

    @property
    def lock_in_through(self) -> date | None:
        """Last day of the locked-in schedule: the 9th anniversary of PTO.

        Special Condition 7.a actually ends the period "at the conclusion of the
        Customer's applicable Relevant Period on or after the 9th anniversary of the
        original PTO date", i.e. at the next annual true-up, which can be up to a year
        later. This models the anniversary itself — the conservative end — because the
        true-up month is a per-customer billing fact the engine is not given. The
        difference only ever *understates* the locked-in benefit.
        """
        if not self.has_lock_in:
            return None
        return self.pto_date.replace(year=self.pto_date.year + LOCK_IN_YEARS)

    def table_vintage(self, year: int) -> str:
        """Which published table prices exports in calendar ``year``.

        Returns the application-year vintage while the lock-in covers the year, else
        :data:`CURRENT`. A year straddling the anniversary is treated as locked in for
        the whole year; the residual is a partial-year effect the report notes.
        """
        through = self.lock_in_through
        if through is None or year > through.year:
            return CURRENT
        return str(self.application_year)


# --- the rate schedule -----------------------------------------------------------------


class ExportRateSchedule:
    """Resolves the $/kWh export compensation for any timestamp, honoring the lock-in.

    Rates are returned **per component** because Schedule NBT accrues and applies the two
    separately: Sheet 57359-E, SC 2.d — "Export credits for generation avoided costs will
    only offset volumetric (kwh) generation charges ... and export credits for delivery
    avoided costs will only offset volumetric (kwh) delivery charges". Summing them into
    one number, as consumer calculators do, overstates the credit whenever one side runs
    out of charges to offset — and for a CCA customer the generation side is not PG&E's to
    credit at all (SC 2.a).
    """

    def __init__(
        self,
        utility: str | Utility,
        vintage: Vintage,
        *,
        tables_dir: str | Path = TABLES_DIR,
        holiday_calendar: str | None = None,
    ) -> None:
        self.utility = Utility(utility)
        self.vintage = vintage
        self.tables_dir = tables_dir
        self.holiday_calendar = holiday_calendar or _HOLIDAY_CALENDAR[self.utility]

    def table_for(self, year: int) -> AccTable:
        return load_acc_table(
            self.utility, self.vintage.table_vintage(year), tables_dir=self.tables_dir
        )

    def day_type_codes(self, index: pd.DatetimeIndex) -> np.ndarray:
        """0 = weekday, 1 = weekend/holiday, matching :data:`DAY_TYPES`."""
        years = {int(y) for y in index.year.unique()}
        holidays = set().union(*(holiday_dates(self.holiday_calendar, y) for y in years))
        weekend = index.dayofweek.values >= 5
        if holidays:
            weekend = weekend | np.isin(index.date, list(holidays))
        return weekend.astype(np.int8)

    def rates(self, index: pd.DatetimeIndex) -> pd.DataFrame:
        """$/kWh per component for each timestamp in ``index`` (tz-aware local)."""
        if index.tz is None:
            raise ValueError("export-rate lookup needs a tz-aware local index")
        dt = self.day_type_codes(index)
        months = index.month.values - 1
        hours = index.hour.values
        years = index.year.values

        out = {c: np.empty(len(index), dtype=float) for c in COMPONENTS}
        for year in np.unique(years):
            mask = years == year
            table = self.table_for(int(year))
            for c in COMPONENTS:
                grid = table.lookup(int(year), c)
                out[c][mask] = grid[dt[mask], months[mask], hours[mask]]
        return pd.DataFrame(out, index=index)

    def acc_plus_rate(self, *, low_income: bool, eligible: bool = True) -> float:
        """Flat $/kWh ACC Plus adder for this vintage, or 0.0 when not eligible."""
        if not eligible:
            return 0.0
        return acc_plus_table(self.utility).rate(
            self.vintage.application_year, low_income=low_income
        )

    def acc_plus_active(self, day: date) -> bool:
        """Whether the adder still applies — nine years from PTO, same as the lock-in."""
        return day < self.vintage.pto_date.replace(year=self.vintage.pto_date.year + LOCK_IN_YEARS)


def local_index(frame: pd.DataFrame) -> pd.DatetimeIndex:
    """The tz-aware local index of an interval frame (helper for callers)."""
    idx = frame.index
    if not isinstance(idx, pd.DatetimeIndex) or idx.tz is None:
        raise ValueError(f"expected a tz-aware DatetimeIndex in {LOCAL_TZ}")
    return idx
