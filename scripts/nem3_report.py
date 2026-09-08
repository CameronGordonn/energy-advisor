"""M3 demonstration: NEM 3.0 solar + battery payback with uncertainty and vintage timing.

Runs the full NBT pipeline end to end on the real SDG&E ACC export tables and the real
SDG&E TOU-DR1 tariff, and prints the honest-broker report: solar-only vs solar+battery
(greedy realistic AND LP optimum), the non-bypassable import floor, the nine-year lock-in
vintage-timing answer, and a Monte Carlo payback range.

IMPORTANT — what is real and what is illustrative here:
  * Tariff rates, the NBC set, and the 576-per-year ACC export tables are REAL, cited data.
  * The LOAD PROFILE below is SYNTHETIC and clearly labeled. No real SDG&E household's
    interval data is available (dad's export never arrived; Cameron is a PG&E customer with
    no solar). The reconciliation trust artifact is the 11 PG&E bills, unaffected by this.
    Swap in a real Green Button export to get a real household's numbers.

    PYTHONPATH=src python scripts/nem3_report.py
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from greenbutton.models import (
    COL_ESTIMATED,
    COL_KWH,
    Direction,
    IntervalSeries,
    MeterMeta,
    Utility,
)
from nem3.acc import ExportRateSchedule, Vintage
from nem3.netting import NbtSettings
from nem3.payback import InstallCosts, compare_vintage_timing, evaluate
from nem3.pvwatts import ProductionResult, SystemSpec
from tariffs.bill import marginal_energy_price
from tariffs.loader import load_spec_versions
from tariffs.schema import Layer, Service
from uncertainty.montecarlo import simulate_payback

YEAR = 2026
TZ = "America/Los_Angeles"

# CALENDAR 2026. This window used to start on 2026-06-01 because that was the only
# committed SDG&E vintage and `marginal_energy_price` refuses to price a date no spec
# covers rather than extrapolating backwards. The 1/1/2026, 4/1/2026 and 2026-05-01
# TOU-DR1 vintages are now transcribed, so a calendar year is covered end to end and the
# run crosses four rate versions per layer instead of one.
#
# That matters for more than tidiness: January-April are priced by vintages on which the
# weekday 10:00-14:00 window is NOT super-off-peak (the year-round extension took effect
# 2026-05-01), so a battery scheduled against this window sees the real, changing daytime
# price rather than one year's rule projected backwards over the whole span.
START = date(YEAR, 1, 1)
END = date(YEAR, 12, 31)  # inclusive


def _window(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    lo = pd.Timestamp(START, tz=TZ)
    hi = pd.Timestamp(END + timedelta(days=1), tz=TZ)
    return idx[(idx >= lo) & (idx < hi)]


def _analysis_index() -> pd.DatetimeIndex:
    """Hourly local timestamps over [START, END], spanning two calendar years."""
    full = pd.date_range(f"{YEAR}-01-01", f"{YEAR + 1}-12-31 23:00", freq="h", tz=TZ)
    return _window(full)


def illustrative_load() -> IntervalSeries:
    """A synthetic evening-peaked San Diego household, ~6,500 kWh/yr. NOT real meter data."""
    idx = _analysis_index()
    h = idx.hour.values
    doy = idx.dayofyear.values
    base = 0.45 + 0.9 * np.exp(-((h - 20) ** 2) / 6) + 0.3 * np.exp(-((h - 7) ** 2) / 5)
    summer = 1.0 + 0.35 * np.exp(-((doy - 215) ** 2) / 2500)  # AC bump in Aug
    kwh = base * summer
    return IntervalSeries(
        utility=Utility.SDGE,
        direction=Direction.IMPORT,
        interval=timedelta(hours=1),
        meta=MeterMeta(utility=Utility.SDGE, source_file="ILLUSTRATIVE (synthetic)"),
        frame=pd.DataFrame({COL_KWH: kwh, COL_ESTIMATED: False}, index=idx),
    )


def illustrative_production(system_kw: float) -> pd.Series:
    """A synthetic clear-sky-ish daily bell for a south array. NOT a PVWatts fetch.

    Built per calendar year and then sliced to the analysis window, because that is how a
    real PVWatts result arrives (a generic 8760 mapped onto one year's wall clock) — see
    ``ProductionResult.to_series``.
    """
    idx = pd.date_range(f"{YEAR}-01-01", periods=8760, freq="h", tz=TZ)
    h = idx.hour.values
    doy = idx.dayofyear.values
    daylight = np.clip(np.sin(np.pi * (h - 6.5) / 11), 0, None)
    seasonal = 0.75 + 0.25 * np.cos(2 * np.pi * (doy - 172) / 365)  # summer > winter
    ac = system_kw * 0.78 * daylight * seasonal
    result = ProductionResult(
        spec=SystemSpec(32.7, -117.16, system_kw, 20, 180),
        ac_kwh=ac,
        station_info={"note": "synthetic"},
        source="synthetic-illustrative",
        fetched_at="n/a",
    )
    both = pd.concat([result.to_series(YEAR), result.to_series(YEAR + 1)])
    return both[_window(pd.DatetimeIndex(both.index))]


def monthly_periods() -> list[tuple[date, date]]:
    """Calendar-month billing periods over the analysis window."""
    out = []
    d = START
    while d <= END:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        e = min(nxt - timedelta(days=1), END)
        out.append((d, e))
        d = e + timedelta(days=1)
    return out


def main() -> None:
    load = illustrative_load()
    system_kw = 5.0
    production = illustrative_production(system_kw)

    delivery = load_spec_versions("TOU-DR1", Layer.DELIVERY)
    # Both halves of the schedule are now real: SDG&E's UDC + WF-NBC/DWR-BC (delivery) and
    # Schedule EECC (generation, bundled). The two re-sum to SDG&E's own printed Total
    # Electric Rate — see tests/tariffs/test_sdge_layers.py — so the dollar totals below are
    # no longer illustrative for a BUNDLED SDG&E household. (A CCA customer pays their CCA's
    # generation rate plus the vintaged PCIA instead of EECC; that overlay is still
    # un-authored, so this run is bundled-only. The LOAD remains synthetic — see below.)
    # provider is now required: TOU-DR1 generation can be supplied by SDG&E (bundled EECC)
    # or by a CCA, and their rates differ by up to 20 c/kWh in a single period.
    generation = load_spec_versions("TOU-DR1", Layer.GENERATION, provider="SDG&E")

    settings = NbtSettings(
        care=False,
        service=Service.BUNDLED,
        territory="coastal_basic",
        low_income=False,
        acc_plus_eligible=False,  # SDG&E ACC Plus unconfirmed; conservative (see acc.py)
    )
    schedule = ExportRateSchedule(
        "SDG&E", Vintage(application_year=YEAR, pto_date=date(YEAR, 4, 1))
    )
    periods = monthly_periods()
    idx = load.frame.index
    # Marginal retail import $/kWh, read off the same two specs the biller uses, so the
    # dispatch model and the settlement cannot disagree about what an imported kWh costs.
    # This replaces a hand-typed vector (0.62 / 0.40 / 0.22 on / off / super-off) that was
    # wrong in the direction that matters: TOU-DR1's real super-off-peak total is 0.37660,
    # not 0.22 — a 71% understatement of the cost of importing in exactly the window a
    # battery is most likely to charge in, which biased arbitrage toward the battery.
    imp_price = marginal_energy_price([delivery, generation], idx, care=settings.care)
    exp_price = (schedule.rates(idx)["delivery"] + schedule.rates(idx)["generation"]).to_numpy()

    print("=" * 78)
    print("M3 — NEM 3.0 solar + battery, SDG&E TOU-DR1 (Net Billing Tariff)")
    print("=" * 78)
    print(f"System: {system_kw:.1f} kW south array + one battery (Powerwall-class default)")
    print(f"Load:   {load.total_kwh:,.0f} kWh/yr  [ILLUSTRATIVE synthetic profile]")
    print(f"        production {float(production.sum()):,.0f} kWh/yr")
    print(f"ACC:    SDG&E NBT{YEAR} vintage, locked through {schedule.vintage.lock_in_through}")
    print()

    scenarios = evaluate(
        load,
        production,
        delivery,
        generation,
        schedule,
        periods,
        settings=settings,
        utility=Utility.SDGE,
        system_kw=system_kw,
        import_price=imp_price,
        export_price=exp_price,
        costs=InstallCosts(),
    )

    print(f"{'Scenario':<56}{'bill/yr':>10}{'save/yr':>10}{'payback':>10}")
    print("-" * 86)
    baseline = scenarios[0].annual_bill + scenarios[0].annual_savings
    print(f"{'No solar (baseline)':<56}{baseline:>10,.0f}{'—':>10}{'—':>10}")
    for s in scenarios:
        pb = "never" if not s.pays_back else f"{s.simple_payback_years:.1f} yr"
        print(f"{s.name:<56}{s.annual_bill:>10,.0f}{s.annual_savings:>10,.0f}{pb:>10}")

    solar = scenarios[0]
    detail = solar.detail
    print()
    print(f"Non-bypassable import floor: ${detail.nbc_floor:,.0f}/yr on gross imports — no")
    print("amount of solar export can erase this (differentiation invariant 4).")

    greedy = next(s for s in scenarios if "greedy" in s.name)
    lp = next(s for s in scenarios if "LP" in s.name)
    lo, hi = sorted((greedy.annual_savings, lp.annual_savings))
    print()
    print("Battery strategies (realistic controller vs idealized optimizer), SETTLED savings:")
    print(f"  greedy TOU controller ${greedy.annual_savings:,.0f}/yr")
    print(f"  LP perfect-foresight  ${lp.annual_savings:,.0f}/yr")
    print(f"  band ${lo:,.0f}..${hi:,.0f}/yr. The LP optimizes a marginal-price proxy, so once")
    print("  the NBT credit caps and NBC floor are applied it is NOT guaranteed to beat the")
    if greedy.annual_savings >= lp.annual_savings:
        print("  greedy controller — and here it does not, a caution against quoting the LP alone.")
    else:
        print("  greedy controller — here it does, but the gap is the controller's headroom.")

    print()
    print("Vintage timing (the nine-year lock-in question no consumer tool answers):")
    from nem3.acc import MissingAccTableError

    try:
        # The semantically exact comparison for a 2026 shopper is 2026-vs-2027, but SDG&E
        # has not published the NBT2027 table yet (it posts a new vintage late each year),
        # so demonstrate on the two published vintages that DO exist.
        timing = compare_vintage_timing(
            load,
            production,
            delivery,
            generation,
            periods,
            settings=settings,
            utility=Utility.SDGE,
            this_year=2025,
        )
        print(f"  apply {timing.this_year}: net bill ${-timing.this_year_savings:,.0f}/yr")
        print(f"  apply {timing.next_year}: net bill ${-timing.next_year_savings:,.0f}/yr")
        print(f"  -> {timing.recommendation}")
        print("  FINDING: SDG&E's published NBT2025, NBT2026 and current-year export tables")
        print("  are byte-identical for every overlapping year — the nine-year lock-in")
        print("  currently confers no advantage on SDG&E, unlike the PG&E case installers cite.")
        print("  (2026-vs-2027 needs SDG&E's NBT2027 table, not yet published — the tool")
        print("   refuses to extrapolate an avoided-cost forecast rather than guess it.)")
    except MissingAccTableError as e:
        print(f"  next year's ACC vintage is not published yet: {e}")

    print()
    print("Payback distribution (Monte Carlo over rate escalation, degradation, load drift):")
    for s in (solar, greedy):
        if s.annual_savings <= 0:
            print(f"  {s.name}: negative annual savings — does not pay back. Reason: the NBC")
            print("    floor and fixed charges exceed what this array's exports can offset.")
            continue
        dist = simulate_payback(s.upfront_cost, s.annual_savings, horizon_years=25)
        print(f"  {s.name}:")
        print(f"    upfront ${s.upfront_cost:,.0f} (after 30% ITC) — {dist.summary()}")

    print()
    print("Notes (failure conditions carried per invariant 2):")
    for n in detail.notes:
        print(f"  - {n}")


if __name__ == "__main__":
    main()
