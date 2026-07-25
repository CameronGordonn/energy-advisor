"""Monte Carlo over the assumptions behind a payback figure — invariant 3.

A single payback number implies a certainty the inputs do not have. Three assumptions
dominate a 20-year solar/battery payback, and all three are genuinely uncertain:

- **Rate escalation**: how fast retail import rates (and thus avoided-cost savings) grow.
  CA IOU residential rates have risen well above general inflation, but the forward path
  is a distribution, not a line.
- **Panel degradation**: production declines ~0.4-0.7%/yr; the exact rate varies by module.
- **Load drift**: the household's consumption trends up or down (electrification, occupancy).

This wrapper takes a *first-year* savings figure and the deterministic pieces it depends on,
samples the three drivers, and reports the payback as a distribution (percentiles), plus the
probability the system never pays back within its warranty life. It deliberately does not
re-run the full interval settlement per sample — that would be thousands of year-long
simulations — but scales the first-year savings by physically-grounded annual factors, which
is the standard cash-flow treatment and keeps the honest range honest without implying
false precision the underlying data cannot support.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Drivers:
    """Distributions for the three payback drivers. Means/SDs are annual fractional rates.

    Defaults are round, defensible central values with wide-enough spreads to avoid false
    precision; a caller with better local data should override them. They are assumptions,
    stated as such, not measurements.
    """

    rate_escalation_mean: float = 0.045  # CA residential rates have run ~4-6%/yr
    rate_escalation_sd: float = 0.02
    degradation_mean: float = 0.005  # ~0.5%/yr module degradation
    degradation_sd: float = 0.0015
    load_drift_mean: float = 0.0  # no assumed trend unless the caller supplies one
    load_drift_sd: float = 0.01
    discount_rate: float = 0.0  # set >0 to report discounted payback / NPV instead


DEFAULT_DRIVERS = Drivers()


@dataclass(frozen=True)
class PaybackDistribution:
    upfront_cost: float
    first_year_savings: float
    horizon_years: int
    payback_p10: float | None
    payback_p50: float | None
    payback_p90: float | None
    prob_never_pays_back: float
    cumulative_savings_p50: float
    samples: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))

    def summary(self) -> str:
        def fmt(v: float | None) -> str:
            return "never" if v is None else f"{v:.1f} yr"

        return (
            f"payback P10 {fmt(self.payback_p10)} / P50 {fmt(self.payback_p50)} / "
            f"P90 {fmt(self.payback_p90)}; "
            f"P(never within {self.horizon_years} yr) = {self.prob_never_pays_back:.0%}; "
            f"median {self.horizon_years}-yr cumulative savings "
            f"${self.cumulative_savings_p50:,.0f}"
        )


def simulate_payback(
    upfront_cost: float,
    first_year_savings: float,
    *,
    horizon_years: int = 25,
    drivers: Drivers = DEFAULT_DRIVERS,
    n: int = 10_000,
    seed: int = 0,
) -> PaybackDistribution:
    """Sample cumulative savings over ``horizon_years`` and derive the payback distribution.

    Each sample draws one escalation, degradation and drift rate (held constant across the
    horizon, the standard simplification), builds the annual savings stream

        savings_y = first_year_savings * (1 + escalation + drift - degradation) ** y

    and finds the first year cumulative savings cover ``upfront_cost``. Samples that never
    cover it within the horizon contribute to ``prob_never_pays_back``.
    """
    rng = np.random.default_rng(seed)
    esc = rng.normal(drivers.rate_escalation_mean, drivers.rate_escalation_sd, n)
    deg = np.clip(rng.normal(drivers.degradation_mean, drivers.degradation_sd, n), 0, None)
    drift = rng.normal(drivers.load_drift_mean, drivers.load_drift_sd, n)

    years = np.arange(horizon_years)
    # growth factor per sample per year: (1 + esc + drift - deg) ** y
    g = (1.0 + esc + drift - deg)[:, None] ** years[None, :]
    annual = first_year_savings * g
    if drivers.discount_rate > 0:
        annual = annual / (1.0 + drivers.discount_rate) ** years[None, :]
    cumulative = np.cumsum(annual, axis=1)

    covered = cumulative >= upfront_cost
    ever = covered.any(axis=1)
    first_year = np.where(ever, covered.argmax(axis=1) + 1, horizon_years + 1).astype(float)
    paid = first_year[ever]

    def pct(p: float) -> float | None:
        return float(np.percentile(paid, p)) if paid.size else None

    return PaybackDistribution(
        upfront_cost=round(upfront_cost, 2),
        first_year_savings=round(first_year_savings, 2),
        horizon_years=horizon_years,
        payback_p10=pct(10),
        payback_p50=pct(50),
        payback_p90=pct(90),
        prob_never_pays_back=round(float((~ever).mean()), 3),
        cumulative_savings_p50=round(float(np.percentile(cumulative[:, -1], 50)), 2),
        samples=first_year,
    )
