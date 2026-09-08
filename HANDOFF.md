# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it short and
current: state, how to run, open decisions, exact next action._

## Status: **M0, M2, M4 done. M1 and M3 have complete engines, DoDs blocked on data.**
_(2026-09-07, session 7)_

> **Session 7 shipped M4 — the public methodology writeup and case study.** (commit `b0df750`)
> 166 tests green, ruff clean, **11/11 PG&E golden bills still reconcile** (worst +$0.22).
> Nothing this session touched `tariffs/` or `nem3/`; the change is docs, README, ROADMAP
> and a privacy scrub. Full detail in SESSION_NOTES §Session 7 — do not re-derive.
>
> - **`docs/METHODOLOGY.md`** (six sections) and **`docs/index.html`** (the same material as a
>   standalone static page with a residual chart) are the deliverables. README leads with the
>   reconciliation table and links both; its M4 row is marked done.
> - **The case study is SELF-ATTRIBUTED by decision, not anonymized.** Cameron chose to keep
>   CARE visible and to scrub-then-publish the session logs. ROADMAP's M4 line was amended
>   from "anonymized" to "honest" with the rationale inline so the DoD does not contradict
>   what shipped. Scrubbed from all committed docs: unit number, CARE renewal date, tenancy
>   dates, the duplicate raw statement-total list. Kept: city, schedule, exact dates and
>   amounts, the whole reasoning trail.
> - **No M3 payback figure appears in the writeup** — those numbers run on a synthetic load,
>   and publishing them would contradict invariant 6. M3 is presented as engine + structural
>   findings, with the data gate stated.
> - **New observation, worth keeping:** the reconciliation residual is **one-sided** — all
>   eleven errors positive, mean +$0.14, +0.14% across $1,084.26. Explained (0.3 kWh
>   meter-read boundary + the 2025 franchise-fee approximation). It is the answer to "how do
>   you know you didn't curve-fit this?", and stating it first is stronger than being caught.

> **⚠ CONTEXT: the Santa Cruz PG&E service ended in July 2026** and the last export in `data/`
> runs to 2026-07-18. The final statement and any post-move interval data are probably
> unreachable. The 11 committed golden bills are unaffected. Cameron has **no plug-in EV**, so
> EV2-A/EV-TOU-5 plans are filtered out of rankings by default.

## What exists now
- **Engine**: N-period first-match-wins TOU rules with weekday/weekend/holiday day types,
  month-conditional windows, cited holiday calendars, `Baseline.allowance_multiplier`,
  `MinimumBill`, per-kWh surcharges, `NonBypassable`, `period_codes`, and
  **`marginal_energy_price`** (version-aware per-interval retail price; refuses dates no spec
  covers; rejects layers that classify an hour differently).
- **Specs (21 files, 13 schedule-layers)**: PG&E E-TOU-C (4 vintages) / E-TOU-D / EV2-A / E-1
  delivery, each with matched 3CE and PG&E-bundled generation; SDG&E TOU-DR1 delivery +
  generation (EECC), TOU-DR2, EV-TOU-5, TOU-DR-P (deliberately unloadable). Every SDG&E
  delivery spec carries a `non_bypassable` block.
- **M2 optimizer**: `scripts/rate_optimizer.py` — ranking, verdict, component-level *why*,
  sensitivity, assumption audit.
- **M3 NEM 3.0 engine** (`src/nem3/`): `acc.py`, `netting.py`, `solar.py`, `pvwatts.py`,
  `battery.py` (greedy + cvxpy LP, both always returned), `payback.py`;
  `uncertainty/montecarlo.py`. Driver: `scripts/nem3_report.py`.
- **M4 writeup**: `docs/METHODOLOGY.md` + `docs/index.html`.

## How to run
```bash
conda activate energy-advisor    # env prefix: /home/cameron/miniforge3/envs/energy-advisor
pytest -q                                                   # 166 tests; golden tests skip if data/ absent
ruff check . && ruff format --check .
PYTHONPATH=src python scripts/reconcile_report.py           # 11 line-item comparisons (the trust artifact)
PYTHONPATH=src python scripts/reconcile_report.py --write-readme
PYTHONPATH=src python scripts/rate_optimizer.py             # M2 ranking + sensitivity + assumption audit
PYTHONPATH=src python scripts/nem3_report.py                # M3 solar+battery (REAL SDG&E rates, synthetic load)
PYTHONPATH=src python scripts/build_acc_tables.py --utility 'SDG&E' --vintage 2026 --source FILE.csv --citation '...'
```

