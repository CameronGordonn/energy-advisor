# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it short and
current: state, how to run, open decisions, exact next action._

## Status: **M0 done. M2 done on PG&E. M3 engine complete + SDG&E now real end-to-end. M1 blocked on data.**
_(2026-09-07, session 6)_

> **Session 6 closed the last open SDG&E blocker and made SDG&E dollar figures real.**
> 166 tests green (was 133), ruff clean, **11/11 PG&E golden bills still reconcile**
> (worst +$0.22, byte-identical output — all of this session's work is additive).
> Full detail in SESSION_NOTES §2026-09-07 Session 6 — do not re-derive.
>
> 1. **Open decision 1 (super-off-peak window) is RESOLVED.** The two SDG&E sources did not
>    conflict — the tariff changed. SDG&E extended weekday 10:00-14:00 super-off-peak from
>    Mar/Apr-only to **year-round effective 2026-05-01**. The specs were already right.
>    Caveat kept: the advice letter / revised P.U.C. sheet were not located; evidence is
>    SDG&E's own customer-facing publications. Pre-2026-05-01 vintages need `months: [3,4]`.
> 2. **SDG&E bundled generation (Schedule EECC) is authored** — the missing half. Delivery +
>    generation rebuild SDG&E's printed Total Electric Rate *and* Total Adjusted CARE Rate on
>    all twelve cells (`tests/tariffs/test_sdge_layers.py`).
> 3. **NBC blocks added to TOU-DR2 and EV-TOU-5**, verified against their own tables.
> 4. **`marginal_energy_price` replaces a hand-typed price vector** in the M3 report.
>
> **Three findings worth keeping.** (a) On TOU-DR1 the UDC total is period-flat, so **100% of
> the TOU price signal lives in the generation layer** — the delivery-as-generation stand-in
> was producing a flat signal. (b) **EV-TOU-5's super-off-peak is ~45% non-bypassable**
> (vs ~6.5% in other windows), because it discounts distribution but not NBCs — a calculator
> netting against the headline rate overstates super-off-peak import shifting by ~2x.
> (c) The old typed vector priced super-off-peak at 0.22 where the real total is **0.37660**
> — a 71% understatement, biased toward buying the battery.
>
> Carried from session 5: SDG&E's NBT2025/NBT2026/current export tables are **byte-identical**,
> so the nine-year lock-in confers **no** dollar advantage on SDG&E (opposite the PG&E pitch);
> and under full NBT settlement the LP dispatch can settle **worse** than greedy.

> **⚠ CONTEXT: the Santa Cruz lease ended 2026-07-31** and the last export in `data/` runs to
> 2026-07-18. If the PG&E account is closed, the final statement and any post-move interval
> data are probably unreachable now. The 11 committed golden bills are unaffected.
> Cameron has **no plug-in EV**, so EV2-A/EV-TOU-5 plans are filtered out of rankings by default.

## What exists now
- **Engine**: N-period first-match-wins TOU rules with weekday/weekend/holiday day types,
  month-conditional windows, cited holiday calendars, `Baseline.allowance_multiplier`,
  `MinimumBill`, per-kWh surcharges, `NonBypassable`. Plus `period_codes` and
  **`marginal_energy_price`** (version-aware per-interval retail price; refuses dates no
  spec covers; rejects layers that classify an hour differently).
- **Specs (21 files, 13 schedule-layers)**: PG&E E-TOU-C (4 vintages) / E-TOU-D / EV2-A / E-1
  delivery, each with matched 3CE and PG&E-bundled generation; **SDG&E TOU-DR1 delivery +
  generation (EECC)**, TOU-DR2, EV-TOU-5, TOU-DR-P (deliberately unloadable). Every SDG&E
  delivery spec now carries a `non_bypassable` block.
- **M2 optimizer**: `scripts/rate_optimizer.py` — ranking, verdict, component-level *why*,
  sensitivity, assumption audit.
- **M3 NEM 3.0 engine** (`src/nem3/`): `acc.py` (real SDG&E vintage export tables NBT25/26/
  current, 576/yr, 9-yr PTO lock-in), `netting.py` (NBT settlement, NBC import floor, ACC
  Plus, honest caveat notes), `solar.py`, `pvwatts.py` (real client + never-fabricate guard),
  `battery.py` (greedy + cvxpy LP, both always returned), `payback.py`;
  `uncertainty/montecarlo.py`. Driver: `scripts/nem3_report.py`.

## How to run
```bash
conda activate energy-advisor    # env prefix: /home/cameron/miniforge3/envs/energy-advisor
pytest -q                                                   # 166 tests; golden tests skip if data/ absent
                                                            # (pyproject sets pythonpath=src; scripts still need it)
ruff check . && ruff format --check .
PYTHONPATH=src python scripts/reconcile_report.py           # 11 line-item comparisons (the trust artifact)
PYTHONPATH=src python scripts/reconcile_report.py --write-readme
PYTHONPATH=src python scripts/rate_optimizer.py             # M2 ranking + sensitivity + assumption audit
PYTHONPATH=src python scripts/nem3_report.py                # M3 solar+battery (REAL SDG&E rates, synthetic load)
PYTHONPATH=src python scripts/build_acc_tables.py --utility 'SDG&E' --vintage 2026 --source FILE.csv --citation '...'
```

## M2 headline (PG&E household, 4345 kWh / 328 days) — unchanged
**SWITCH to E-TOU-C + PG&E bundled generation — $170.72/yr cheaper than today.** The saving
is **leaving the CCA, not changing schedule** (PCIA +$159.88/yr, UUT on it +$13.59, franchise
fee +$2.54, while 3CE generation is only ~$5/yr cheaper). A 2018-vintage CCA customer pays
PCIA 0.03679/kWh where the 2026 *bundled* PCIA is −0.01011. Moot for Cameron (lease ended),
but the strongest validation of the method so far and a good M4 case study. Caveat printed
in the report: PG&E Rules 22.1/23.1 require six months' notice to elect bundled service,
with Schedule TBCC in between — the saving is not immediate and the TBS window is unpriced.

## M3 demo output (bundled SDG&E TOU-DR1, coastal_basic, synthetic 6,264 kWh load, 5 kW)
Window **2026-06-01 .. 2027-05-31** (see open item 1). Dollar totals are now REAL for a
bundled SDG&E household; only the LOAD is synthetic.
```
No solar (baseline)                        3,022
Solar only                                 1,855   save 1,168   9.0 yr
Solar + battery (greedy TOU controller)      505   save 2,518   7.5 yr
Solar + battery (LP marginal optimum)        427   save 2,595   7.3 yr
Non-bypassable import floor: $86/yr on gross imports.
```

## EXACT NEXT ACTION

M3's **DoD** ("one *real* household payback distribution + vintage-timing") is still **data-
gated, not code-gated** — no household has solar/export interval data. Do NOT fabricate a
load to "finish" it. Everything below is code-only and unblocked:

1. **Transcribe SDG&E's earlier 2026 rate vintages** (1/1/2026 and 4/1/2026 Total Rates
   Tables, delivery + generation), with **`months: [3, 4]` on the weekday 10:00-14:00
   super-off-peak rule** for any vintage before 2026-05-01. This restores a calendar-year
   SDG&E run and exercises the version-switching path end to end. Smallest well-defined unit
   of work here.
