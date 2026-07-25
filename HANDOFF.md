# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it short and
current: state, how to run, open decisions, exact next action._

## Status: **M0 done. M2 done on PG&E (cross-check unavailable). M3 ENGINE complete + tested; M3 DoD data-gated. M1 blocked on data.**
_(2026-07-25, session 5)_

> **Session 5 built the entire NEM 3.0 engine (M3 groundwork, all four HANDOFF items).**
> 133 tests green (was 96), ruff clean, **11/11 PG&E golden bills still reconcile** (the M3
> work is additive to the engine). New package `src/nem3/`: `acc.py` (real SDG&E vintage
> export tables + 9-yr PTO lock-in), `netting.py` (NBT settlement + NBC import floor),
> `solar.py`, `pvwatts.py`, `battery.py` (greedy + cvxpy LP), `payback.py`;
> `uncertainty/montecarlo.py`. Driver: `scripts/nem3_report.py`. Full detail in
> SESSION_NOTES §2026-07-25 Session 5 — do not re-derive.
>
> **Two real findings worth keeping:** (1) SDG&E's published NBT2025/NBT2026/current export
> tables are **byte-identical**, so the nine-year lock-in confers **no** dollar advantage on
> SDG&E today (opposite the PG&E pitch). (2) Under the full NBT settlement the LP battery
> dispatch can settle **worse** than the greedy controller, because the LP optimizes a
> marginal-price proxy while dollars come from the settlement's credit caps + NBC floor.

> **⚠ CONTEXT CHANGE: the Santa Cruz lease ends 2026-07-31.** Before the account closes,
> export the full Green Button interval data and every remaining bill PDF (including the
> final statement, which arrives after move-out). Portal access usually dies with the
> account and this household's 12 months of data is the project's entire trust artifact.
> Cameron has **no plug-in EV**, so EV2-A plans are filtered out of rankings by default.

The bill engine reproduces **all 11 PG&E statements within ±$2**, worst residual
**+$0.22**, from the customer's own hourly interval data (CCA/3CE + CARE account).
**96 tests green, ruff clean.** See the README reconciliation table.

Session 4 landed the **N-period, day-type-aware TOU engine** (the blocker for everything),
opened **M2 on the PG&E household**, and authored the **SDG&E delivery specs**. Full detail
in SESSION_NOTES §2026-07-23 Session 4 — do not re-derive any of it.

## What exists now
- **Engine**: N-period first-match-wins TOU rules with weekday/weekend/holiday day types,
  month-conditional windows, cited holiday calendars, `Baseline.allowance_multiplier`,
  `MinimumBill`, per-kWh surcharges. Backward compatible: every PG&E spec was untouched
  and the reconciliation output was **byte-identical** across the refactor.
- **Specs (12 → 23)**: PG&E E-TOU-C / **E-TOU-D / EV2-A / E-1** delivery + matched
  **3CE generation** for each; **SDG&E TOU-DR1 / TOU-DR2 / EV-TOU-5 / TOU-DR-P** delivery.
- **M2 optimizer**: `scripts/rate_optimizer.py`, one command → ranking, verdict, a
  component-level *why*, sensitivity, and an assumption audit.
- **M3 NEM 3.0 engine** (`src/nem3/`): `acc.py` (real committed SDG&E vintage export tables
  NBT25/26/current, 576/yr, 9-yr PTO lock-in), `netting.py` (NBT "no-netting" settlement,
  per-component export credits, NBC import floor, ACC Plus, honest caveat notes), `solar.py`
  (behind-the-meter import/export split), `pvwatts.py` (real NREL client + cache +
  never-fabricate guard), `battery.py` (greedy TOU + cvxpy LP, both always returned),
  `payback.py` (scenario ranking + vintage-timing). `uncertainty/montecarlo.py` (payback
  distribution). Driver: `scripts/nem3_report.py`. Table importer: `scripts/build_acc_tables.py`.

## How to run
```bash
conda activate energy-advisor    # env prefix: /home/cameron/miniforge3/envs/energy-advisor
PYTHONPATH=src python -m pytest -q                          # 133 tests; golden tests skip if data/ absent
ruff check . && ruff format --check .
PYTHONPATH=src python scripts/reconcile_report.py           # 11 line-item comparisons (the trust artifact)
PYTHONPATH=src python scripts/reconcile_report.py --write-readme
PYTHONPATH=src python scripts/rate_optimizer.py             # M2 ranking + sensitivity + assumption audit
PYTHONPATH=src python scripts/nem3_report.py                # M3 solar+battery report (synthetic load, real ACC/tariff)
# Re-import an ACC export table from a utility's MIDAS file (SDG&E already committed):
PYTHONPATH=src python scripts/build_acc_tables.py --utility 'SDG&E' --vintage 2026 --source FILE.csv --citation '...'
```

## M2 headline (PG&E household, 4345 kWh / 328 days, current rates)
**SWITCH to E-TOU-C + PG&E bundled generation — $170.72/yr cheaper than today.**
```
E-TOU-C + PG&E   933.50   <- best eligible
E-1     + PG&E   990.57
E-TOU-D + PG&E  1038.50
E-TOU-C + 3CE   1104.22   <- current
E-1     + 3CE   1160.91
E-TOU-D + 3CE   1208.80
```
The saving is **leaving the CCA, not changing schedule**: PCIA +$159.88/yr, UUT on it
+$13.59, franchise fee +$2.54, while 3CE's generation is only ~$5/yr cheaper than PG&E's. A
2018-vintage CCA customer pays PCIA 0.03679/kWh where the 2026 *bundled* PCIA is −0.01011 —
a ~4.7c/kWh gap 3CE's discount no longer covers. **Moot for Cameron (lease ends 07-31), but
it is the strongest validation of the method so far, and a good M4 case study.**
Among schedules alone the driver is the **baseline credit** (E-TOU-C and E-1 have one;
E-TOU-D and EV2-A do not), not peak/off-peak spreads.
**Caveat printed in the report:** PG&E Rules 22.1/23.1 require six months' advance notice to
elect bundled service, with Transitional Bundled Service (Schedule TBCC, short-term market
prices) in between — the saving is not immediate and the TBS window is unpriced.

