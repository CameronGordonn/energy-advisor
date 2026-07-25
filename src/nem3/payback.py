"""Solar / battery payback, with the vintage-timing question and honest failure notes.

Ties the pieces together into the answer M3 exists to give: annual bill savings and a
simple payback period for solar-only, solar+battery (greedy AND LP), and the "install this
year vs next" vintage comparison. Every figure is paired with the conditions that would
overturn it (invariant 2) — a configuration that does not pay back must be able to say so
and say why.

Point estimates only live here; the distribution wrapper (:mod:`uncertainty.montecarlo`)
turns the ``annual_savings`` produced here into a range over rate escalation, panel
degradation and load drift, because a single payback number is how competitors lie by
accident (invariant 3).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from greenbutton.models import IntervalSeries, Utility
from tariffs.bill import compute_bill
from tariffs.schema import Service, TariffSpec

from .acc import ExportRateSchedule, Vintage
from .battery import Battery, DispatchResult, greedy_dispatch, lp_dispatch
from .netting import NbtSettings, NbtYear, settle_year
from .solar import split_meter


@dataclass(frozen=True)
class Scenario:
    """One shoppable configuration and what it costs after solar/battery credits."""

    name: str
    annual_bill: float  # $ due over the modeled year under this configuration
    annual_savings: float  # vs the no-solar baseline; negative means it costs more
    upfront_cost: float
    simple_payback_years: float | None  # None when savings <= 0 (never pays back)
    detail: NbtYear | None = None

    @property
    def pays_back(self) -> bool:
        return self.simple_payback_years is not None


def _simple_payback(upfront: float, annual_savings: float) -> float | None:
    if annual_savings <= 0 or upfront <= 0:
        return None
    return round(upfront / annual_savings, 1)


def baseline_annual_bill(
    load: IntervalSeries,
    delivery: TariffSpec | Sequence[TariffSpec],
    generation: TariffSpec | Sequence[TariffSpec],
    periods: Sequence[tuple[date, date]],
    *,
    care: bool,
    service: Service,
    territory: str | None,
) -> float:
    """The no-solar bill: the customer's real load billed at retail, no exports.

    This is the number every savings figure is measured against, so it uses the same
    :func:`tariffs.bill.compute_bill` that reconciles the golden bills — the solar
    analysis is anchored to a bill the engine is known to reproduce.
    """
    total = 0.0
    for ps, pe in periods:
        bill = compute_bill(
            load,
            [delivery, generation],
            ps,
            pe,
            care=care,
            service=service,
            territory=territory,
            allow_before_effective=True,
        )
        total += bill.total
    return round(total, 2)


@dataclass(frozen=True)
class InstallCosts:
    """Turn-key installed costs before incentives. Caller supplies real quotes."""

    solar_per_kw: float = 3000.0  # $/kW-DC, typical CA residential cash price
    battery_flat: float = 12000.0  # installed cost of the default battery
    itc_fraction: float = 0.30  # federal investment tax credit (30% through 2032)

    def solar(self, kw: float) -> float:
        return self.solar_per_kw * kw * (1 - self.itc_fraction)

    def battery(self) -> float:
        return self.battery_flat * (1 - self.itc_fraction)


DEFAULT_COSTS = InstallCosts()


def evaluate(
    load: IntervalSeries,
    production,  # pd.Series, hourly production aligned to the load year
    delivery: TariffSpec | Sequence[TariffSpec],
    generation: TariffSpec | Sequence[TariffSpec],
    schedule: ExportRateSchedule,
    periods: Sequence[tuple[date, date]],
    *,
    settings: NbtSettings,
    utility: Utility,
    system_kw: float,
    import_price: np.ndarray,
    export_price: np.ndarray,
    battery: Battery | None = None,
    costs: InstallCosts = DEFAULT_COSTS,
) -> list[Scenario]:
    """Rank solar-only, solar+battery(greedy), solar+battery(LP) against no solar.

    ``import_price`` / ``export_price`` are the hourly marginal signals the battery
    dispatch optimizes against; the *dollar* figures always come from the full NBT
    settlement applied to the dispatched series, never from those marginal prices.
    """
    baseline = baseline_annual_bill(
        load,
        delivery,
        generation,
        periods,
        care=settings.care,
        service=settings.service,
        territory=settings.territory,
    )
    battery = battery or Battery()

    def settle(imp, exp) -> NbtYear:
        return settle_year(
            imp,
            exp,
            delivery,
            generation,
            schedule,
            periods,
            settings=settings,
            allow_before_effective=True,
        )

    imp0, exp0 = split_meter(load, production, utility=utility)
    scenarios: list[Scenario] = []

    solar_only = settle(imp0, exp0)
    scenarios.append(_scenario("Solar only", solar_only, baseline, costs.solar(system_kw)))

    for disp in (
        greedy_dispatch(imp0, exp0, import_price, export_price, battery),
        lp_dispatch(imp0, exp0, import_price, export_price, battery, allow_grid_charge=False),
    ):
        year = settle(disp.imports, disp.exports)
        label = (
            "Solar + battery (greedy TOU controller)"
            if disp.label == "greedy"
            else "Solar + battery (LP, perfect-foresight marginal optimum)"
        )
        scenarios.append(
            _scenario(label, year, baseline, costs.solar(system_kw) + costs.battery(), disp)
        )
    return scenarios


def _scenario(
    name: str, year: NbtYear, baseline: float, upfront: float, disp: DispatchResult | None = None
) -> Scenario:
    savings = round(baseline - year.amount_due, 2)
    return Scenario(
        name=name,
        annual_bill=year.amount_due,
        annual_savings=savings,
        upfront_cost=round(upfront, 2),
        simple_payback_years=_simple_payback(upfront, savings),
        detail=year,
    )


@dataclass(frozen=True)
class TimingComparison:
    """Install-this-year vs next-year, driven purely by the locked-in ACC vintage."""

    this_year: int
    next_year: int
    this_year_savings: float
    next_year_savings: float
    lock_in_delta: float  # this_year - next_year, annual $; >0 favors installing now

    @property
    def recommendation(self) -> str:
        if abs(self.lock_in_delta) < 1.0:
            return (
                "timing is immaterial for this utility right now: the published vintages "
                "value this array's exports identically, so 'lock in before rates drop' has "
                "no dollar behind it here"
            )
        better = self.this_year if self.lock_in_delta > 0 else self.next_year
        return (
            f"apply in {better}: its locked-in ACC vintage is worth "
            f"${abs(self.lock_in_delta):.0f}/yr more for this array, for nine years"
        )


def compare_vintage_timing(
    load: IntervalSeries,
    production,
    delivery,
    generation,
    periods,
    *,
    settings: NbtSettings,
    utility: Utility,
    this_year: int,
    pto_offset_days: int = 90,
) -> TimingComparison:
    """Value the same array's exports under this year's vs next year's application vintage.

    The load, production and everything else are held fixed; only the :class:`Vintage`
    changes, which is exactly the lock-in question no consumer tool answers. PTO is
    assumed a fixed offset after application in both cases, so the nine-year clock start
    does not confound the comparison — the difference is the ACC forecast alone.
    """
    from datetime import timedelta

    imp, exp = split_meter(load, production, utility=utility)

    def savings_for(app_year: int) -> float:
        pto = date(app_year, 1, 1) + timedelta(days=pto_offset_days)
        sched = ExportRateSchedule(utility, Vintage(application_year=app_year, pto_date=pto))
        year = settle_year(
            imp,
            exp,
            delivery,
            generation,
            sched,
            periods,
            settings=settings,
            allow_before_effective=True,
        )
        # Savings is monotone in credits; compare credit-driven amount due directly.
        return -year.amount_due

    a = savings_for(this_year)
    b = savings_for(this_year + 1)
    return TimingComparison(
        this_year=this_year,
        next_year=this_year + 1,
        this_year_savings=round(a, 2),
        next_year_savings=round(b, 2),
        lock_in_delta=round(a - b, 2),
    )
