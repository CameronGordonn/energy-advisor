# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it short and
current: state, how to run, open decisions, exact next action._

## Status: **M0 complete. M2 substantially complete on PG&E. M1 blocked on data only.**
_(2026-07-23, session 4)_

The bill engine reproduces **all 11 PG&E statements within ±$2**, worst residual
**+$0.22**, from the customer's own hourly interval data (CCA/3CE + CARE account).
**91 tests green, ruff clean.** See the README reconciliation table.

Session 4 landed the **N-period, day-type-aware TOU engine** (the blocker for everything),
opened **M2 on the PG&E household**, and authored the **SDG&E delivery specs**. Full detail
in SESSION_NOTES §2026-07-23 Session 4 — do not re-derive any of it.

## What exists now
- **Engine**: N-period first-match-wins TOU rules with weekday/weekend/holiday day types,
  month-conditional windows, cited holiday calendars, `Baseline.allowance_multiplier`,
  `MinimumBill`, per-kWh surcharges. Backward compatible: every PG&E spec was untouched
  and the reconciliation output was **byte-identical** across the refactor.
- **Specs (12 → 19)**: PG&E E-TOU-C / **E-TOU-D / EV2-A / E-1** delivery + matched
  **3CE generation** for each; **SDG&E TOU-DR1 / TOU-DR2 / EV-TOU-5 / TOU-DR-P** delivery.
- **M2 optimizer**: `scripts/rate_optimizer.py`, one command → ranking, verdict, a
  component-level *why*, sensitivity, and an assumption audit.

## How to run
```bash
conda activate energy-advisor    # env prefix: /home/cameron/miniforge3/envs/energy-advisor
PYTHONPATH=src python -m pytest -q                          # 91 tests; golden tests skip if data/ absent
ruff check . && ruff format --check .
PYTHONPATH=src python scripts/reconcile_report.py           # 11 line-item comparisons (the trust artifact)
PYTHONPATH=src python scripts/reconcile_report.py --write-readme
PYTHONPATH=src python scripts/rate_optimizer.py             # M2 ranking + sensitivity + assumption audit
PYTHONPATH=src python scripts/rate_optimizer.py --no-care    # fully tariff-grounded (no derived CARE rates)
```

## M2 headline (PG&E household, 4345 kWh / 328 days, current rates)
**STAY on E-TOU-C + 3CE.** `E-TOU-C 1104.22 < EV2-A 1130.52 (conditional, needs an EV)
< E-1 1160.91 < E-TOU-D 1208.80`. The gap is driven by the **baseline credit** (E-TOU-C and
E-1 have one; E-TOU-D and EV2-A do not), *not* by peak/off-peak spreads. E-1 overtakes only
if 4-9 p.m. usage grows ~358%; E-TOU-D never overtakes on a load-neutral shift.

## EXACT NEXT ACTION — close the M2 definition of done

The only remaining piece of M2 is the cross-check against **PG&E's own rate comparison**,
and it needs Cameron, not code:

1. Sign in at pge.com → **Rate Plan Comparison** (pge.com/rateanalysis-pge). It is login-
   gated, so it cannot be fetched; the account holder must run it.
2. Save its output as YAML:
   ```yaml
   source: PG&E Rate Plan Comparison, run 2026-07-XX
   plans: {E-TOU-C: 1104.22, E-1: 1160.91, E-TOU-D: 1208.80, EV2-A: 1130.52}
   ```
3. `PYTHONPATH=src python scripts/rate_optimizer.py --pge-comparison FILE`

Expect a **level** difference and do not treat it as an error: PG&E's tool prices *bundled*
service while this household buys generation from 3CE. **The ranking and the spreads are
what must agree.** The script already prints all of this plus the cross-checks that are
complete.

### If that is blocked, the next most valuable work, in order
1. **Fill the SDG&E baseline allowances.** TOU-DR1 / TOU-DR2 / TOU-DR-P currently raise at
   load because `baseline.territory` and the allowances are UNVERIFIED. SDG&E publishes
   them per **climate zone** (Coastal / Inland / Mountain / Desert) x Basic vs All-Electric.
   Authoring one spec per zone, or adding a zone-keyed allowance table to `Baseline`, makes
   three schedules billable. This is the single highest-leverage unblocked task.
