"""Inspect a Green Button interval export: what is in the file, and what it implies.

This is the front door for a person who has just downloaded their usage data and has no
idea whether it is any good. It answers, in order:

1. **Did we read it correctly?** Utility, interval length, date span, coverage, gaps,
   estimated readings, DST transitions, and whether an export (solar) register is present.
   This is also the diagnostic to run first against any *new* utility's export, before
   trusting a single dollar figure computed from it.
2. **What does the usage look like?** Monthly totals, an hour-of-day profile, weekday vs
   weekend, and the share of consumption falling in the windows California TOU rates
   actually price differently.

Deliberately produces **no dollar figures**. Pricing requires a tariff spec and, per
CLAUDE.md's reconciliation gate, may only ship for a utility whose bills the engine has
been shown to reproduce. Usage analysis has no such gate — it is arithmetic on the
customer's own meter — so this module is safe to run on any export, including one from a
utility the billing engine has never been validated against.

The 4-9 p.m. peak window is not a choice made here: it is the on-peak window of *both*
PG&E's E-TOU-C ("Peak Pricing 4-9 p.m. Every Day") and SDG&E's TOU-DR1, the two utilities'
default residential TOU schedules. The other bucket boundaries follow SDG&E's super-off-peak
structure (overnight 00:00-06:00, daytime 10:00-14:00).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from greenbutton._common import GreenButtonParseError
from greenbutton.models import COL_KWH, IntervalSeries, ParseReport, Utility
from greenbutton.pge import parse_pge_interval_csv
from greenbutton.sdge import parse_sdge_interval_csv

# Hour buckets, half-open [start, end). Chosen to match how CA residential TOU schedules
# actually split the day (see module docstring), not invented for presentation.
PEAK_START, PEAK_END = 16, 21
OVERNIGHT_START, OVERNIGHT_END = 0, 6
SOLAR_START, SOLAR_END = 10, 14

# Below this fraction of expected intervals present, a year-total or a bill reconciliation
# built on the file would be quietly understated rather than obviously broken.
COVERAGE_WARN = 0.98
# A CA residential TOU comparison wants a full seasonal cycle; less is extrapolation.
SHORT_SPAN_DAYS = 300

# Peak-share bands. A flat 5/24 = 20.8% of the day sits in the 16:00-21:00 window, so a
# household with no time-of-use behaviour at all lands near 21%. Materially above that
# means load is concentrated in the expensive window; materially below means it is not.
PEAK_SHARE_FLAT = 5 / 24
# Bands are set around the 20.8% flat-load baseline, not at round numbers: a household at
# 27% is using a third more of its power in the expensive window than a featureless load
# would, which is a real signal and should not be reported as "about average".
PEAK_HEAVY = 0.25
PEAK_LIGHT = 0.17


class MonthUsage(BaseModel):
    month: str  # YYYY-MM
    kwh: float
    days: int


class Finding(BaseModel):
    """One plain-English observation, for a reader who does not know what a kWh is.

    ``kind`` is presentation only: ``good`` (works in your favour), ``watch`` (worth
    knowing, may cost you), ``info`` (neutral context). Findings state what the data shows
    and what it implies about rate structures **in general** — never what any specific
    plan would cost, which needs a tariff spec and the reconciliation gate.
    """

    kind: str
    title: str
    detail: str


class Inspection(BaseModel):
    """Everything the inspector concluded, JSON-serializable for any front end."""

    model_config = ConfigDict(frozen=True)

    # -- provenance ----------------------------------------------------------
    source_name: str
    utility: Utility
    interval_minutes: int
    first_start: str
    last_start: str
    span_days: int

    # -- data quality --------------------------------------------------------
    n_intervals: int
    n_estimated: int
    n_gaps: int
    coverage: float
    dst_fall_back_days: list[str] = Field(default_factory=list)
    dst_spring_forward_days: list[str] = Field(default_factory=list)

    # -- usage ---------------------------------------------------------------
    total_kwh: float
    avg_kwh_per_day: float
    by_month: list[MonthUsage] = Field(default_factory=list)
    by_hour_kwh: list[float] = Field(default_factory=list)  # 24 entries, hour 0..23
    weekday_kwh: float = 0.0
    weekend_kwh: float = 0.0

    # -- the shares that decide whether a TOU rate helps ---------------------
    peak_share: float = 0.0  # 16:00-21:00, every day
    overnight_share: float = 0.0  # 00:00-06:00
    solar_window_share: float = 0.0  # 10:00-14:00
    peak_share_weekday: float = 0.0

    # -- extremes ------------------------------------------------------------
    busiest_day: str | None = None
    busiest_day_kwh: float = 0.0
    busiest_hour_of_day: int | None = None

    # -- solar / NEM ---------------------------------------------------------
    has_export_register: bool = False
    export_kwh: float = 0.0

    # -- narrative -----------------------------------------------------------
    findings: list[Finding] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def looks_billable(self) -> bool:
        """Whether this file is good enough to attempt a bill reconciliation against."""
        return self.coverage >= COVERAGE_WARN and self.n_intervals > 0


def _detect_and_parse(path: Path) -> tuple[IntervalSeries, ParseReport]:
    """Parse without being told which utility wrote the file.

    Both IOUs run the same Opower export platform, so the formats differ only in details
    (PG&E writes ISO dates, SDG&E unpadded M/D/YYYY and a separate export register). Rather
    than sniff those details and risk being subtly wrong, try each real parser and keep the
    one that succeeds — the parsers already validate their own format strictly.
    """
    errors: dict[str, str] = {}
    for name, parser in (("PG&E", parse_pge_interval_csv), ("SDG&E", parse_sdge_interval_csv)):
        try:
            return parser(path)
        except GreenButtonParseError as exc:
            errors[name] = str(exc)
        except Exception as exc:  # a malformed file can fail deeper than the format check
            errors[name] = f"{type(exc).__name__}: {exc}"
    detail = "\n".join(f"  as {k}: {v}" for k, v in errors.items())
    raise GreenButtonParseError(
        f"{path.name}: not recognized as a PG&E or SDG&E Green Button interval export.\n"
        f"{detail}\n"
        "  If this is a billing-history or cost summary, re-export the INTERVAL usage "
        "(15-minute or hourly readings), which is a different download."
    )


def _findings(
    *,
    peak_share: float,
    overnight_share: float,
    solar_window_share: float,
    weekend_share: float,
    span_days: int,
    coverage: float,
    has_export: bool,
    export_kwh: float,
    avg_kwh_per_day: float,
) -> list[Finding]:
    """Turn the shares into plain English, for someone who does not know what a kWh is.

    Every statement here is about the SHAPE of the load and what it implies for rate
    STRUCTURES in general. None of it says what a plan would cost, because that needs a
    tariff spec and the reconciliation gate (CLAUDE.md invariant 1).
    """
    out: list[Finding] = []

    pct = f"{peak_share:.0%}"
    if peak_share >= PEAK_HEAVY:
        out.append(
            Finding(
                kind="watch",
                title=f"{pct} of your electricity is used during peak hours",
                detail=(
                    "Between 4 and 9 p.m. — the window both PG&E and SDG&E charge the most "
                    "for on their standard residential plans. That is above the "
                    f"{PEAK_SHARE_FLAT:.0%} you would see from a household with a flat, "
                    "featureless load, so time-of-use pricing works against you here. "
                    "Moving laundry, dishwashing, pool pumps or EV charging outside that "
                    "window is the single largest lever you have."
                ),
            )
        )
    elif peak_share <= PEAK_LIGHT:
        out.append(
            Finding(
                kind="good",
                title=f"Only {pct} of your electricity is used during peak hours",
                detail=(
                    "Between 4 and 9 p.m., when both PG&E and SDG&E charge the most. That "
                    f"is below the {PEAK_SHARE_FLAT:.0%} a perfectly flat load would show, "
                    "so your usage already avoids the expensive window — which generally "
                    "favours a time-of-use plan over a flat-rate one."
                ),
            )
        )
    else:
        out.append(
            Finding(
                kind="info",
                title=f"{pct} of your electricity is used during peak hours",
                detail=(
                    "Between 4 and 9 p.m., the most expensive window on both utilities' "
                    f"standard plans. That is close to the {PEAK_SHARE_FLAT:.0%} a flat "
                    "load would show, so your usage is neither concentrated in nor "
                    "noticeably avoiding the peak window."
                ),
            )
        )

    if overnight_share >= 0.25:
        out.append(
            Finding(
                kind="good",
                title=f"{overnight_share:.0%} of your usage is overnight",
                detail=(
                    "Between midnight and 6 a.m., the cheapest hours on most California "
                    "time-of-use plans. Plans built around EV charging lean even harder "
                    "into these hours."
                ),
            )
        )

    if weekend_share >= 0.35:
        out.append(
            Finding(
                kind="info",
                title="Your weekends are noticeably busier than your weekdays",
                detail=(
                    f"{weekend_share:.0%} of your electricity is used on Saturdays and "
                    "Sundays, which are only 29% of the week. SDG&E prices weekends "
                    "differently from weekdays, so this shape matters there more than it "
                    "does on PG&E."
                ),
            )
        )

    if has_export:
        out.append(
            Finding(
                kind="info",
                title="This looks like a solar account",
                detail=(
                    f"Your file contains a separate export register — {export_kwh:,.0f} kWh "
                    "sent back to the grid over this period. The analysis above covers "
                    "electricity you drew FROM the grid; what your exports are worth "
                    "depends on which net-metering regime you are on, which this tool does "
                    "not yet decide for you."
                ),
            )
        )
    elif solar_window_share >= 0.20:
        out.append(
            Finding(
                kind="info",
                title=f"{solar_window_share:.0%} of your usage happens in the sunniest hours",
                detail=(
                    "Between 10 a.m. and 2 p.m. Electricity used while a rooftop system is "
                    "generating is the most valuable kind for a solar owner, because it "
                    "offsets power you would otherwise buy rather than being exported for "
                    "a lower credit."
                ),
            )
        )

    out.append(
        Finding(
            kind="info",
            title=f"You use about {avg_kwh_per_day:,.0f} kWh a day",
            detail=(
                "For context, the average California single-family household uses roughly "
                "16-20 kWh a day, though this varies enormously with climate zone, house "
                "size, and whether heating and cooking are electric or gas."
            ),
        )
    )

    if span_days < SHORT_SPAN_DAYS:
        out.append(
            Finding(
                kind="watch",
                title=f"This file covers {span_days} days, not a full year",
                detail=(
                    "California rates change between summer and winter, and so does most "
                    "households' usage. Any annual conclusion drawn from a partial year is "
                    "an extrapolation. Both utilities let you export up to 13 months."
                ),
            )
        )
    if coverage < COVERAGE_WARN:
        out.append(
            Finding(
                kind="watch",
                title="Some readings are missing from this file",
                detail=(
                    f"Only {coverage:.1%} of the expected readings are present, so the "
                    "totals above understate your real usage by roughly that much. Try "
                    "re-exporting the data before drawing conclusions from it."
                ),
            )
        )
    return out


def _share(frame: pd.DataFrame, mask: pd.Series, total: float) -> float:
    return float(frame.loc[mask, COL_KWH].sum() / total) if total else 0.0


def inspect_export(path: str | Path) -> Inspection:
    """Parse a Green Button interval CSV and describe it. No pricing, no tariff needed."""
    path = Path(path)
    series, report = _detect_and_parse(path)

    f = series.frame
    idx = f.index
    total = float(f[COL_KWH].sum())
    hours = idx.hour
    is_weekend = idx.dayofweek >= 5

    daily = f[COL_KWH].groupby(idx.date).sum()
    span_days = max(1, (series.end - series.start).days)

    # Group on local YYYY-MM strings rather than pandas Periods: converting a tz-aware
    # index to a PeriodIndex silently drops the timezone, which would bucket the late
    # hours of a month-end evening into the following month.
    months = pd.Index(idx.strftime("%Y-%m"), name="month")
    monthly = f[COL_KWH].groupby(months).sum()
    month_days = pd.Series(idx.date, index=months).groupby(level=0).nunique()
    by_month = [
        MonthUsage(month=str(m), kwh=round(float(v), 2), days=int(month_days.loc[m]))
        for m, v in monthly.items()
    ]

    by_hour = f[COL_KWH].groupby(hours).sum().reindex(range(24), fill_value=0.0)

    peak = (hours >= PEAK_START) & (hours < PEAK_END)
    overnight = (hours >= OVERNIGHT_START) & (hours < OVERNIGHT_END)
    solar_win = (hours >= SOLAR_START) & (hours < SOLAR_END)

    weekday_total = float(f.loc[~is_weekend, COL_KWH].sum())
    peak_weekday_kwh = float(f.loc[peak & ~is_weekend, COL_KWH].sum())

    warnings: list[str] = []
    if report.coverage < COVERAGE_WARN:
        warnings.append(
            f"Only {report.coverage:.1%} of expected readings are present "
            f"({report.n_gaps} missing). Totals below understate real usage by roughly "
            f"the same fraction, and this file is not suitable for a bill comparison."
        )
    if span_days < SHORT_SPAN_DAYS:
        warnings.append(
            f"This covers {span_days} days. A rate comparison needs a full seasonal cycle "
            f"(summer and winter) — with less, any annual figure is an extrapolation."
        )
    if report.n_estimated:
        warnings.append(
            f"{report.n_estimated} reading(s) are flagged estimated by the utility rather "
            f"than metered."
        )

    notes = list(report.notes)
    # The SDG&E parser surfaces a live export register in its notes rather than dropping
    # it (NEM netting is M3, but its PRESENCE changes what questions are worth asking).
    export_kwh = 0.0
    has_export = False
    for note in report.notes:
        if "export register present" in note.lower():
            has_export = True
            m = re.search(r"([\d.]+)\s*kWh total", note)
            if m:
                export_kwh = float(m.group(1))

    if series.interval.total_seconds() / 60 >= 60:
        notes.append(
            "This meter reports hourly, not 15-minute, readings. That is fine for "
            "California time-of-use periods, which are all hour-aligned."
        )

    weekend_share = (total - weekday_total) / total if total else 0.0
    findings = _findings(
        peak_share=_share(f, peak, total),
        overnight_share=_share(f, overnight, total),
        solar_window_share=_share(f, solar_win, total),
        weekend_share=weekend_share,
        span_days=span_days,
        coverage=report.coverage,
        has_export=has_export,
        export_kwh=export_kwh,
        avg_kwh_per_day=total / span_days,
    )

    return Inspection(
        source_name=path.name,
        utility=report.utility,
        interval_minutes=report.interval_minutes,
        first_start=report.first_start,
        last_start=report.last_start,
        span_days=span_days,
        n_intervals=report.n_intervals,
        n_estimated=report.n_estimated,
        n_gaps=report.n_gaps,
        coverage=round(report.coverage, 6),
        dst_fall_back_days=report.dst_fall_back_days,
        dst_spring_forward_days=report.dst_spring_forward_days,
        total_kwh=round(total, 2),
        avg_kwh_per_day=round(total / span_days, 2),
        by_month=by_month,
        by_hour_kwh=[round(float(v), 3) for v in by_hour],
        weekday_kwh=round(weekday_total, 2),
        weekend_kwh=round(total - weekday_total, 2),
        peak_share=round(_share(f, peak, total), 4),
        overnight_share=round(_share(f, overnight, total), 4),
        solar_window_share=round(_share(f, solar_win, total), 4),
        peak_share_weekday=round(peak_weekday_kwh / weekday_total, 4) if weekday_total else 0.0,
        busiest_day=str(daily.idxmax()) if len(daily) else None,
        busiest_day_kwh=round(float(daily.max()), 2) if len(daily) else 0.0,
        busiest_hour_of_day=int(by_hour.idxmax()) if total else None,
        has_export_register=has_export,
        export_kwh=round(export_kwh, 2),
        findings=findings,
        notes=notes,
        warnings=warnings,
    )
