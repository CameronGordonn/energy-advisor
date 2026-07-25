"""Behind-the-meter split and battery dispatch."""

from __future__ import annotations

import numpy as np
import pytest

from greenbutton.models import COL_KWH, Direction
from nem3.battery import Battery, greedy_dispatch, lp_dispatch
from nem3.solar import self_consumption_kwh, split_meter


def test_split_conserves_energy(load_series, production):
    imp, exp = split_meter(load_series, production)
    prod_total = float(production.sum())
    # import - export == load - production, exactly (self-consumption cancels).
    net = imp.total_kwh - exp.total_kwh
    assert net == pytest.approx(load_series.total_kwh - prod_total, abs=1e-6)


def test_split_directions_and_nonnegative(load_series, production):
    imp, exp = split_meter(load_series, production)
    assert imp.direction is Direction.IMPORT
    assert exp.direction is Direction.EXPORT
    assert (imp.frame[COL_KWH] >= 0).all()
    assert (exp.frame[COL_KWH] >= 0).all()
    # Never import and export in the same interval.
    assert not ((imp.frame[COL_KWH] > 0) & (exp.frame[COL_KWH] > 0)).any()


def test_self_consumption_plus_export_equals_production(load_series, production):
    _imp, exp = split_meter(load_series, production)
    sc = self_consumption_kwh(load_series, production)
    assert sc + exp.total_kwh == pytest.approx(float(production.sum()), abs=1e-6)


def _prices(index):
    h = index.hour.values
    imp_price = np.where(
        (h >= 16) & (h < 21), 0.60, np.where((h < 6) | ((h >= 10) & (h < 14)), 0.20, 0.35)
    )
    exp_price = np.full(len(index), 0.05)
    return imp_price, exp_price


def test_battery_preserves_total_load(load_series, production):
    imp, exp = split_meter(load_series, production)
    imp_price, exp_price = _prices(imp.frame.index)
    bat = Battery()
    for disp in (
        greedy_dispatch(imp, exp, imp_price, exp_price, bat),
        lp_dispatch(imp, exp, imp_price, exp_price, bat, allow_grid_charge=False),
    ):
        # Net metered energy (import - export) can only rise by the round-trip loss;
        # the battery moves energy in time, it does not conjure or delete load.
        base_net = imp.total_kwh - exp.total_kwh
        new_net = disp.imports.total_kwh - disp.exports.total_kwh
        assert new_net >= base_net - 1e-6  # losses make you import a bit more, never less


def test_battery_never_makes_you_worse_off_on_energy_value(load_series, production):
    imp, exp = split_meter(load_series, production)
    imp_price, exp_price = _prices(imp.frame.index)
    bat = Battery()

    def energy_cost(i, e):
        return float(
            imp_price @ i.frame[COL_KWH].to_numpy() - exp_price @ e.frame[COL_KWH].to_numpy()
        )

    base = energy_cost(imp, exp)
    g = greedy_dispatch(imp, exp, imp_price, exp_price, bat)
    lp = lp_dispatch(imp, exp, imp_price, exp_price, bat, allow_grid_charge=False)
    gc = energy_cost(g.imports, g.exports)
    lc = energy_cost(lp.imports, lp.exports)
    # The LP is the optimum, so it must be at least as good as greedy, which must be at
    # least as good as no battery — the gap the honest-broker output exists to show.
    assert lc <= gc + 1e-6
    assert gc <= base + 1e-6


def test_lp_beats_or_ties_greedy_strictly_when_arbitrage_exists(load_series, production):
    imp, exp = split_meter(load_series, production)
    imp_price, exp_price = _prices(imp.frame.index)
    bat = Battery()

    def energy_cost(i, e):
        return float(
            imp_price @ i.frame[COL_KWH].to_numpy() - exp_price @ e.frame[COL_KWH].to_numpy()
        )

    g = greedy_dispatch(imp, exp, imp_price, exp_price, bat)
    lp = lp_dispatch(imp, exp, imp_price, exp_price, bat, allow_grid_charge=False)
    # With a real peak/offpeak spread and daily surplus there is arbitrage to capture.
    assert energy_cost(lp.imports, lp.exports) < energy_cost(g.imports, g.exports)