2. **Resolve the TOU-DR1 super-off-peak conflict** (see open decisions).
3. **PG&E bundled-generation specs.** Cheap — the EECC/generation numbers are already in
   each delivery spec's unbundling comments — and it adds the "leave 3CE?" counterfactual,
   which is currently absent from the ranking and stated as such in the report.
4. **M3 groundwork** (NEM 3.0): the SDG&E NBC set is modeled and the import floor is
   documented at **0.02099/kWh** plus PCIA; the netting logic is what's missing.

## Open decisions
1. **⚠ SDG&E TOU-DR1 super-off-peak window — two SDG&E sources disagree.** The tariff-book
   sheet (Advice 3167-E, last revised **2018**) restricts weekday super-off-peak 10:00-14:00
   to **March and April**; SDG&E's current pricing page (pricing effective 6/1/2026, the
   same vintage as the rate tables used) shows it **year-round**. Specs follow the current
   page and flag it. **Material for ten months of the year — confirm from a current tariff
   sheet before any SDG&E dollar figure ships.**
2. **TOU-DR-P is deliberately unloadable.** Period windows unsourced, and the **RYU Event
   Adder ($1.16/kWh, 4-9 p.m. on event days)** is event-contingent with no engine concept.
   Do **not** default it to zero events — that would make the plan look like a free lunch.
   Preferred: caller-supplied event days, or report as a range, or exclude and say why.
3. **CARE rates on PG&E counterfactual schedules are DERIVED, not printed**
   (`care = 0.65 x standard - 0.01038`). Validated to ≤1e-5 on E-TOU-C, cross-checked
   against E-1's printed tier pair, and corroborated by SDG&E's tables printing "CARE
   Discount 35%". Still an assumption; `--no-care` is the tariff-only ranking.
4. **Santa Cruz UUT Adjustment — RESOLVED as a modeling assumption**, mechanism still
   UNVERIFIED. Adopted **$0.21649/day** (best fit of five candidates). It is
   schedule-independent, so it cannot reorder the ranking, and the optimizer proves that by
   re-ranking under all three mechanisms. No longer blocks anything.
5. **Which CCA and which SDG&E schedule dad is on** — still unresolvable without a bill.
   The San Diego CCA generation overlay remains deliberately un-authored.

## Blocked on data (not on work)
- **M1 DoD** (dad's last 3 SDG&E bills within ±$2) and the README SDG&E rows. Dad's data is
  unavailable indefinitely: no bills, no Green Button export, no portal login. Do not plan
  around it arriving.
- Validation of `src/greenbutton/sdge.py` against a real SDG&E export.

## Flagged approximations still open (all sub-$0.05, non-blocking)
- **2025 franchise fee**: the 2026 specs now use the exact E-FFS per-kWh rate ($0.00059);
  the 2025-vintage specs still carry the old percent-of-energy approximation. Fix by
  pulling the superseded E-FFS sheet (59112-E) if it ever matters.
- **2025 summer generation credit** is still bill-fitted (the 2026 one is now tariff-exact);
  the superseded unbundling sheets would make it exact.
- **California Climate Credit** modeled as an observed per-bill line (−$58.23 on 10/28).
  PG&E files **$(36.18), Aug/Sep bill cycles** on every 2026 residential sheet — generalise
  to a versioned semiannual credit and reconcile against the observed figure.

## Schema gaps (recorded, none blocking today)
- `PerKwhAdder` has no CARE variant, so a per-kWh line CARE customers are exempt from can't
  be an adder (worked around on SDG&E by folding WF-NBC/DWR-BC into the energy `Rate`).
- **FERA / DRAH** (0.39688/day on both IOUs) unmodelable — `Rate` has only `standard`/`care`.
- No `tiers` concept. Correct for E-1 today (the two-tier case is an exact identity via the
  baseline credit — see SESSION_NOTES); required if a third distinct tier price appears.

Do **not** build CLI/API/Docker/deployment/web UI — roadmap "Later", gated behind M5.
