"""Battery dispatch: a greedy TOU heuristic AND a cvxpy LP optimum, always both.

CLAUDE.md: "start with a greedy TOU-arbitrage heuristic for interpretability, then
LP-optimal via cvxpy; always report both so users see the gap between realistic controller
behavior and theoretical optimum." That gap is a first-class honest-broker output: the LP
knows the whole year in advance and is physically unachievable, so quoting only the LP
oversells the battery. Quoting only the greedy understates a well-configured controller.
The truth for a real household sits between them, and the width of the band is information.

Both dispatchers take the *no-battery* import and export series (from
:mod:`nem3.solar`) and an hour-indexed retail import price and ACC export price, and
return a modified (import, export) pair the NBT settlement then values. The battery only
moves energy in time — it never creates or destroys the customer's load.

Modeling choices, all conservative and stated:
- **Round-trip efficiency** is applied on charge (``sqrt(eta)`` each way), so stored energy
  costs more than it returns — the arbitrage must beat the loss to be worth doing.
- **The greedy rule** is the one a real TOU controller runs without a forecast: charge from
  surplus solar first, then charge from the grid during the cheapest hours only if that
  energy can later displace a strictly more expensive import; discharge to cover load
  during the most expensive (peak) hours. It is causal — no lookahead beyond the day.
- **The LP** maximizes bill savings over the horizon with perfect foresight, subject to
  power and energy limits and efficiency. It is the unreachable ceiling, labeled as such.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from greenbutton.models import COL_ESTIMATED, COL_KWH, Direction, IntervalSeries


@dataclass(frozen=True)
class Battery:
    """A home battery. Defaults ≈ one Tesla Powerwall 3."""

    usable_kwh: float = 13.5
    max_power_kw: float = 5.0
    round_trip_efficiency: float = 0.90
    min_soc_frac: float = 0.0  # reserve floor (e.g. 0.2 for backup); usable is above this

    @property
    def eta_one_way(self) -> float:
        return float(np.sqrt(self.round_trip_efficiency))


@dataclass(frozen=True)
class DispatchResult:
    imports: IntervalSeries
    exports: IntervalSeries
    label: str  # "greedy" | "lp"
    cycles: float  # equivalent full cycles over the horizon (battery wear proxy)


def _rebuild(base: IntervalSeries, kwh: np.ndarray, direction: Direction) -> IntervalSeries:
    frame = pd.DataFrame(
        {COL_KWH: kwh, COL_ESTIMATED: base.frame[COL_ESTIMATED].to_numpy()},
        index=base.frame.index,
    )
    return base.model_copy(update={"frame": frame, "direction": direction})


def _prep(imports: IntervalSeries, exports: IntervalSeries) -> tuple[np.ndarray, np.ndarray, float]:
    if not imports.frame.index.equals(exports.frame.index):
        raise ValueError("import and export series must share an index")
    imp = imports.frame[COL_KWH].to_numpy().astype(float)
    exp = exports.frame[COL_KWH].to_numpy().astype(float)
    step_h = imports.interval.total_seconds() / 3600.0
    return imp, exp, step_h


def greedy_dispatch(
    imports: IntervalSeries,
    exports: IntervalSeries,
    import_price: np.ndarray,
    export_price: np.ndarray,
    battery: Battery,
) -> DispatchResult:
    """Causal TOU controller: soak up surplus solar, discharge into the priciest imports.

    No forecast beyond the daily price pattern. Per interval, in order:
    1. Charge from any solar surplus (free energy) up to power/energy headroom.
    2. Discharge to cover import whenever the current import price is above the day's
       median import price (a proxy for "peak") and there is stored energy.
    Grid charging is deliberately omitted from the heuristic: a solar household's battery
    is almost always solar-charged, and grid arbitrage under NBT rarely clears the
    round-trip loss plus NBCs. The LP below is free to grid-charge, so any value from it
    shows up as part of the greedy-to-optimum gap rather than being silently assumed.
    """
    imp, exp, step_h = _prep(imports, exports)
    cap = battery.usable_kwh
    p_max = battery.max_power_kw * step_h
    eta = battery.eta_one_way

    idx = imports.frame.index
    price = pd.Series(import_price, index=idx)
    # "Peak" = above each day's own median import price, so the rule tracks TOU windows
    # without hard-coding them.
    day_median = price.groupby(idx.date).transform("median").to_numpy()

    soc = 0.0
    out_imp = imp.copy()
    out_exp = exp.copy()
    throughput = 0.0
    for t in range(len(imp)):
        # 1. Charge from surplus solar.
        if out_exp[t] > 0 and soc < cap:
            charge = min(out_exp[t], p_max, (cap - soc) / eta)
            soc += charge * eta
            out_exp[t] -= charge
            throughput += charge * eta
        # 2. Discharge into expensive imports.
        if out_imp[t] > 0 and soc > 0 and import_price[t] >= day_median[t]:
            discharge = min(out_imp[t] / eta, p_max, soc)
            soc -= discharge
            out_imp[t] -= discharge * eta
    cycles = throughput / cap if cap else 0.0
    return DispatchResult(
        imports=_rebuild(imports, out_imp, Direction.IMPORT),
        exports=_rebuild(exports, out_exp, Direction.EXPORT),
        label="greedy",
        cycles=round(cycles, 1),
    )


def lp_dispatch(
    imports: IntervalSeries,
    exports: IntervalSeries,
    import_price: np.ndarray,
    export_price: np.ndarray,
    battery: Battery,
    *,
    allow_grid_charge: bool = True,
) -> DispatchResult:
    """Perfect-foresight LP upper bound on battery value (cvxpy).

    Maximizes (avoided import cost + export revenue) over the whole horizon subject to
    power, energy and efficiency constraints. This is unreachable — it knows every future
    price and load — and is reported only as the ceiling on what a battery could ever save
    against the greedy controller's realistic floor.

    The objective uses the *marginal* retail import price and ACC export price supplied by
    the caller; it does not re-derive NBT netting (credit caps, buckets), so the LP is an
    optimistic bound in that respect too. The final dollar figures always come from
    :mod:`nem3.netting` applied to the dispatched series, not from this objective.
    """
    import cvxpy as cp

    imp, exp, step_h = _prep(imports, exports)
    n = len(imp)
    cap = battery.usable_kwh
    p_max = battery.max_power_kw * step_h
    eta = battery.eta_one_way

    # Model the four battery energy flows directly rather than a signed net, so power and
    # efficiency constraints stay linear and the sign of every term is unambiguous.
    charge = cp.Variable(n, nonneg=True)  # energy into the battery terminal
    discharge = cp.Variable(n, nonneg=True)  # energy out of the battery terminal
    soc = cp.Variable(n + 1, nonneg=True)
    solar_to_batt = cp.Variable(n, nonneg=True)
    grid_to_batt = cp.Variable(n, nonneg=True)
    batt_to_load = cp.Variable(n, nonneg=True)
    batt_to_grid = cp.Variable(n, nonneg=True)

    new_import = imp + grid_to_batt - batt_to_load
    new_export = exp - solar_to_batt + batt_to_grid

    constraints = [
        charge == solar_to_batt + grid_to_batt,
        discharge == batt_to_load + batt_to_grid,
        solar_to_batt <= exp,
        batt_to_load <= imp,
        new_import >= 0,
        new_export >= 0,
        charge <= p_max,
        discharge <= p_max,
        soc[0] == 0,
        soc[1:] == soc[:-1] + charge * eta - discharge / eta,
        soc <= cap,
    ]
    if not allow_grid_charge:
        constraints.append(grid_to_batt == 0)

    cost = import_price @ new_import - export_price @ new_export
    prob = cp.Problem(cp.Minimize(cost), constraints)
    prob.solve()
    if prob.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"LP dispatch did not solve (status {prob.status})")

    ni = np.clip(new_import.value, 0.0, None)
    ne = np.clip(new_export.value, 0.0, None)
    throughput = float(np.sum(np.maximum(charge.value, 0.0)) * eta)
    cycles = throughput / cap if cap else 0.0
    return DispatchResult(
        imports=_rebuild(imports, ni, Direction.IMPORT),
        exports=_rebuild(exports, ne, Direction.EXPORT),
        label="lp",
        cycles=round(cycles, 1),
    )
