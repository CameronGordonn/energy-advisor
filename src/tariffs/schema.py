"""Tariff spec schema — versioned, effective-dated, citation-mandatory *data*.

A spec is a pure data description of one billing layer (``delivery`` or
``generation``) for one schedule, effective from a date. The billing function in
:mod:`tariffs.bill` turns (interval series + spec + period) into an itemized bill;
no rate value lives in code.

Invariants (CLAUDE.md):
- Every spec carries a non-empty ``citation`` pointing at the source of its numbers.
- Any field left as the literal ``UNVERIFIED`` makes the loader raise, rather than
  letting a guessed number reach a dollar figure. See :func:`tariffs.loader.load_spec`.
- Delivery and generation are modeled as separate layers now (even for PG&E) so the
  SDG&E + CCA milestone doesn't force a refactor.

TOU model: a schedule declares an ordered, **first-match-wins** list of
:class:`TouRule` plus a ``default_period`` for hours no rule claims. Rules may be
restricted by day type (weekday vs weekend/holiday) and by month, which is what SDG&E
residential needs (three periods; different weekend tables; a Mar/Apr-only carve-out).
Two-period PG&E schedules keep writing ``peak_hours`` — it is sugar that normalizes to
periods ``peak``/``offpeak``, so those specs and their ``summer_peak``/``winter_offpeak``
energy keys are unchanged.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .holidays import get_calendar

UNVERIFIED = "UNVERIFIED"

LEGACY_PEAK = "peak"
LEGACY_OFFPEAK = "offpeak"


class Layer(StrEnum):
    DELIVERY = "delivery"
    GENERATION = "generation"


class Season(StrEnum):
    SUMMER = "summer"
    WINTER = "winter"


class Service(StrEnum):
    """How the customer buys generation — which changes which lines they pay.

    Straight from the schedules' own BILLING special conditions: "CCA/DA customers shall
    pay all charges shown in the Unbundling of Total Rates except for the Bundled Power
    Charge Indifference Adjustment and the generation charge. These customers shall also
    pay for their applicable Vintaged Power Charge Indifference Adjustment ... [and] the
    franchise fee surcharge provided in Schedule E-FFS."

    So the delivery layer is shared between bundled and CCA customers; only a couple of
    lines differ. Modeling that with an ``applies_to`` tag keeps one delivery spec per
    schedule instead of two near-identical copies that would drift apart at the next rate
    change.
    """

    BUNDLED = "bundled"  # generation supplied by the utility
    CCA = "cca"  # generation supplied by a CCA / Direct Access provider


class AppliesTo(StrEnum):
    ALL = "all"
    BUNDLED = "bundled"
    CCA = "cca"

    def covers(self, service: Service) -> bool:
        return self is AppliesTo.ALL or self.value == service.value


class DayType(StrEnum):
    """Which days a TOU rule applies to.

    ``WEEKEND`` means the schedule's weekend/holiday table: Saturday and Sunday, plus
    the observed holidays of ``TouDef.holiday_calendar`` when one is named.
    """

    ALL = "all"
    WEEKDAY = "weekday"
    WEEKEND = "weekend"


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SeasonDef(_Base):
    """Which calendar months fall in each season (CA IOU seasons are month-bounded)."""

    summer_months: list[int] = Field(min_length=1, max_length=12)
    winter_months: list[int] = Field(min_length=1, max_length=12)

    @field_validator("summer_months", "winter_months")
    @classmethod
    def _valid_months(cls, v: list[int]) -> list[int]:
        if any(m < 1 or m > 12 for m in v):
            raise ValueError("months must be 1..12")
        return v

    def season_for(self, month: int) -> Season:
        if month in self.summer_months:
            return Season.SUMMER
        if month in self.winter_months:
            return Season.WINTER
        raise ValueError(f"month {month} not assigned to a season")


class TouRule(_Base):
    """One first-match-wins TOU rule: this period, these hours, these days/months."""

    period: str = Field(min_length=1)
    hours: list[tuple[int, int]] = Field(
        min_length=1, description="Half-open local-clock windows [start, end); end may be 24"
    )
    days: DayType = DayType.ALL
    months: list[int] | None = Field(
        default=None, description="Calendar months the rule applies to; None = every month"
    )

    @field_validator("hours")
    @classmethod
    def _valid_hours(cls, v: list[tuple[int, int]]) -> list[tuple[int, int]]:
        for start, end in v:
            if not (0 <= start < end <= 24):
                raise ValueError(
                    f"hour window must satisfy 0 <= start < end <= 24, got [{start},{end})"
                )
        return v

    @field_validator("months")
    @classmethod
    def _valid_months(cls, v: list[int] | None) -> list[int] | None:
        if v is not None and (not v or any(m < 1 or m > 12 for m in v)):
            raise ValueError("months must be non-empty and in 1..12")
        return v

    def matches(self, hour: int, month: int, weekday: bool) -> bool:
        if self.days is DayType.WEEKDAY and not weekday:
            return False
        if self.days is DayType.WEEKEND and weekday:
            return False
        if self.months is not None and month not in self.months:
            return False
        return any(start <= hour < end for start, end in self.hours)


def _prettify(period: str) -> str:
    if period == LEGACY_OFFPEAK:
        return "Off Peak"
    return period.replace("_", " ").title()


class TouDef(_Base):
    """The schedule's TOU periods: ordered rules + a default for unclaimed hours.

    Legacy two-period form (every PG&E spec here): give ``peak_hours`` and nothing else;
    it normalizes to a single ``peak`` rule with ``offpeak`` as the default, which is
    exactly the old "off-peak is the complement" behaviour.
    """

    # Legacy sugar (kept in the model so the spec files stay readable as written).
    peak_hours: list[int] | None = Field(
        default=None, description="Local clock hours [h, h+1) that are peak (two-period sugar)"
    )
    label_peak: str = "Peak"
    label_offpeak: str = "Off Peak"

    # General form.
    rules: list[TouRule] = Field(default_factory=list)
    default_period: str = ""
    labels: dict[str, str] = Field(
        default_factory=dict, description="period -> bill line label; defaults to Title Case"
    )
    holiday_calendar: str | None = Field(
        default=None,
        description="Named calendar in tariffs.holidays whose dates use the weekend table; "
        "None means weekend = Saturday/Sunday only",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy(cls, data: Any) -> Any:
        """Expand ``peak_hours`` into the general rule form (peak / offpeak)."""
        if not isinstance(data, dict):
            return data
        hours = data.get("peak_hours")
        if hours is None:
            return data
        if data.get("rules") or data.get("default_period"):
            raise ValueError("give either peak_hours (two-period sugar) or rules/default_period")
        if not hours or any(h < 0 or h > 23 for h in hours):
            raise ValueError("peak_hours must be non-empty and in 0..23")
        windows = _contiguous(sorted(set(hours)))
        data = dict(data)
        data["rules"] = [{"period": LEGACY_PEAK, "hours": windows, "days": DayType.ALL.value}]
        data["default_period"] = LEGACY_OFFPEAK
        data["labels"] = {
            LEGACY_PEAK: data.get("label_peak", "Peak"),
            LEGACY_OFFPEAK: data.get("label_offpeak", "Off Peak"),
            **data.get("labels", {}),
        }
        return data

    @model_validator(mode="after")
    def _check(self) -> TouDef:
        if not self.rules or not self.default_period:
            raise ValueError("tou needs either peak_hours, or rules + default_period")
        if self.holiday_calendar is not None:
            get_calendar(self.holiday_calendar).dates(2026)  # raises if unknown/UNVERIFIED
        return self

    @property
    def periods(self) -> list[str]:
        """Periods in bill-line order: rule order, then the default period."""
        out: list[str] = []
        for r in self.rules:
            if r.period not in out:
                out.append(r.period)
        if self.default_period not in out:
            out.append(self.default_period)
        return out

    def label(self, period: str) -> str:
        return self.labels.get(period) or _prettify(period)

    def period_for(self, hour: int, month: int, weekday: bool) -> str:
        for r in self.rules:
            if r.matches(hour, month, weekday):
                return r.period
        return self.default_period

    @property
    def day_type_sensitive(self) -> bool:
        return any(r.days is not DayType.ALL for r in self.rules)


def _contiguous(hours: list[int]) -> list[tuple[int, int]]:
    """[16,17,18,19,20] -> [(16, 21)]."""
    windows: list[tuple[int, int]] = []
    for h in hours:
        if windows and windows[-1][1] == h:
            windows[-1] = (windows[-1][0], h + 1)
        else:
            windows.append((h, h + 1))
    return windows


class Rate(_Base):
    """A $/unit value with standard and/or CARE (low-income) variants.

    Either variant may be absent (``None``) when a spec is only partially known —
    e.g. Cameron's bill gives the CARE base-services rate but not the standard one.
    Requesting a variant that is ``None`` raises at *bill* time (never fabricated),
    which keeps CARE reconciliation working while refusing to bill a standard
    customer on an incomplete spec.
    """

    standard: float | None = None
    care: float | None = None

    def for_customer(self, *, care: bool, what: str = "rate") -> float:
        val = self.care if care else self.standard
        if val is None:
            variant = "CARE" if care else "standard"
            raise ValueError(
                f"{what}: no {variant} value in spec (fill from the tariff sheet before "
                "billing this customer class)"
            )
        return val


class Allowance(_Base):
    """Summer/winter kWh-per-day baseline allowance for one territory or climate zone."""

    summer: float = Field(gt=0)
    winter: float = Field(gt=0)


class Baseline(_Base):
    """Baseline-allowance credit: min(usage, multiplier x allowance) x credit (negative).

    ``allowance_multiplier`` is 1.0 for PG&E (credit up to 100% of baseline) and 1.30 for
    SDG&E residential, whose schedules credit up to 130% of the baseline allowance.

    Allowances are per *territory* (PG&E) or *climate zone* (SDG&E), and further split by
    Basic vs All-Electric service. That is a **customer** fact, not a schedule fact, so a
    spec may either pin one territory (``territory`` + the two flat allowances, which is
    how the PG&E specs read, since the customer's territory is known from their bill) or
    publish the whole table via ``allowances`` and let the caller pass a ``territory`` at
    bill time. Publishing the table is what lets one SDG&E spec serve every climate zone
    instead of four near-identical files.
    """

    territory: str | None = None
    allowance_kwh_per_day_summer: float | None = None
    allowance_kwh_per_day_winter: float | None = None
    allowances: dict[str, Allowance] = Field(
        default_factory=dict, description="territory/zone key -> allowance; overrides the flat pair"
    )
    credit_per_kwh: Rate
    allowance_multiplier: float = Field(
        default=1.0, gt=0, description="Fraction of baseline the credit applies to (SDG&E: 1.30)"
    )

    @model_validator(mode="after")
    def _has_an_allowance(self) -> Baseline:
        flat = (
            self.allowance_kwh_per_day_summer is not None
            and self.allowance_kwh_per_day_winter is not None
        )
        if not flat and not self.allowances:
            raise ValueError(
                "baseline needs either allowance_kwh_per_day_summer/_winter or an "
                "`allowances` table keyed by territory/climate zone"
            )
        if self.allowances and self.territory is not None and self.territory not in self.allowances:
            raise ValueError(
                f"baseline.territory {self.territory!r} is not a key of `allowances` "
                f"({sorted(self.allowances)}) — pick the customer's actual zone"
            )
        if not self.allowances and self.territory is None:
            raise ValueError("baseline pinned to flat allowances must name its territory")
        return self

    def allowance_per_day(self, season: Season, territory: str | None = None) -> float:
        """kWh/day for ``season``; ``territory`` selects a row of ``allowances``.

        Raises on an unknown territory rather than falling back to a default — a wrong
        baseline zone silently mis-sizes the largest credit on a CA residential bill.
        """
        key = territory or self.territory
        if self.allowances:
            if key is None:
                raise ValueError(
                    "this spec publishes a baseline allowance table "
                    f"({sorted(self.allowances)}) but no territory was supplied; the "
                    "customer's climate zone is a customer fact and must be passed in "
                    "(compute_bill(..., territory=...)), never defaulted"
                )
            try:
                a = self.allowances[key]
            except KeyError:
                raise ValueError(
                    f"unknown baseline territory {key!r}; this spec publishes "
                    f"{sorted(self.allowances)}"
                ) from None
            return a.summer if season is Season.SUMMER else a.winter
        if territory is not None and territory != self.territory:
            raise ValueError(
                f"spec is pinned to territory {self.territory!r} but {territory!r} was "
                "requested; use a spec with an `allowances` table"
            )
        return (
            self.allowance_kwh_per_day_summer
            if season is Season.SUMMER
            else self.allowance_kwh_per_day_winter
        )

    def credited_kwh(
        self, season: Season, days: int, total_kwh: float, territory: str | None = None
    ) -> float:
        allowance = days * self.allowance_per_day(season, territory) * self.allowance_multiplier
        return min(total_kwh, allowance)


class PerKwhAdder(_Base):
    """A $/kWh line (PCIA, generation credit, ...): flat, per-season, or per-season TOU.

    Resolution order for a given season, most specific first:
    1. TOU: a rate for every one of the schedule's periods, either from ``per_kwh_tou``
       (keys ``"<season>_<period>"``) or from the two-period legacy fields
       ``per_kwh_<season>_peak`` / ``_offpeak``. Billed against each period's kWh.
    2. Seasonal flat: ``per_kwh_<season>``.
    3. Flat: ``per_kwh``.

    A *partial* TOU set (some periods priced, others not) raises rather than falling back
    to a flat rate — that would silently invent a price for the unpriced periods.

    The PG&E "Generation Credit" for CCA customers is a TOU-weighted PG&E generation
    rate, so where two bills pin down the peak/off split it is modeled as TOU (exact);
    where only one bill exists (summer, here) it falls back to a seasonal blend.

    **Vintaged adders.** The PCIA is priced per *vintage* — the year the customer's load
    departed bundled service — and on SDG&E's 2026 tables the CCA column spans 0.01538 to
    0.05055 $/kWh. That 0.035 $/kWh spread is about $210/year on a 6,000 kWh household,
    more than the entire annual saving the PG&E case study found from switching supplier,
    so pinning one vintage into a spec would be the single largest error a CCA bill could
    carry. A spec may therefore publish the whole table via
    ``per_kwh_by_vintage`` and let the caller pass ``vintage`` at bill time, exactly as
    ``Baseline.allowances`` does for climate zone. Like that one, an unknown or missing
    vintage RAISES rather than defaulting: the customer's vintage is a customer fact and
    guessing it silently mis-prices every imported kWh. A spec that legitimately knows its
    customer (the PG&E specs, read off a bill) may still pin a flat ``per_kwh``.
    """

    name: str
    per_kwh: float | None = None
    per_kwh_summer: float | None = None
    per_kwh_winter: float | None = None
    per_kwh_summer_peak: float | None = None
    per_kwh_summer_offpeak: float | None = None
    per_kwh_winter_peak: float | None = None
    per_kwh_winter_offpeak: float | None = None
    per_kwh_tou: dict[str, float] = Field(
        default_factory=dict, description='N-period TOU rates keyed "<season>_<period>"'
    )
    per_kwh_by_vintage: dict[str, float] = Field(
        default_factory=dict,
        description="vintage key -> flat $/kWh; selected by `vintage` at bill time",
    )
    vintage_pin: str | None = Field(
        default=None, description="pin one row of per_kwh_by_vintage (customer known)"
    )
    applies_to: AppliesTo = AppliesTo.ALL
    citation: str

    @model_validator(mode="after")
    def _fold_legacy_tou(self) -> PerKwhAdder:
        legacy = {
            f"{s}_{p}": getattr(self, f"per_kwh_{s}_{p}")
            for s in ("summer", "winter")
            for p in (LEGACY_PEAK, LEGACY_OFFPEAK)
        }
        merged = {k: v for k, v in legacy.items() if v is not None} | self.per_kwh_tou
        object.__setattr__(self, "per_kwh_tou", merged)
        return self

    @model_validator(mode="after")
    def _vintage_table_is_exclusive(self) -> PerKwhAdder:
        """A vintaged adder may not also carry a flat or TOU rate.

        Both forms present would mean two defensible answers for the same line, and which
        one won would depend on resolution order rather than on the tariff.
        """
        if not self.per_kwh_by_vintage:
            if self.vintage_pin is not None:
                raise ValueError(
                    f"adder {self.name!r}: vintage_pin set without a per_kwh_by_vintage table"
                )
            return self
        others = [self.per_kwh, self.per_kwh_summer, self.per_kwh_winter]
        if any(v is not None for v in others) or self.per_kwh_tou:
            raise ValueError(
                f"adder {self.name!r}: per_kwh_by_vintage cannot be combined with flat or "
                "TOU rates — pick the form the tariff actually uses"
            )
        if self.vintage_pin is not None and self.vintage_pin not in self.per_kwh_by_vintage:
            raise ValueError(
                f"adder {self.name!r}: vintage_pin {self.vintage_pin!r} is not a key of "
                f"per_kwh_by_vintage ({sorted(self.per_kwh_by_vintage)})"
            )
        return self

    def _tou(self, season: Season, periods: list[str]) -> dict[str, float] | None:
        found = {p: self.per_kwh_tou.get(f"{season.value}_{p}") for p in periods}
        present = {p: v for p, v in found.items() if v is not None}
        if not present:
            return None
        if len(present) != len(periods):
            missing = sorted(set(periods) - set(present))
            raise ValueError(
                f"adder {self.name!r}: TOU rates for {season} cover "
                f"{sorted(present)} but not {missing} — fill them or drop the TOU form "
                "(a flat fallback would invent a rate for the missing periods)"
            )
        return present

    def vintage_rate(self, vintage: str | None) -> float:
        """$/kWh for ``vintage`` from ``per_kwh_by_vintage``.

        Raises on a missing or unknown vintage rather than defaulting, for the same reason
        ``Baseline.allowance_per_day`` raises on an unknown climate zone: the value is a
        customer fact, and a wrong one mis-prices every kWh without looking wrong.
        """
        key = vintage or self.vintage_pin
        if key is None:
            raise ValueError(
                f"adder {self.name!r} publishes a per-vintage table "
                f"({sorted(self.per_kwh_by_vintage)}) but no vintage was supplied; the "
                "customer's PCIA vintage is a customer fact and must be passed in "
                "(compute_bill(..., vintage=...)), never defaulted"
            )
        if key not in self.per_kwh_by_vintage:
            raise ValueError(
                f"adder {self.name!r}: unknown vintage {key!r}; the tariff prices "
                f"{sorted(self.per_kwh_by_vintage)}"
            )
        return self.per_kwh_by_vintage[key]

    def rate(self, season: Season) -> float:
        """Flat/seasonal $/kWh. Raises when only TOU rates exist (use :meth:`amount`)."""
        if self.per_kwh is not None:
            return self.per_kwh
        val = self.per_kwh_summer if season is Season.SUMMER else self.per_kwh_winter
        if val is None:
            raise ValueError(f"adder {self.name!r} has no rate for {season}")
        return val

    def amount(
        self,
        season: Season,
        usage: dict[str, float],
        *,
        vintage: str | None = None,
    ) -> tuple[float, float | None]:
        """(amount, per-kwh rate or None). Rate is None for TOU adders (blended line)."""
        if self.per_kwh_by_vintage:
            r = self.vintage_rate(vintage)
            return sum(usage.values()) * r, r
        periods = list(usage)
        tou = self._tou(season, periods)
        if tou is not None:
            return sum(usage[p] * tou[p] for p in periods), None
        r = self.rate(season)
        return sum(usage.values()) * r, r


class Surcharge(_Base):
    """A trailing line billed *outside* the other surcharges' base (franchise fee, UUT).

    Either a percentage of a named prior subtotal (``rate`` + ``of``) or a flat $/kWh
    (``per_kwh``). Surcharges are computed against the sub-period subtotal snapshotted
    *before* any surcharge is added, so they never compound each other — which is how the
    bills read: the Santa Cruz UUT base excludes the franchise fee surcharge.

    The $/kWh form exists because PG&E's CCA franchise fee surcharge (Schedule E-FFS) is
    a flat per-kWh rate by PCIA vintage, not a percentage — see the E-FFS citation on the
    delivery specs.
    """

    name: str
    rate: float | None = None
    of: str | None = Field(
        default=None, description="Which running subtotal to apply to: 'pretax' | 'energy'"
    )
    per_kwh: float | None = None
    applies_to: AppliesTo = AppliesTo.ALL
    citation: str

    @model_validator(mode="after")
    def _exactly_one_form(self) -> Surcharge:
        percent = self.rate is not None and self.of is not None
        flat = self.per_kwh is not None
        if percent == flat:
            raise ValueError(
                f"surcharge {self.name!r}: give either rate+of (percent) or per_kwh (flat), "
                "not both and not neither"
            )
        return self

    def amount(self, *, pretax: float, energy: float, kwh: float) -> tuple[float, float | None]:
        """(amount, reported rate)."""
        if self.per_kwh is not None:
            return kwh * self.per_kwh, self.per_kwh
        base = energy if self.of == "energy" else pretax
        return base * self.rate, self.rate


class NonBypassable(_Base):
    """The per-kWh charges billed on GROSS metered imports under the Net Billing Tariff.

    Schedule NBT, Special Condition 2.f: "Customers on this tariff must pay non-bypassable
    charges (NBCs) for each kilowatt-hour of electricity they consume from the grid (based
    on the metered import channel). The following NBCs may not be reduced by any credits
    for exports to the grid, except for the ACC Plus credit: Public Purpose Program,
    Nuclear Decommissioning Charge, Competition Transition Charge, and Wildfire Fund
    Charge."

    This block is **declarative only** — it changes no bill. The NBC components are
    already inside the schedule's energy rates (that is how the utilities' rate tables
    publish them), so billing them again would double-count. What the NBT netting model
    needs is to know how much of an energy charge is non-bypassable, in order to carve it
    out of the amount export credits are allowed to offset. Hence
    ``included_in_energy_rate``: when true (the normal case) the netting code *subtracts*
    this from the offsettable subtotal rather than adding it to the bill.

    The resulting floor — no matter how much a customer exports, imports still cost at
    least this much per kWh — is differentiation invariant 4, and it is the line generic
    NEM calculators skip entirely.
    """

    components: dict[str, Rate] = Field(
        min_length=1, description="Charge name -> $/kWh, one entry per named NBC"
    )
    included_in_energy_rate: bool = True
    citation: str = Field(min_length=1)

    def per_kwh(self, *, care: bool) -> float:
        """Total non-bypassable $/kWh for this customer class.

        Raises (via :meth:`Rate.for_customer`) if a component has no value for the class,
        rather than treating a missing NBC as zero — a silently-zero NBC would understate
        the import floor, which is precisely the error this model exists to avoid.
        """
        return sum(
            r.for_customer(care=care, what=f"non-bypassable charge {name!r}")
            for name, r in self.components.items()
        )


class MinimumBill(_Base):
    """A per-day floor on the layer total (SDG&E Minimum Bill; PG&E has none)."""

    per_day: Rate
    name: str = "Minimum Bill Adjustment"
    citation: str = Field(min_length=1)


class EventAdder(_Base):
    """A per-kWh charge that applies only on days the utility calls, with a day's notice.

    SDG&E's RYU Event Period Adder (Schedule EECC-TOU-DR-P SC 14/15) is the only instance
    today: $1.16/kWh **on top of** the ordinary energy charge, 4 p.m.-9 p.m., on up to
    eighteen days a calendar year that SDG&E picks and announces the day before.

    **Why this is a schema field and not a rate.** The tariff fixes three of the four
    things needed to bill it — the rate, the hours, the annual cap — and cannot fix the
    fourth. *Which* days is a fact about a billing period, so the day list is a bill-time
    input exactly like ``territory`` (climate zone) and the PCIA ``vintage``, and like both
    of those, omitting it RAISES rather than defaulting. See ``bill.compute_layer``.

    **Why it must not default to zero.** Zero events is the single most likely outcome in
    any given year (SDG&E called none in 2021, 2022, 2023, 2025 or 2026-to-date) *and* the
    assumption under which the schedule looks unambiguously cheap. A default that is both
    usually right and systematically flattering is the installer-tool failure mode
    CLAUDE.md's honest-broker invariant exists to prevent: at 6/1/2026 rates one summer
    event day cancels ~6.7 ordinary summer days of TOU-DR-P's on-peak saving, so the
    difference between 0 and the 18-event cap is the difference between a recommendation
    and its opposite. Callers that want the optimistic case must ask for it by passing an
    empty list, which is a decision on the record rather than a silent default.
    """

    name: str = Field(min_length=1)
    per_kwh: Rate
    hours: list[tuple[int, int]] = Field(
        min_length=1, description="Half-open local-clock windows [start, end) on an event day"
    )
    max_events_per_year: int = Field(gt=0)
    citation: str = Field(min_length=1)

    @field_validator("hours")
    @classmethod
    def _valid_hours(cls, v: list[tuple[int, int]]) -> list[tuple[int, int]]:
        for start, end in v:
            if not (0 <= start < end <= 24):
                raise ValueError(
                    f"hour window must satisfy 0 <= start < end <= 24, got [{start},{end})"
                )
        return v

    def covers(self, hour: int) -> bool:
        return any(start <= hour < end for start, end in self.hours)


class TariffSpec(_Base):
    """One layer (delivery or generation) of one schedule, effective from a date."""

    schedule_id: str
    name: str
    provider: str
    layer: Layer
    effective_date: date
    citation: str = Field(min_length=1)

    seasons: SeasonDef
    tou: TouDef

    # Delivery-style components (all optional so a generation spec can omit them).
    fixed_per_day: Rate | None = None
    fixed_name: str = "Base Services Charge"
    energy: dict[str, Rate] | None = Field(
        default=None, description='Energy $/kWh keyed "<season>_<period>"'
    )
    baseline: Baseline | None = None
    adders: list[PerKwhAdder] = Field(default_factory=list)
    energy_commission_tax_per_kwh: float | None = None
    surcharges: list[Surcharge] = Field(default_factory=list)
    minimum_bill: MinimumBill | None = None
    non_bypassable: NonBypassable | None = None
    event_adder: EventAdder | None = None
    """Set only by event-contingent schedules (SDG&E TOU-DR-P). Its presence makes
    ``event_days`` a REQUIRED argument to the billing functions — see :class:`EventAdder`."""

    @field_validator("citation")
    @classmethod
    def _citation_verified(cls, v: str) -> str:
        if v.strip().upper() == UNVERIFIED or not v.strip():
            raise ValueError("citation is mandatory and must not be UNVERIFIED")
        return v

    @model_validator(mode="after")
    def _energy_keys_cover_seasons_and_periods(self) -> TariffSpec:
        if self.energy is None:
            return self
        want = {f"{s.value}_{p}" for s in Season for p in self.tou.periods}
        have = set(self.energy)
        if extra := sorted(have - want):
            raise ValueError(
                f"energy has unknown key(s) {extra}; expected '<season>_<period>' over "
                f"seasons {[s.value for s in Season]} and periods {self.tou.periods}"
            )
        if missing := sorted(want - have):
            raise ValueError(f"energy is missing rate(s) for {missing} (never inferred)")
        return self

    def energy_rate(self, season: Season, period: str) -> Rate:
        if self.energy is None:
            raise ValueError(f"{self.schedule_id}: spec has no energy rates")
        return self.energy[f"{season.value}_{period}"]
