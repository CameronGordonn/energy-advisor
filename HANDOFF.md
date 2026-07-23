# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it short and
current: state, how to run, open decisions, exact next action._

## Status: **M0 COMPLETE + polished. M1 in progress** (2026-07-23, session 3).

The bill engine reproduces **all 11 PG&E statements within ±$2**, worst residual
**+$0.22**, from the customer's own hourly interval data (CCA/3CE + CARE account).
**56 tests green, ruff clean.** See README reconciliation table.

Session 3 landed (`70677c2`): **Workstream B complete** (non-CARE PG&E billing
unblocked) and **Workstream A step 1 complete** (SDG&E Green Button parser).

## What changed this session (detail in SESSION_NOTES §2026-07-23)
- **Non-CARE PG&E billing works.** Filled the Income Tier 3 Base Services Charge
  **$0.79343/day** from the real tariff sheet (**Cal. P.U.C. Sheet 61364-E**). The IGFC
  has three tiers: T1/CARE 0.19713, T2/FERA 0.39688, T3/default 0.79343 — all documented
  in the spec. **FERA is a class the engine can't express yet** (`Rate` has only
  `standard`/`care`).
- **The tariff sheet independently confirmed M0's bill-derived rates** (Total Usage and
  Baseline Credit match exactly) — evidence the reconciliation isn't curve-fitting.
- **FF/UUT verified customer-class-independent**; the IGFC is the only graduated piece.
- **`src/greenbutton/_common.py`** — shared parser core (both IOUs use the same Opower
  platform). `pge.py` refactored onto it, behavior byte-identical; **11/11 bills still
  reconcile**.
- **`src/greenbutton/sdge.py`** — SDG&E parser: `M/D/YYYY` dates, IMPORT/EXPORT register
  split (bills import; export noted, NEM netting is M3), `Utility.SDGE`. 16 tests.
- Found the **Climate Credit** figure M2 needs: PG&E E-TOU-C **$(36.18) semi-annual,
  paid in the Aug and Sep bill cycles** (not Apr/Oct as earlier notes assumed).

## How to run
```bash
conda activate energy-advisor    # env prefix: /home/cameron/miniforge3/envs/energy-advisor
PYTHONPATH=src python -m pytest -q                          # 56 tests; golden tests skip if data/ absent
ruff check . && ruff format --check .
PYTHONPATH=src python scripts/reconcile_report.py           # print all 11 line-item comparisons
PYTHONPATH=src python scripts/reconcile_report.py --write-readme   # refresh README table
PYTHONPATH=src python scripts/extract_golden_bills.py [--write]    # PDF -> fixtures (self-check gated)
```

## EXACT NEXT ACTION — extend the tariff engine to N-period, day-type-aware TOU

**This is the hard blocker for the rest of M1.** SDG&E residential schedules cannot be
expressed at all by the current 2-period engine, so no SDG&E spec can be authored until
this lands. It needs no customer data and is fully testable now.

What SDG&E requires that the engine lacks (all confirmed from Cal. P.U.C. Sheets
29952–29955-E; full period tables in SESSION_NOTES):
1. **Three periods** — On-Peak / Off-Peak / Super-Off-Peak. `TouDef.peak_hours` is a
   single list with off-peak as the complement; a third period is unrepresentable.
2. **Weekday vs weekend/holiday schedules differ** (weekday super-off-peak 00:00–06:00;
   weekend/holiday 00:00–14:00). `_usage()` keys off hour only, never day type.
3. **Month-conditional periods** — winter weekday 10:00–14:00 is super-off-peak in
   **March and April only**.
4. **Baseline credit up to 130% of baseline** (PG&E is 100%) — add a multiplier to
   `Baseline`, which currently hardcodes `min(usage, allowance)`.

