# CLAUDE.md — Home Energy Advisor

## Session continuity (READ FIRST, every session)

Before doing anything else in a new session, read **HANDOFF.md** (latest state + the
exact next action) and **SESSION_NOTES.md** (running decision log, newest first). These
carry context that isn't derivable from the code: pending decisions, flagged modeling
choices, and what the previous instance was mid-way through. Do not re-derive or
re-litigate anything already settled there.

Keep them current as you work: append decisions to SESSION_NOTES.md, and **rewrite
HANDOFF.md whenever you finish a milestone or pause** so the next instance can resume
cold. When context runs long, proactively offer the user a fresh handoff prompt.

## What this is

An independent home energy decision engine for California IOU customers (SDG&E first, PG&E second). A homeowner supplies their own Green Button interval data (manual CSV upload for now); the product answers, with numbers they can verify against their actual bills:

1. Which rate schedule minimizes their annual cost, with the counterfactual fully re-simulated.
2. Whether solar and/or a battery pays back under NEM 3.0 (Net Billing Tariff), including the ACC vintage lock-in timing question ("install this year vs next").
3. How sensitive every recommendation is to the assumptions behind it.

The customer brings the data. All other inputs are free public feeds. No imagery, no scraping, no paid data dependencies.

## Differentiation invariants (never violate these)

Every design decision gets tested against the competition: SDG&E's free rate self-analysis, nem3calculator.com (free, PG&E-focused), and installer-side tools (Aurora, Solargraf, Energy Toolbase, OpenSolar) that live inside sales funnels. We win by being the only tool that is simultaneously independent, reconciliation-verified, and uncertainty-honest. Concretely:

1. **Reconciliation-gated.** No feature that produces a dollar figure ships until the underlying bill engine reproduces real utility bills from real interval data within ±$2/month. Accuracy against actual bills is the product's trust artifact and its marketing. Every tariff schedule implementation must carry golden-bill regression tests.
2. **Honest broker.** The engine must be equally capable of outputting "do not buy the battery" and must surface break-even conditions, not just best-case payback. No recommendation without its failure conditions. This is the structural difference from installer tools, whose economics reward a "yes."
3. **Uncertainty is a first-class output.** Point estimates are how competitors lie by accident. Payback and savings figures ship as distributions (Monte Carlo over rate escalation, solar degradation, load drift), reported as ranges with stated assumptions. This is the mathematical depth competitors don't have.
4. **SDG&E-territory correctness others fumble.** Model the CCA layer explicitly: San Diego Community Power generation rates layered on SDG&E delivery. Model non-bypassable charges and the resulting bill floor (~2.5¢/kWh on imports). Generic calculators skip both; we treat them as core.
5. **Vintage-aware NEM 3.0 modeling.** ACC export rates lock for 9 years by PTO vintage year. "When to install" is a product question no consumer tool answers; ours does.
6. **Real interval data, never modeled load profiles.** If a computation could be done from a synthetic profile, it isn't our differentiator. Everything routes through the customer's actual 15-minute data.

When implementing anything, if a generic/standard approach and a differentiating approach both exist, flag the tradeoff instead of silently choosing the generic one.

## Architecture

```
src/
  greenbutton/     # parsers: PG&E and SDG&E Green Button CSV/XML -> canonical interval series
  tariffs/         # tariff engine: pure functions (interval series + tariff spec) -> itemized bill
  tariffs/specs/   # versioned tariff data files (YAML), one per schedule per effective date
  nem3/            # ACC export tables, vintage lock-in logic, netting rules, NBCs
  scenarios/       # rate switch, solar (PVWatts), battery dispatch (cvxpy), EV load shift
  uncertainty/     # Monte Carlo wrappers over scenarios
  report/          # report generation (later milestone)
tests/
  golden_bills/    # anonymized real-bill fixtures; the reconciliation gate lives here
data/              # gitignored; raw Green Button exports live here locally, never committed
```

Principles:
- The tariff engine is a pure function of (interval data, tariff spec, billing period). No I/O, no network, deterministic. All utility-specific mess lives in the spec files and parsers.
- Tariff specs are data, not code: YAML with effective-date versioning and a citation field pointing at the exact utility tariff sheet (URL + revision) each number came from. A spec without a citation is invalid.
- Never fabricate a rate, threshold, or rule. If a tariff detail is unknown, mark it `UNVERIFIED` in the spec and raise at load time rather than guessing.
- Never scrape utility login portals. Data enters via user-supplied files only (Bayou Energy API is a future paid rail, out of scope now).

## Data sources (all free)

- Customer usage: Green Button "Download My Data" CSV (SDG&E: 15-min, up to 13 months; PG&E similar).
- Tariff structures: NREL/NLR Utility Rate Database (URDB) as a starting reference — but CA IOU rates change mid-year, so current SDG&E/PG&E residential schedules are hand-maintained in `tariffs/specs/` from the utilities' published tariff sheets, each with citation and effective date.
- NEM 3.0 export values: CPUC Avoided Cost Calculator tables (576 rates/year: 12 months x 24 hours x weekday/weekend), per vintage year. PG&E publishes full export-credit CSVs.
- Solar production: PVWatts API (free NREL/NLR developer key) for hourly production estimates by location/tilt/azimuth.

## Conventions

- Environment: conda, env name `energy-advisor` (see environment.yml). Python 3.12.
- Tests: pytest; golden-bill reconciliation tests are the merge gate for anything in `tariffs/` or `nem3/`. Target ±$2/month vs. actual bills.
- Lint/format: ruff.
- Types: pydantic models at module boundaries (interval series, tariff spec, bill).
- Privacy: real Green Button exports and real bills never enter git. `data/` and `tests/golden_bills/raw/` are gitignored; committed fixtures are anonymized (no names, account numbers, or addresses; dates may be shifted).
- Battery dispatch: start with a greedy TOU-arbitrage heuristic for interpretability, then LP-optimal via cvxpy; always report both so users see the gap between realistic controller behavior and theoretical optimum.

## Current focus

See ROADMAP.md. Work only on the current milestone; do not build ahead (no web UI, no payment, no Bayou integration until their milestone).

## Working style

- Terse, technically precise. No filler praise.
- When a modeling decision has material dollar impact on outputs (netting order, true-up handling, baseline allowances), stop and surface it as a decision point with the options and their consequences rather than picking silently.
- Prefer small verifiable increments: each PR-sized change should move a reconciliation number or add a tested capability.