## Headline results (unchanged; both are in the writeup)
**M0/M4 reconciliation** — 11/11 within ±$2, worst **+$0.22** (0.43% of that bill), all
positive, total +$1.55 on $1,084.26 billed.

**M2, PG&E household (4345 kWh / 328 days)** — **SWITCH to E-TOU-C + PG&E bundled generation,
$170.72/yr cheaper.** The saving is **leaving the CCA, not changing schedule**: PCIA
+$159.88/yr, UUT on it +$13.59, franchise fee +$2.54, while 3CE generation is only $4.85/yr
cheaper. A 2018-vintage CCA customer pays PCIA 0.03679/kWh where the 2026 *bundled* PCIA is
−0.01011. Caveat printed in the report: PG&E Rules 22.1/23.1 require six months' notice, with
Schedule TBCC in between. Sensitivity (live run): E-1 overtakes only if evening usage grew
353%, or 132% load-neutral.

**M3 demo** (bundled SDG&E TOU-DR1, coastal_basic, **synthetic** 6,264 kWh load, 5 kW, window
2026-06-01 .. 2027-05-31): baseline $3,022/yr; solar only $1,855; +battery greedy $505; LP
$427; NBC import floor $86/yr. **Dollar totals are real, the LOAD is not — these figures are
deliberately absent from the public writeup.**

## EXACT NEXT ACTION

1. **Publish the writeup.** `docs/index.html` is ready to serve. The Artifact publish was
   blocked by session 7's permission classifier; the remaining paths are GitHub Pages on
   `docs/` or an Artifact publish once permitted. This is the last piece of M4's "writeup
   live" and takes minutes.
2. **Transcribe SDG&E's earlier 2026 rate vintages** (1/1/2026 and 4/1/2026 Total Rates
   Tables, delivery + generation), with **`months: [3, 4]` on the weekday 10:00-14:00
   super-off-peak rule** for any vintage before 2026-05-01. Restores a calendar-year SDG&E run
   and exercises version-switching end to end. Smallest well-defined unit of code work.
3. **CCA generation overlay** — a CCA's own generation rate + the vintaged PCIA, replacing
   EECC. PCIA vintage table already in the generation spec header. Blocked only on *which* CCA
   (San Diego Community Power vs Clean Energy Alliance).
4. **Confirm SDG&E ACC Plus** from an SDG&E NBT sheet. `acc.acc_plus_table` raises for SDG&E;
   `acc_plus_eligible=False` is the conservative path.
5. **PG&E ACC tables** — per-vintage PDFs (pge.com/energyexportcredit), not MIDAS CSVs; needs
   a different parser. Low priority.
6. **TOU-DR-P** — needs an events model before it can be ranked (open decision 2).

**M5 is the next milestone** (5 strangers send Green Button CSVs, receive a report, written
go/no-go on charging). It needs no new engine work — it needs the writeup published and
somewhere to post. Do not start it while M4's publish step is open.

> **⚠ READ THIS BEFORE STARTING M5 — the two milestones are coupled.** M5 targets San Diego
> (SDG&E) users, and **the engine has never been validated against a single real SDG&E bill or
> a real SDG&E Green Button export.** `src/greenbutton/sdge.py` was written to the documented
> format and never run on a real file; no SDG&E golden bill exists. Sending dollar figures to
> five strangers on that basis would violate invariant 1 (reconciliation-gated), which is the
> product's whole trust claim.
> **The consequence is a sequencing rule, and it is good news:** the FIRST recruit who supplies
> an SDG&E export *plus* three bills closes **M1's DoD**, and only then does the SDG&E path
> earn the right to produce dollar figures for the other four. So recruit for data before
> recruiting for sales, and tell the first one or two people plainly that they are validating
> the engine, not buying a verdict. A PG&E recruit needs no such caveat — that path is already
> reconciled 11/11.

