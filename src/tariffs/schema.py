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
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

UNVERIFIED = "UNVERIFIED"


class Layer(StrEnum):
    DELIVERY = "delivery"
    GENERATION = "generation"


class Season(StrEnum):
    SUMMER = "summer"
    WINTER = "winter"


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


class TouDef(_Base):
    """Peak window(s). Off-peak is the complement (M0 schedules are two-period)."""

    peak_hours: list[int] = Field(description="Local clock hours [h, h+1) that are peak")
    label_peak: str = "Peak"
    label_offpeak: str = "Off Peak"

    @field_validator("peak_hours")
    @classmethod
    def _valid_hours(cls, v: list[int]) -> list[int]:
        if not v or any(h < 0 or h > 23 for h in v):
            raise ValueError("peak_hours must be non-empty and in 0..23")
        return v

    def is_peak(self, hour: int) -> bool:
        return hour in self.peak_hours


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


class SeasonalTouRates(_Base):
    """Energy $/kWh indexed by season then period (peak/offpeak)."""

    summer_peak: Rate
    summer_offpeak: Rate
    winter_peak: Rate
    winter_offpeak: Rate

    def rate(self, season: Season, *, peak: bool) -> Rate:
        key = f"{season.value}_{'peak' if peak else 'offpeak'}"
        return getattr(self, key)


class Baseline(_Base):
    """Baseline-allowance credit: min(usage, allowance) x credit rate (negative)."""

    territory: str
    allowance_kwh_per_day_summer: float
    allowance_kwh_per_day_winter: float
    credit_per_kwh: Rate

    def allowance_per_day(self, season: Season) -> float:
        return (
            self.allowance_kwh_per_day_summer
            if season is Season.SUMMER
            else self.allowance_kwh_per_day_winter
        )


class PerKwhAdder(_Base):
    """A flat or per-season $/kWh line (PCIA, generation credit, etc.)."""

    name: str
    per_kwh: float | None = None
    per_kwh_summer: float | None = None
    per_kwh_winter: float | None = None
    citation: str

    def rate(self, season: Season) -> float:
        if self.per_kwh is not None:
            return self.per_kwh
        val = self.per_kwh_summer if season is Season.SUMMER else self.per_kwh_winter
        if val is None:
            raise ValueError(f"adder {self.name!r} has no rate for {season}")
        return val


class PercentSurcharge(_Base):
    """A percentage line applied to a named prior subtotal (franchise fee, UUT)."""

    name: str
    rate: float
    of: str = Field(description="Which running subtotal to apply to: 'pretax' | 'energy'")
    citation: str


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
    energy: SeasonalTouRates | None = None
    baseline: Baseline | None = None
    adders: list[PerKwhAdder] = Field(default_factory=list)
    energy_commission_tax_per_kwh: float | None = None
    surcharges: list[PercentSurcharge] = Field(default_factory=list)

    @field_validator("citation")
    @classmethod
    def _citation_verified(cls, v: str) -> str:
        if v.strip().upper() == UNVERIFIED or not v.strip():
            raise ValueError("citation is mandatory and must not be UNVERIFIED")
        return v
