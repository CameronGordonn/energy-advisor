# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it short and
current: state, how to run, open decisions, exact next action._

## Status: **M0 COMPLETE + polished** (2026-07-20, session 2).

The bill engine reproduces **all 11 PG&E statements within ±$2** (was 3), worst residual
**+$0.22**, from the customer's own hourly interval data. This is a **CCA (3CE) + CARE**
account. **39 tests green, ruff clean.** See README reconciliation table.

Coverage: **a full 12 months, Aug 2025 → Jun 2026** (every statement on hand). The 3
earliest (Aug–Oct 2025) were image PDFs, now OCR'd (tesseract, installed in the env) and
hand-fixtured; the 10/28 bill carries a **California Climate Credit −$58.23** (modeled as
an observed adjustment).

## What changed this session (see SESSION_NOTES §2026-07-20 Session 2)
- **Intra-period rate-version splitting** in the engine: a bill period can straddle a rate
  change, and delivery vs generation change on different dates. `compute_layer` takes a
  list of effective-dated versions; `load_spec_versions` loads them. Backward compatible.
- **New spec versions** (all rates derived from the bills, cited): E-TOU-C delivery
  `2025-01-01`, `2025-09-01`, `2026-01-01` (pre-IGFC, no BSC, higher per-kWh, a summer
  step on 2025-09-01); 3CE generation `2025-01-01` + existing renamed to `2026-02-15`
  (3CE winter rate changed 02-15, **date derived from interval data**).
- **Generation Credit now exact TOU** (winter AND summer, ≤$0.01/bill) — resolved a
  flagged APPROX. New TOU fields on `PerKwhAdder`.
- **Bug fix**: percent surcharges were double-counting across same-season sub-periods.
- Extractor generalized for the pre-IGFC bill format. 5 new text fixtures (committed in
  the first session-2 commit).
- **OCR**: installed tesseract/poppler/pytesseract/pdf2image; OCR'd the 3 image bills and
  hand-built + verified their fixtures. Summer-2025 delivery/gen/gen-credit rates + the
  Climate Credit now modeled. All 11 bills reconcile.

## How to run
```bash
conda activate energy-advisor    # env prefix: /home/cameron/miniforge3/envs/energy-advisor
PYTHONPATH=src python -m pytest -q                          # 39 tests; golden tests skip if data/ absent
ruff check . && ruff format --check .
PYTHONPATH=src python scripts/reconcile_report.py           # print all 11 line-item comparisons
PYTHONPATH=src python scripts/reconcile_report.py --write-readme   # refresh README table
PYTHONPATH=src python scripts/extract_golden_bills.py [--write]    # PDF -> fixtures (self-check gated)
```