2. **CCA generation overlay** — a CCA's own generation rate + the vintaged PCIA, replacing
   EECC. The PCIA vintage table is already recorded in the generation spec header. Blocked
   only on *which* CCA (San Diego Community Power vs Clean Energy Alliance).
3. **Confirm SDG&E ACC Plus** from an SDG&E NBT sheet (a blog claims SDG&E residential get
   none). `acc.acc_plus_table` raises for SDG&E; `acc_plus_eligible=False` is conservative.
4. **PG&E ACC tables** — PG&E publishes per-vintage PDFs (pge.com/energyexportcredit), not
   the MIDAS CSVs SDG&E uses; needs a different parser. Low priority.
5. **TOU-DR-P** — needs an events model before it can be ranked (open decision 2).

Or shift to **M4** (public methodology writeup + case study). It is explicitly the
portfolio-justifying milestone, and the material is now strong: the M2 CCA-vs-bundled
finding, the NBT/lock-in findings, the EV-TOU-5 non-bypassable finding, and a reconciliation
table at ±$0.22 worst case. **This is the recommended next move if no new data arrives.**

## Open decisions
1. **SDG&E TOU-DR1 super-off-peak window — RESOLVED 2026-09-07.** Year-round, effective
   2026-05-01 (see the session-6 note above and the in-spec citation). Residual caveat: the
   superseding advice letter / revised P.U.C. sheet were not located.
