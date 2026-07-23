"""The pure billing function: (interval series + spec + period) -> itemized bill.

No I/O, no network, deterministic. All utility-specific structure lives in the spec.
The output mirrors how PG&E presents a bill (full-rate energy lines + a CARE Discount
line; per-season sub-periods when a rate season changes mid-period), so a line-by-line
reconciliation against a real statement is direct.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from greenbutton.models import LOCAL_TZ, IntervalSeries

from .holidays import holiday_dates
from .schema import Layer, Season, TariffSpec, TouDef

CENTS = 2


def _r(x: float) -> float:
    """Round to cents the way each bill line is rounded before summing."""
    return round(x + 1e-9, CENTS)


class LineItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    amount: float
    season: str | None = None
    quantity: float | None = None
    unit: str | None = None
    rate: float | None = None


class LayerBill(BaseModel):
    model_config = ConfigDict(frozen=True)

    layer: Layer
    provider: str
    schedule_id: str
    line_items: list[LineItem]
    total: float

    def bucket(self) -> dict[str, float]:
        """Amounts summed by line name (collapses per-season sub-period splits)."""
        out: dict[str, float] = {}
        for li in self.line_items:
            out[li.name] = _r(out.get(li.name, 0.0) + li.amount)
        return out


class Bill(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_start: date
    period_end: date
    total_kwh: float
    layers: list[LayerBill]
    observed_adjustments: list[LineItem] = []

    @property
    def total(self) -> float:
        t = sum(layer.total for layer in self.layers)
        t += sum(a.amount for a in self.observed_adjustments)
        return _r(t)


# --- period / usage helpers ------------------------------------------------


def _season_subperiods(
    start: date, end_inclusive: date, spec: TariffSpec
) -> list[tuple[Season, date, date]]:
    """Split [start, end] into maximal runs of days sharing one rate season."""
    runs: list[tuple[Season, date, date]] = []
    d = start
    run_start = start
    run_season = spec.seasons.season_for(start.month)
    while d <= end_inclusive:
        s = spec.seasons.season_for(d.month)
        if s != run_season:
            runs.append((run_season, run_start, d - timedelta(days=1)))
            run_start, run_season = d, s
        d += timedelta(days=1)
    runs.append((run_season, run_start, end_inclusive))
    return runs


def _version_for(
    day: date, versions: Sequence[TariffSpec], *, allow_before_effective: bool = False
) -> TariffSpec:
    """Newest spec version whose effective_date is on or before ``day``."""
    chosen = None
    for v in versions:  # versions arrive sorted ascending by effective_date
        if v.effective_date <= day:
            chosen = v
    if chosen is None:
        if allow_before_effective:
            return versions[0]
        raise ValueError(
            f"no {versions[0].schedule_id} {versions[0].layer} spec effective on {day} "
            f"(earliest version is {versions[0].effective_date})"
        )
    return chosen


def _rate_subperiods(
    start: date,
    end_inclusive: date,
    versions: Sequence[TariffSpec],
    *,
    allow_before_effective: bool = False,
) -> list[tuple[TariffSpec, Season, date, date]]:
    """Split [start, end] into maximal runs sharing one (spec version, season).

    A single billing period can cross both a season boundary (Jun 1) and a rate-version
    effective date (e.g. PG&E's 2026-03-01 IGFC change, or 3CE's 2026-02-15 generation
    update), and the two layers change on different dates. PG&E itemizes each such run as
    its own sub-block; this reproduces that split so line items sum to the bill.
    """
    pick = lambda d: _version_for(  # noqa: E731
        d, versions, allow_before_effective=allow_before_effective
    )
    runs: list[tuple[TariffSpec, Season, date, date]] = []
    d = start
    run_start = start
    cur_v = pick(start)
    cur_s = cur_v.seasons.season_for(start.month)
    while d <= end_inclusive:
        v = pick(d)
        s = v.seasons.season_for(d.month)
        if v is not cur_v or s != cur_s:
            runs.append((cur_v, cur_s, run_start, d - timedelta(days=1)))
            run_start, cur_v, cur_s = d, v, s
        d += timedelta(days=1)
    runs.append((cur_v, cur_s, run_start, end_inclusive))
    return runs


def _period_table(tou: TouDef) -> np.ndarray:
    """(month, day-type, hour) -> index into ``tou.periods``.

    12 x 2 x 24 = 576 cells, resolved once per sub-period by the same first-match-wins
    rule walk the schedule declares. Day-type axis: 0 = weekend/holiday, 1 = weekday.
    """
    periods = tou.periods
    table = np.empty((12, 2, 24), dtype=np.int8)
    for m in range(12):
        for wd in (0, 1):
            for h in range(24):
                table[m, wd, h] = periods.index(tou.period_for(h, m + 1, weekday=bool(wd)))
    return table


def _usage(
    series: IntervalSeries, spec: TariffSpec, d0: date, d1_inclusive: date
) -> dict[str, float]:
    """kWh per TOU period over [d0 00:00, d1+1 00:00) in local time.

    Keys are ``spec.tou.periods`` in bill-line order; a period with no usage still
    appears (as 0.0) so the bill shows every line the schedule defines.
    """
    idx = series.frame.index
    lo = pd.Timestamp(d0, tz=LOCAL_TZ)
    hi = pd.Timestamp(d1_inclusive + timedelta(days=1), tz=LOCAL_TZ)
    sub = series.frame[(idx >= lo) & (idx < hi)]
    tou = spec.tou
    periods = tou.periods

    sidx = sub.index
    if tou.day_type_sensitive:
        holidays = set().union(
            *(holiday_dates(tou.holiday_calendar, y) for y in {d0.year, d1_inclusive.year})
        )
        is_weekend = sidx.dayofweek.values >= 5
        if holidays:
            is_weekend = is_weekend | np.isin(sidx.date, list(holidays))
        wd = (~is_weekend).astype(np.int8)
    else:
        wd = np.ones(len(sidx), dtype=np.int8)  # day type is irrelevant; any axis works

    codes = _period_table(tou)[sidx.month.values - 1, wd, sidx.hour.values]
    kwh = sub["kwh"].to_numpy()
    return {p: float(kwh[codes == i].sum()) for i, p in enumerate(periods)}


# --- the billing function --------------------------------------------------


def compute_layer(
    series: IntervalSeries,
    spec: TariffSpec | Sequence[TariffSpec],
    period_start: date,
    period_end: date,
    *,
    care: bool = False,
    allow_before_effective: bool = False,
) -> LayerBill:
    """Itemize one layer (delivery or generation) over an inclusive date period.

    ``spec`` may be a single :class:`TariffSpec` or several effective-dated versions of
    the same layer; when the period spans a version's effective date the period is split
    at that boundary (see :func:`_rate_subperiods`) and each run billed on its version.

    ``allow_before_effective`` prices days that predate the earliest version anyway, using
    that earliest version. It is off by default so a *reconciliation* can never silently
    bill a real statement on rates that did not exist yet. The M2 optimizer turns it on
    deliberately: it re-prices a past year of load at today's rates, which is a
    counterfactual, not a reproduction of a bill.
    """
    if isinstance(spec, TariffSpec):
        versions = [spec]
    else:
        versions = sorted(spec, key=lambda s: s.effective_date)
    if not versions:
        raise ValueError("compute_layer: no spec version supplied")
    meta = versions[-1]  # schedule_id/provider/layer are shared across versions
    items: list[LineItem] = []

    for spec, season, d0, d1 in _rate_subperiods(
        period_start, period_end, versions, allow_before_effective=allow_before_effective
    ):
        days = (d1 - d0).days + 1
        usage = _usage(series, spec, d0, d1)
        total_kwh = sum(usage.values())
        tag = season.value
        # Build this sub-period's lines locally: percent surcharges below must apply to
        # THIS run's subtotal only. Two runs can share a season tag (a version change
        # within one season, e.g. 3CE's 2026-02-15 update), so filtering by season tag
        # would let a later run's surcharge double-count an earlier run's charges.
        sub: list[LineItem] = []

        # Fixed charge (per day).
        if spec.fixed_per_day is not None:
            rate = spec.fixed_per_day.for_customer(care=care, what=spec.fixed_name)
            sub.append(
                LineItem(
                    name=spec.fixed_name,
                    season=tag,
                    quantity=days,
                    unit="day",
                    rate=rate,
                    amount=_r(days * rate),
                )
            )

        # Energy (charged at standard rate; CARE handled as a discount line below).
        if spec.energy is not None:
            for period, kwh in usage.items():
                label = spec.tou.label(period)
                std = spec.energy_rate(season, period).for_customer(
                    care=False, what=f"{label} energy"
                )
                sub.append(
                    LineItem(
                        name=f"Energy {label}",
                        season=tag,
                        quantity=_r(kwh),
                        unit="kWh",
                        rate=std,
                        amount=_r(kwh * std),
                    )
                )

        # Baseline credit: min(usage, allowance) x credit (standard rate).
        credited_kwh = 0.0
        if spec.baseline is not None:
            credited_kwh = spec.baseline.credited_kwh(season, days, total_kwh)
            cr = spec.baseline.credit_per_kwh.for_customer(care=False, what="baseline credit")
            sub.append(
                LineItem(
                    name="Baseline Credit",
                    season=tag,
                    quantity=_r(credited_kwh),
                    unit="kWh",
                    rate=cr,
                    amount=_r(credited_kwh * cr),
                )
            )

        # CARE discount = sum (care - standard) x kWh over energy + baseline credit.
        # Only emitted for layers that actually define CARE rates (delivery, not 3CE).
        if care and spec.energy is not None:
            disc = 0.0
            has_care = False
            for period, kwh in usage.items():
                r = spec.energy_rate(season, period)
                if r.care is not None and r.standard is not None:
                    disc += kwh * (r.care - r.standard)
                    has_care = True
            if spec.baseline is not None:
                bc = spec.baseline.credit_per_kwh
                if bc.care is not None and bc.standard is not None:
                    disc += credited_kwh * (bc.care - bc.standard)
                    has_care = True
            if has_care:
                sub.append(LineItem(name="CARE Discount", season=tag, amount=_r(disc)))

        # Per-kWh adders (PCIA, generation credit, ...). May be flat, seasonal, or TOU;
        # a TOU adder (e.g. the TOU-weighted Generation Credit) reports no single rate.
        for adder in spec.adders:
            amt, rate = adder.amount(season, usage)
            sub.append(
                LineItem(
                    name=adder.name,
                    season=tag,
                    quantity=_r(total_kwh),
                    unit="kWh",
                    rate=rate,
                    amount=_r(amt),
                )
            )

        # Energy Commission Tax (generation layer), per kWh.
        if spec.energy_commission_tax_per_kwh is not None:
            r = spec.energy_commission_tax_per_kwh
            sub.append(
                LineItem(
                    name="Energy Commission Tax",
                    season=tag,
                    quantity=_r(total_kwh),
                    unit="kWh",
                    rate=r,
                    amount=_r(total_kwh * r),
                )
            )

        # Percent surcharges (franchise fee on energy; UUT on pretax subtotal), each on
        # this sub-period's own subtotal.
        pretax = sum(li.amount for li in sub)
        energy_sub = sum(li.amount for li in sub if li.name.startswith("Energy "))
        for sur in spec.surcharges:
            amt, rate = sur.amount(pretax=pretax, energy=energy_sub, kwh=total_kwh)
            sub.append(LineItem(name=sur.name, season=tag, rate=rate, amount=_r(amt)))

        items.extend(sub)

    # Minimum bill: a floor on the *layer* total over the whole period (SDG&E). Applied
    # once, not per sub-period, since the tariff states it per billing month; the shortfall
    # is emitted as its own line so the reconciliation shows when the floor bound.
    if meta.minimum_bill is not None:
        days = (period_end - period_start).days + 1
        floor = days * meta.minimum_bill.per_day.for_customer(
            care=care, what=meta.minimum_bill.name
        )
        so_far = sum(li.amount for li in items)
        if so_far < floor:
            items.append(
                LineItem(
                    name=meta.minimum_bill.name,
                    quantity=days,
                    unit="day",
                    amount=_r(floor - so_far),
                )
            )

    total = _r(sum(li.amount for li in items))
    return LayerBill(
        layer=meta.layer,
        provider=meta.provider,
        schedule_id=meta.schedule_id,
        line_items=items,
        total=total,
    )


def compute_bill(
    series: IntervalSeries,
    specs: Sequence[TariffSpec | Sequence[TariffSpec]],
    period_start: date,
    period_end: date,
    *,
    care: bool = False,
    observed_adjustments: list[LineItem] | None = None,
    allow_before_effective: bool = False,
) -> Bill:
    """Itemize a full multi-layer bill (delivery + generation + observed adjustments).

    Each element of ``specs`` is one layer, given either as a single spec or as several
    effective-dated versions of that layer (see :func:`compute_layer`).
    """
    layers = [
        compute_layer(
            series,
            s,
            period_start,
            period_end,
            care=care,
            allow_before_effective=allow_before_effective,
        )
        for s in specs
    ]
    first = specs[0]
    tou_spec = first if isinstance(first, TariffSpec) else next(iter(first))
    usage = _usage(series, tou_spec, period_start, period_end)
    return Bill(
        period_start=period_start,
        period_end=period_end,
        total_kwh=_r(sum(usage.values())),
        layers=layers,
        observed_adjustments=observed_adjustments or [],
    )
