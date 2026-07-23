"""Observed-holiday calendars, by name, for day-type-aware TOU.

CA IOUs price observed holidays on the weekend/holiday schedule, which moves
on-peak-hour usage to a cheaper period on ~6-10 days a year — real dollars, so the
list is not guessable. Each calendar here is a *named, cited* set of rules taken from
the utility's own tariff; a spec references one by name (``tou.holiday_calendar``) and
the loader raises on an unknown name.

Holiday *dates* are computed (a date rule is arithmetic, not a rate), but *which*
holidays a schedule observes is tariff data and must carry a citation. A calendar whose
list has not been confirmed from the tariff is registered as ``UNVERIFIED`` and raises
when used, per the never-fabricate invariant.
"""

from __future__ import annotations

from datetime import date, timedelta
from enum import StrEnum
from functools import lru_cache

from pydantic import BaseModel, ConfigDict


class UnverifiedHolidayCalendarError(ValueError):
    """The named calendar's holiday list is not yet confirmed from a tariff source."""


# --- date rules ------------------------------------------------------------


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th ``weekday`` (Mon=0) of a month; ``n=-1`` means the last one."""
    if n > 0:
        d = date(year, month, 1)
        offset = (weekday - d.weekday()) % 7
        return d + timedelta(days=offset + 7 * (n - 1))
    d = date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


class Observance(StrEnum):
    """How a fixed-date holiday shifts when it lands on a weekend.

    The two CA IOUs modeled here do NOT use the same rule, and the difference is worth
    real money: under ``FEDERAL`` a Saturday holiday moves to the preceding Friday, which
    takes a whole weekday's on-peak hours off peak. Under ``SUNDAY_TO_MONDAY`` it does
    not move at all, and Saturday was already a weekend day, so nothing changes.
    """

    FEDERAL = "federal"  # Sat -> preceding Fri, Sun -> following Mon ("legally observed")
    SUNDAY_TO_MONDAY = "sunday_to_monday"  # Sun -> following Mon; Sat unchanged


def _observed(d: date, rule: Observance) -> date:
    if d.weekday() == 5 and rule is Observance.FEDERAL:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


class HolidayCalendar(BaseModel):
    """A named set of observed holidays, with the tariff citation that fixes the list."""

    model_config = ConfigDict(frozen=True)

    name: str
    citation: str
    fixed: list[tuple[int, int]] = []  # (month, day), shifted per `observance`
    floating: list[tuple[int, int, int]] = []  # (month, weekday Mon=0, n; n=-1 => last)
    observance: Observance = Observance.FEDERAL
    verified: bool = True

    def dates(self, year: int) -> set[date]:
        if not self.verified:
            raise UnverifiedHolidayCalendarError(
                f"holiday calendar {self.name!r}: the observed-holiday list is UNVERIFIED — "
                "confirm it from the schedule's tariff sheet before billing with it"
            )
        out = {_observed(date(year, m, d), self.observance) for m, d in self.fixed}
        out |= {_nth_weekday(year, m, wd, n) for m, wd, n in self.floating}
        return out


# --- registry --------------------------------------------------------------

_CALENDARS: dict[str, HolidayCalendar] = {}


def register(cal: HolidayCalendar) -> HolidayCalendar:
    _CALENDARS[cal.name] = cal
    return cal


def get_calendar(name: str) -> HolidayCalendar:
    try:
        return _CALENDARS[name]
    except KeyError:
        raise ValueError(
            f"unknown holiday calendar {name!r} (known: {sorted(_CALENDARS) or 'none'}); "
            "register it from a tariff source rather than guessing the list"
        ) from None


@lru_cache(maxsize=64)
def holiday_dates(name: str | None, year: int) -> frozenset[date]:
    """Observed holidays in ``year`` for a named calendar; empty when ``name`` is None.

    ``None`` means the schedule's weekend/holiday day type covers Saturday and Sunday
    only — an explicit modeling choice, not a silent default: a spec that needs holidays
    must name a calendar.
    """
    if name is None:
        return frozenset()
    return frozenset(get_calendar(name).dates(year))


# PG&E residential TOU holidays, verbatim from Schedule E-TOU-D Special Condition 1:
# "New Year's Day, President's Day, Memorial Day, Independence Day, Labor Day, Veterans
# Day, Thanksgiving Day, and Christmas Day.  The dates will be those on which the holidays
# are legally observed."  Eight holidays — note there is no MLK Day, Columbus Day or
# Juneteenth on this list. Independently corroborated by 3CE's residential rate sheet,
# which prints the same eight for its PG&E-territory schedules.
register(
    HolidayCalendar(
        name="pge_residential",
        citation=(
            "PG&E Schedule E-TOU-D, Special Condition 1 (TIME PERIODS), Cal. P.U.C. "
            "Sheet 61137-E, Advice 7846-E, effective 2026-03-01; same list printed on "
            "3CE's PG&E-territory residential rate sheet effective 2026-02-15."
        ),
        fixed=[(1, 1), (7, 4), (11, 11), (12, 25)],
        floating=[
            (2, 0, 3),  # President's Day - 3rd Monday in February
            (5, 0, -1),  # Memorial Day - last Monday in May
            (9, 0, 1),  # Labor Day - 1st Monday in September
            (11, 3, 4),  # Thanksgiving Day - 4th Thursday in November
        ],
    )
)

# SDG&E residential TOU holidays, verbatim from Electric Rule 1 (Definitions), HOLIDAYS:
# "New Year's Day (January 1), President's Day (third Monday in February), Memorial Day
# (last Monday in May), Independence Day (July 4), Labor Day (first Monday in September),
# Veterans Day (November 11), Thanksgiving Day (fourth Thursday in November), and
# Christmas Day (December 25). When a Holiday listed above falls on Sunday, the following
# Monday shall be defined as a Holiday. No change will be made for Holidays falling on
# Saturday."
#
# Same eight days as PG&E, but a DIFFERENT observance rule — hence Observance above. This
# was HANDOFF open decision 1; it is now resolved from the tariff, not guessed.
register(
    HolidayCalendar(
        name="sdge_residential",
        citation=(
            "SDG&E Electric Rule 1 (Definitions), HOLIDAYS — elec_elec-rules_erule1.pdf, "
            "retrieved 2026-07-23. Observance: Sunday -> following Monday; Saturday "
            "holidays do not shift."
        ),
        fixed=[(1, 1), (7, 4), (11, 11), (12, 25)],
        floating=[
            (2, 0, 3),  # President's Day - third Monday in February
            (5, 0, -1),  # Memorial Day - last Monday in May
            (9, 0, 1),  # Labor Day - first Monday in September
            (11, 3, 4),  # Thanksgiving Day - fourth Thursday in November
        ],
        observance=Observance.SUNDAY_TO_MONDAY,
    )
)