2. **TOU-DR-P is deliberately unloadable.** Period windows unsourced, and the **RYU Event
   Adder ($1.16/kWh, 4-9 p.m. on event days)** is event-contingent with no engine concept.
   Do **not** default it to zero events — that would make the plan look like a free lunch.
   Preferred: caller-supplied event days, or report as a range, or exclude and say why.
3. **SDG&E baseline allowances — RESOLVED.** Full climate-zone table (Sheet 29294-E) ships
   in-spec; `territory` is supplied **at bill time** because the zone is a customer fact.
   Omitting it raises rather than defaulting.
4. **CARE rates on PG&E counterfactual schedules are DERIVED, not printed**
   (`care = 0.65 x standard - 0.01038`). Validated to ≤1e-5 on E-TOU-C, cross-checked
   against E-1's printed tier pair. `--no-care` is the tariff-only ranking.
   *(Note: the SDG&E CARE split is now proven exactly — see `test_sdge_layers.py` — which is
   independent corroboration that the 35%-discount modeling is right in kind.)*
5. **Santa Cruz UUT Adjustment — RESOLVED as a modeling assumption**, mechanism still
   UNVERIFIED. Adopted **$0.21649/day**. Schedule-independent, so it cannot reorder the
   ranking, and the optimizer re-ranks under all three mechanisms to prove it.
6. **Which CCA and which SDG&E schedule dad is on** — still unresolvable without a bill.

## Blocked on data (not on work)
- **M1 DoD** (dad's last 3 SDG&E bills within ±$2) and the README SDG&E rows. Dad's data is
  unavailable indefinitely: no bills, no Green Button export, no portal login. Do not plan
  around it arriving.
- **M3 DoD** needs one real household with solar/export interval data. Same situation.
- Validation of `src/greenbutton/sdge.py` against a real SDG&E export.

## Flagged approximations still open (all sub-$0.05, non-blocking)
- **2025 franchise fee**: 2026 specs use the exact E-FFS per-kWh rate ($0.00059); the
  2025-vintage specs still carry the old percent-of-energy approximation.
- **2025 summer generation credit** is still bill-fitted (the 2026 one is tariff-exact).
- **California Climate Credit** modeled as an observed per-bill line (−$58.23 on 10/28).
  PG&E files **$(36.18), Aug/Sep cycles**; SDG&E files **$(33.50) semi-annual** per Schedule
  GHG-ARR. Generalise to a versioned semiannual credit and reconcile against the observed.
- **California Energy Commission surcharge on SDG&E**: the PG&E specs carry $0.0003/kWh;
  SDG&E's Total Rates Table shows no such column, so it is deliberately NOT asserted either
  way on the SDG&E specs (adding it unsourced would break the layer-identity test). If a
  real SDG&E statement shows it as a line, add it with that citation.

## M3 open items (recorded, none blocking)
- **SDG&E ACC Plus unconfirmed** — `acc.acc_plus_table` raises for SDG&E; settle with
  `acc_plus_eligible=False`.
- **PG&E ACC tables not imported** — PG&E ships per-vintage PDFs, not MIDAS CSVs.
- **LP dispatch is a marginal-price optimum, not a settled-dollar optimum** — under NBT caps
  it can settle below greedy. Documented and reported honestly, not a bug.
- **CCA export terms** — the netting model excludes the CCA generation credit by default
  (Schedule NBT SC 2.a), so a CCA customer's result is a lower bound until supplied.

## Schema gaps (recorded, none blocking today)
- `PerKwhAdder` has no CARE variant (worked around on SDG&E by folding WF-NBC/DWR-BC into
  the energy `Rate`).
- **FERA / DRAH** (0.39688/day on both IOUs) unmodelable — `Rate` has only `standard`/`care`.
- No `tiers` concept. Correct for E-1 today (exact identity via the baseline credit);
  required if a third distinct tier price appears.

Do **not** build CLI/API/Docker/deployment/web UI — roadmap "Later", gated behind M5.