## Open decisions
1. **SDG&E TOU-DR1 super-off-peak window — RESOLVED.** Year-round, effective 2026-05-01.
   Residual caveat: the superseding advice letter / revised P.U.C. sheet were not located; the
   evidence is SDG&E's customer-facing publications. Pre-2026-05-01 vintages need `months: [3,4]`.
2. **TOU-DR-P is deliberately unloadable.** Period windows unsourced, and the **RYU Event
   Adder ($1.16/kWh, 4-9 p.m. on event days)** is event-contingent with no engine concept. Do
   **not** default it to zero events. Preferred: caller-supplied event days, report as a
   range, or exclude and say why.
3. **SDG&E baseline allowances — RESOLVED.** Full climate-zone table (Sheet 29294-E) in-spec;
   `territory` supplied **at bill time**. Omitting it raises rather than defaulting.
4. **CARE rates on PG&E counterfactual schedules are DERIVED, not printed**
   (`care = 0.65 x standard - 0.01038`). Validated to ≤1e-5 on E-TOU-C, cross-checked against
   E-1's printed tier pair, corroborated by SDG&E's printed "CARE Discount 35%". `--no-care`
   is the tariff-only ranking.
5. **Santa Cruz UUT Adjustment — RESOLVED as a modeling assumption**, mechanism still
   UNVERIFIED. Adopted **$0.21649/day**. Schedule-independent, so it cannot reorder the
   ranking; the optimizer re-ranks under all three mechanisms to prove it.
6. **Which CCA and which SDG&E schedule dad is on** — still unresolvable without a bill.
7. **Privacy posture — RESOLVED session 7.** Self-attributed case study, CARE disclosed,
   exact dates and amounts kept, personal-tenancy detail scrubbed. See SESSION_NOTES §Session 7.

## Blocked on data (not on work)
- **M1 DoD** (dad's last 3 SDG&E bills within ±$2) and the README SDG&E rows. Dad's data is
  unavailable indefinitely: no bills, no Green Button export, no portal login.
- **M3 DoD** needs one real household with solar/export interval data. Same situation.
- Validation of `src/greenbutton/sdge.py` against a real SDG&E export.
- **M2's PG&E cross-check** is unavailable, not pending: PG&E's Rate Plan Comparison returns
  "no service agreement eligible for rate enrollment" for this account. `--pge-comparison
  FILE` is built and waiting.

## Flagged approximations still open (all sub-$0.05, non-blocking)
- **2025 franchise fee**: 2026 specs use the exact E-FFS per-kWh rate ($0.00059); the
  2025-vintage specs still carry the percent-of-energy approximation. (This is one of the two
  documented causes of the one-sided residual.)
- **2025 summer generation credit** still bill-fitted (the 2026 one is tariff-exact).
- **California Climate Credit** modeled as an observed per-bill line (−$58.23 on 10/28). PG&E
  files $(36.18), Aug/Sep cycles; SDG&E files $(33.50) semi-annual per Schedule GHG-ARR.
  Generalise to a versioned semiannual credit.
- **California Energy Commission surcharge on SDG&E**: PG&E specs carry $0.0003/kWh; SDG&E's
  Total Rates Table shows no such column, so it is deliberately NOT asserted either way.

## M3 open items (recorded, none blocking)
- SDG&E ACC Plus unconfirmed; settle with `acc_plus_eligible=False`.
- PG&E ACC tables not imported (PDFs, not MIDAS CSVs).
- **LP dispatch is a marginal-price optimum, not a settled-dollar optimum** — under NBT caps
  it can settle below greedy. Documented and reported honestly, not a bug.
- **CCA export terms** — netting excludes the CCA generation credit by default (Schedule NBT
  SC 2.a), so a CCA customer's result is a lower bound until supplied.

## Schema gaps (recorded, none blocking today)
- `PerKwhAdder` has no CARE variant (worked around on SDG&E by folding WF-NBC/DWR-BC into the
  energy `Rate`).
- **FERA / DRAH** (0.39688/day on both IOUs) unmodelable — `Rate` has only `standard`/`care`.
- No `tiers` concept. Correct for E-1 today (exact identity via the baseline credit); required
  if a third distinct tier price appears.

Do **not** build CLI/API/Docker/deployment/web UI — roadmap "Later", gated behind M5.