**Design to implement (backward compatible — worked out, just build it):** replace
`TouDef.peak_hours` with an ordered first-match-wins rule list —
`{period, hours: [[start,end)], days: all|weekday|weekend, months: [...]}` plus a
`default_period`. Keep `peak_hours` as sugar normalizing to periods `peak`/`offpeak` so
**every existing PG&E spec and its YAML keys (`summer_peak`, `winter_offpeak`, …) keep
working untouched**. Then `energy` becomes `dict[str, Rate]` keyed `f"{season}_{period}"`,
`_usage()` returns kWh **per period** instead of `(peak, off)`, and the energy / CARE /
TOU-adder loops iterate periods. SDG&E specs then use `summer_on_peak`,
`winter_super_off_peak`, etc.

**Regression gate for the refactor: all 11 golden bills must still reconcile within ±$2.**
Run `scripts/reconcile_report.py` before and after — this is the product's trust artifact.

### Then, still in M1 (all from public sources, no customer data needed)
5. **SDG&E delivery specs** — TOU-DR1, TOU-DR2, TOU-DR-P, EV-TOU-5. Layer model maps
   directly onto the tariff's own split: **UDC Total + DWR-BC = delivery**, **EECC =
   generation** (the layer a CCA replaces). Model the **NBCs explicitly** (PPP + ND + CTC
   + DWR-BC ≈ 0.0206/kWh on the archived sheet) and the resulting **import floor**
   (invariant #4), plus the **Minimum Bill $0.329/day** (CARE $0.164) and the cited
   **Franchise Fee Differential 5.78%** (City of San Diego).
   ⚠ **The rate VALUES captured in SESSION_NOTES are from the Jan-2018 filing and are
   STALE.** The structure is authoritative and reusable; **re-pull current numbers from
   SDG&E's "Total Rates Table" regulatory PDFs before any spec ships.** Never ship the
   2018 numbers as current.
6. **San Diego CCA generation overlay** — layer on SDG&E delivery exactly like 3CE on
   PG&E. Which CCA is unresolved (see open decisions).
7. **Blocked until dad's bills:** the M1 reconciliation DoD (last 3 SDG&E bills within
   ±$2) and the README SDG&E rows.

Do **not** build CLI/API/Docker/deployment — roadmap "Later", gated behind the M5 demand
verdict.

## Open decisions (need Cameron)
1. **Holiday calendar (NEW, blocks the day-type work).** SDG&E prices holidays as weekend
   days, moving 16:00–21:00 usage off On-Peak on ~6–10 days/year — real dollars. The
   observed-holiday list must come from the tariff (Rule 1 / schedule definitions),
   **not guessed**.
2. **Minimum bill vs NBC import floor (NEW).** Which governs when both bind, and does the
   minimum bill apply to delivery only or the combined bill? Affects every low-usage and
   high-solar month.
3. **Which CCA + which schedule (NEW).** SDCP (City of SD) vs Clean Energy Alliance (parts
   of N. County); and TOU-DR1 vs TOU-DR2 vs TOU-DR-P vs EV-TOU-5. Both unresolvable until
   dad's first bill — confirm from it before authoring the "default" SDG&E path.
4. **Santa Cruz UUT Adjustment** — Cameron: "no idea, leave as observed" (2026-07-20).
   11-bill evidence: a near-constant **−$6.5/mo** credit/cap/exemption, NOT a percentage
   or a phase-out. Fed as an **observed per-bill line** (reconciliation exact regardless);
   mechanism UNVERIFIED. **Must resolve before M2** (the counterfactual can't read an
   adjustment off a bill that doesn't exist).

## Flagged approximations still open (all sub-$0.05, non-blocking)
- **Franchise Fee (PG&E)** basis not cleanly recoverable; modeled per-era as % of energy.
- **2026 Summer Generation Credit** is a single-bill blend (−0.12013); refine to TOU with
  a 2nd 2026-summer bill (needs a Jul/Aug 2026 statement). 2025 summer is already exact TOU.
- **California Climate Credit** modeled as an observed per-bill line (−$58.23 on 10/28).
  For M2, generalize to a versioned semiannual credit — PG&E E-TOU-C files **$(36.18),
  Aug/Sep bill cycles** (Sheet 61364-E); reconcile that against the observed −$58.23.
- **FERA (IGFC Tier 2)** unmodelable — `Rate` supports only `standard`/`care`.