## Open decisions (need Cameron)
1. **Santa Cruz UUT Adjustment** — Cameron: "no idea, leave as observed" (2026-07-20).
   11-bill evidence overturns last session's "phase-out" theory: the adjustment is
   ~constant **−$6.5/mo** (a near-fixed credit/cap/exemption), NOT a percentage or
   trend-to-0. Fed as an **observed per-bill line** (reconciliation is exact regardless);
   mechanism UNVERIFIED. **Must resolve before M2** (the counterfactual can't read an
   adjustment off a bill that doesn't exist). Candidate follow-up: City of Santa Cruz UUT
   ordinance / a PG&E bill insert.

## Flagged approximations still open (all sub-$0.05, non-blocking)
- **Franchise Fee** basis not cleanly recoverable; modeled per-era as % of energy, flagged.
- **2026 Summer Generation Credit** is a single-bill blend (−0.12013); refine to TOU with a
  2nd 2026-summer bill (needs a Jul/Aug 2026 statement). (2025 summer is already exact TOU.)
- **California Climate Credit** modeled as an observed per-bill line (−$58.23 on 10/28).
  For M2, generalize to a versioned semiannual (Apr/Oct) credit; confirm the amount schedule.
- **Non-CARE** E-TOU-C rates still `null` (this account is CARE) — needed for the general
  solar-shopper customer by M2; fill from the E-TOU-C tariff sheet.

## Plan for next session — two parallel workstreams (decided 2026-07-20)

Dad's SDG&E bills aren't available yet, so M1's **reconciliation DoD** is blocked — but
M1's **construction** is not (parser + specs come from public sources). Do both of these;
neither needs new customer data. Deployment/CLI/API/Docker are **out of scope** (roadmap
"Later", gated behind the M5 demand verdict) — do not build them.

### Workstream A — Build M1 from public sources (SDG&E + San Diego CCA)
Author everything except the final reconciliation; validate the moment dad's bills land.
Respect the invariants: every rate cited to a public tariff sheet (URL + revision);
mark unknowns `UNVERIFIED` (loader raises); model the CCA delivery/generation split like
3CE; the version-splitting engine (`load_spec_versions` + `_rate_subperiods`) already
handles mid-period rate changes, reuse it.
1. **SDG&E Green Button parser** (`src/greenbutton/sdge.py`) — SDG&E exports 15-min data
   (up to 13 months); format is public/documented. Mirror the PG&E parser's canonical
   `IntervalSeries` output (tz-aware, PII-stripped, DST-handled, gap-explicit). Add a
   `Utility.SDGE` path. Unit-test against the documented format (no real file yet).
2. **SDG&E residential schedule specs** (`src/tariffs/specs/`) from SDG&E's published
   tariff sheets: standard TOU (**TOU-DR1, TOU-DR2, TOU-DR-P**) and EV (**EV-TOU-5**),
   each delivery-layer, effective-dated, cited. SDG&E baseline allowances + the
   **non-bypassable charges** and the resulting **~2.5¢/kWh import bill floor** (invariant
   #4) — model these explicitly.
3. **San Diego CCA generation overlay** — generation-layer specs for the CCA that serves
   dad's address (**San Diego Community Power** for the City of SD; **Clean Energy
   Alliance** for parts of N. County — confirm from a bill). Layer on SDG&E delivery
   exactly like 3CE-on-PG&E.
4. **Blocked until bills:** the reconciliation gate (M1 DoD = dad's last 3 SDG&E bills
   within ±$2). Confirm dad's exact schedule + CCA + territory from his first bill, then
   reconcile and publish the SDG&E rows in the README table.

### Workstream B — Finish PG&E for the general (non-CARE) customer [M2 prep]
Small; needs no new bills. The engine already bills non-CARE everywhere **except one gap**:
1. **Non-CARE Base Services Charge** — `fixed_per_day.standard` is `null` only in
   `pge_etou_c_delivery_2026-03-01.yaml`. Fill from the E-TOU-C tariff sheet. NOTE the BSC
   is **income-graduated** (CARE ≈ $0.19713/day; non-CARE has income tiers, default
   ~$24.15/mo) — model the default non-CARE tier, cite, and leave a note about tiers.
   (Pre-IGFC specs correctly have no BSC; standard energy rates are already present.)
2. **Franchise Fee / UUT for non-CARE** — verify the basis is customer-class-independent
   (likely yes) once the tariff sheet is in hand; the current FF is still APPROXIMATE.
3. Add a **non-CARE golden path**: a synthetic or (better) a real non-CARE bill later.
   For now, add a test that billing non-CARE no longer raises and the numbers are sane.

### Then: M2 rate optimizer (needs A or B done)
Re-simulate the PG&E household's full year under every eligible schedule; rank annual cost;
report savings + the sensitivity note. Needs the other PG&E residential schedules
(E-1 tiered, E-TOU-D, EV2-A) authored — public tariff sheets, no customer data.

### Still open before M2 (from session 2)
- **UUT Adjustment** mechanism (Cameron: leave observed for now) — needed to model the
  counterfactual. Chase the City of Santa Cruz UUT ordinance / a PG&E bill insert.
- **2026 summer Generation Credit** is a single-bill blend; refine to TOU with a Jul/Aug
  2026 statement.
- **California Climate Credit** — generalize the observed −$58.23 line to a versioned
  semiannual (Apr/Oct) credit.
