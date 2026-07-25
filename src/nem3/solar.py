"""Behind-the-meter physics: combine real load and modeled production into meter channels.

The NBT settles two metered channels — import and export — but a customer's meter only
sees their *net* flow each interval. Self-consumed solar never crosses the meter. So given

    load[t]        (the customer's real metered consumption, invariant 6)
    production[t]  (PVWatts AC output for the proposed array)

the physical import/export channels are, with no battery,

    import[t] = max(0, load[t] - production[t])
    export[t] = max(0, production[t] - load[t])

This module builds those two :class:`IntervalSeries`. It never touches the load *shape* —
production is subtracted interval by interval, self-consumption falls out of the max(),
and what remains is exactly what the meter would register. Battery dispatch (see
:mod:`nem3.battery`) modifies the export/import split further by time-shifting energy, but
the settlement in :mod:`nem3.netting` is identical either way.
"""

from __future__ import annotations

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


def align_production(load: IntervalSeries, production: pd.Series) -> np.ndarray:
    """Production kWh aligned onto ``load``'s index; hours with no PVWatts value are 0.

    PVWatts is hourly; the load meter here is hourly too, but a 15-minute meter would need
    the hourly production spread across its sub-intervals. That split is done by forward-
    filling the hourly rate and dividing by the number of sub-intervals per hour, so total
    production is conserved regardless of meter resolution.
    """
    idx = load.frame.index
    step_h = load.interval.total_seconds() / 3600.0
    per_hour = round(1.0 / step_h) if step_h < 1.0 else 1
    # Align on tz-naive hour keys: flooring a tz-aware index raises on the ambiguous
    # fall-back hour, and the hour label alone is enough to join production to load.
    prod_by_hour = pd.Series(
        production.to_numpy(dtype=float),
        index=production.index.tz_localize(None).floor("h"),
    )
    prod_by_hour = prod_by_hour[~prod_by_hour.index.duplicated()]
    keys = idx.tz_localize(None).floor("h")
    vals = prod_by_hour.reindex(keys).to_numpy(dtype=float)
    vals = np.where(np.isnan(vals), 0.0, vals)
    if per_hour > 1:
        vals = vals / per_hour
    return vals


def _series_like(
    load: IntervalSeries, kwh: np.ndarray, direction: Direction, note: str
) -> IntervalSeries:
    frame = pd.DataFrame(
        {COL_KWH: kwh, COL_ESTIMATED: load.frame[COL_ESTIMATED].to_numpy()},
        index=load.frame.index,
    )
    meta = MeterMeta(
        utility=load.meta.utility,
        service_id=load.meta.service_id,
        account_tail=load.meta.account_tail,
        address_zip=load.meta.address_zip,
        source_file=f"{load.meta.source_file or 'load'} + PV ({note})",
    )
    return IntervalSeries(
        utility=load.utility,
        direction=direction,
        interval=load.interval,
        unit=load.unit,
        meta=meta,
        frame=frame,
    )


def split_meter(
    load: IntervalSeries,
    production: pd.Series,
    *,
    utility: Utility | None = None,
) -> tuple[IntervalSeries, IntervalSeries]:
    """(import_series, export_series) for ``load`` with ``production``, no battery.

    Self-consumption is implicit: every kWh of production first offsets simultaneous load
    and only the surplus is exported, which is what a net meter records.
    """
    prod = align_production(load, production)
    net = load.frame[COL_KWH].to_numpy() - prod
    imports = np.clip(net, 0.0, None)
    exports = np.clip(-net, 0.0, None)
    imp = _series_like(load, imports, Direction.IMPORT, "solar imports")
    exp = _series_like(load, exports, Direction.EXPORT, "solar exports")
    if utility is not None:
        object.__setattr__(imp, "utility", utility)
        object.__setattr__(exp, "utility", utility)
    return imp, exp


def self_consumption_kwh(load: IntervalSeries, production: pd.Series) -> float:
    """Total kWh of production consumed on-site (neither imported nor exported)."""
    prod = align_production(load, production)
    return float(np.minimum(load.frame[COL_KWH].to_numpy(), prod).sum())