## EXACT NEXT ACTION

**M3 groundwork is DONE** (all four items: ACC vintage tables + 9-yr lock-in; NBT netting vs
the NBC floor; PVWatts client; greedy + LP battery dispatch — plus payback + Monte Carlo).
133 tests, gate green. What remains for M3 to hit its **DoD** ("one real household payback
distribution + vintage-timing") is **data, not code** — and no household has solar/export
data, so it is gated exactly like M1. Do NOT fabricate a load to "finish" it.

Pick from these, all unblocked and code-only (no new bills needed):

1. **SDG&E generation layer (EECC) — highest value.** The `nem3_report.py` demo currently
   reuses the delivery spec as a stand-in for generation, so its DOLLAR totals are
   illustrative even though the structure (netting, NBC floor, lock-in) is exact. EECC
   values are already recorded in each SDG&E delivery spec's comments (summer on 0.34920 /
   off 0.12853 / super-off 0.04121; winter on 0.27475 / off 0.19304 / super-off 0.10228).
   Authoring `sdge_tou_dr1_generation` (bundled EECC) makes SDG&E bundled bills — and the M3
   dollar figures — real end to end. Then the CCA overlay (San Diego Community Power /
   Clean Energy Alliance generation + vintaged PCIA) once which CCA is known.
2. **Resolve the TOU-DR1 super-off-peak conflict** (open decision 1). Blocks every SDG&E
   dollar figure regardless of the above.
3. **NBC blocks on the other SDG&E specs** (TOU-DR2, EV-TOU-5) — TOU-DR1 has one; copy the
   pattern so any SDG&E schedule can be settled under NBT.
4. **Confirm SDG&E ACC Plus** from an SDG&E NBT sheet (a blog claims SDG&E residential get
   none). Until then `acc.acc_plus_table` raises for SDG&E and the conservative path is
   `acc_plus_eligible=False`; the engine is correct either way.
5. **PG&E ACC tables** if a PG&E solar case ever matters: PG&E publishes per-vintage PDFs
   (pge.com/energyexportcredit), not the MIDAS CSVs SDG&E uses — needs a different parser.
   Low priority (Cameron's PG&E account is closing).

Or shift to **M4** (public methodology writeup + case study) — the M2 CCA-vs-bundled finding
and now the M3 NBT/lock-in findings are strong material and M4 is explicitly the
portfolio-justifying milestone.

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
3. **SDG&E baseline allowances — RESOLVED.** The full climate-zone table (Cal. P.U.C. Sheet
   29294-E) now ships in-spec, and `territory` is supplied **at bill time** because the zone
   is a customer fact; omitting it raises rather than defaulting. TOU-DR1 and TOU-DR2 load.
4. **CARE rates on PG&E counterfactual schedules are DERIVED, not printed**
   (`care = 0.65 x standard - 0.01038`). Validated to ≤1e-5 on E-TOU-C, cross-checked
   against E-1's printed tier pair, and corroborated by SDG&E's tables printing "CARE
   Discount 35%". Still an assumption; `--no-care` is the tariff-only ranking.
5. **Santa Cruz UUT Adjustment — RESOLVED as a modeling assumption**, mechanism still
   UNVERIFIED. Adopted **$0.21649/day** (best fit of five candidates). It is
   schedule-independent, so it cannot reorder the ranking, and the optimizer proves that by
   re-ranking under all three mechanisms. No longer blocks anything.
6. **Which CCA and which SDG&E schedule dad is on** — still unresolvable without a bill.
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

## M3 open items (recorded, none blocking; see EXACT NEXT ACTION)
- **SDG&E ACC Plus unconfirmed** — a secondary source claims SDG&E residential customers get
  no ACC Plus adder. `acc.acc_plus_table` raises for SDG&E; settle with `acc_plus_eligible=
  False` (conservative). Confirm from an SDG&E NBT sheet.
- **SDG&E generation (EECC) layer un-authored** — the M3 demo reuses delivery as a
  generation stand-in, so its dollar TOTALS are illustrative (structure is exact). Values
  are in each SDG&E delivery spec's comments; see next-action #1.
- **PG&E ACC tables not imported** — PG&E ships per-vintage PDFs, not MIDAS CSVs.
- **LP dispatch is a marginal-price optimum, not a settled-dollar optimum** — under NBT caps
  it can settle below greedy. This is documented and reported honestly, not a bug.

## Schema gaps (recorded, none blocking today)
- `PerKwhAdder` has no CARE variant, so a per-kWh line CARE customers are exempt from can't
  be an adder (worked around on SDG&E by folding WF-NBC/DWR-BC into the energy `Rate`).
- **FERA / DRAH** (0.39688/day on both IOUs) unmodelable — `Rate` has only `standard`/`care`.
- No `tiers` concept. Correct for E-1 today (the two-tier case is an exact identity via the
  baseline credit — see SESSION_NOTES); required if a third distinct tier price appears.

Do **not** build CLI/API/Docker/deployment/web UI — roadmap "Later", gated behind M5.
