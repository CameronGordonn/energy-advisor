# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it short and
current: state, how to run, open decisions, exact next action._

## Status: **M0 COMPLETE + polished** (2026-07-20, session 2).

The bill engine reproduces **all 8 machine-readable PG&E statements within ±$2** (was 3),
worst residual **+$0.21**, from the customer's own hourly interval data. This is a **CCA
(3CE) + CARE** account. **36 tests green, ruff clean.** See README reconciliation table.

Coverage: Oct 2025 → Jun 2026 (8 statements). The 3 earliest (Aug–Oct 2025) are image-only
PDFs (need OCR); the M0 DoD window is fully covered.

## What changed this session (see SESSION_NOTES §2026-07-20 Session 2)
- **Intra-period rate-version splitting** in the engine: a bill period can straddle a rate
  change, and delivery vs generation change on different dates. `compute_layer` takes a
  list of effective-dated versions; `load_spec_versions` loads them. Backward compatible.
- **New spec versions** (all rates derived from the bills, cited): E-TOU-C delivery
  `2025-01-01` + `2026-01-01` (pre-IGFC, no BSC, higher per-kWh); 3CE generation
  `2025-01-01` + existing renamed to `2026-02-15` (3CE winter rate changed 02-15,
  **date derived from interval data**).
- **Generation Credit now exact TOU** (winter, ≤$0.01/bill) — resolved a flagged APPROX.
  New TOU fields on `PerKwhAdder`. Summer still a single-bill blend.
- **Bug fix**: percent surcharges were double-counting across same-season sub-periods.
- Extractor generalized for the pre-IGFC bill format (hyphen separator, `$`-prefixed
  amounts). 5 new golden fixtures written + committed.

## How to run
```bash
conda activate energy-advisor    # env prefix: /home/cameron/miniforge3/envs/energy-advisor
PYTHONPATH=src python -m pytest -q                          # 36 tests; golden tests skip if data/ absent
ruff check . && ruff format --check .
PYTHONPATH=src python scripts/reconcile_report.py           # print all 8 line-item comparisons
PYTHONPATH=src python scripts/reconcile_report.py --write-readme   # refresh README table
PYTHONPATH=src python scripts/extract_golden_bills.py [--write]    # PDF -> fixtures (self-check gated)
```

## Open decisions (need Cameron)
1. **Santa Cruz UUT Adjustment** — 8-bill evidence overturns last session's "phase-out"
   theory: the adjustment is ~constant **−$6.5/mo** (a near-fixed credit/cap/exemption),
   NOT a percentage or trend-to-0. Fed as an **observed per-bill line** (reconciliation is
   exact regardless). Do you know of a Santa Cruz UUT cap/exemption/rebate (CARE-related)?
   Needed to model it for the M2 counterfactual.
2. **OCR the 3 image bills** (Aug–Oct 2025)? No OCR tooling installed. Options: install
   tesseract+poppler+pytesseract; you hand-enter their line items; or skip (they're
   outside the DoD window). One Oct statement likely has an **electric** Climate Credit
   to model if OCR'd.

## Flagged approximations still open (all sub-$0.05, non-blocking)
- **Franchise Fee** basis not cleanly recoverable; modeled per-era as % of energy, flagged.
- **Summer Generation Credit** is a single-bill blend (−0.12013); refine to TOU with a 2nd
  summer bill (needs a Jul/Aug 2026 statement).
- **Non-CARE** E-TOU-C rates still `null` (this account is CARE) — needed for the general
  solar-shopper customer by M2; fill from the E-TOU-C tariff sheet.

## Suggested next actions (pick with Cameron)
- **Commit session-2 work** (branch off `main`; PII is git-ignored, verified clean).
- Resolve the two open decisions above (UUT mechanism, OCR).
- **M1 (ROADMAP):** SDG&E parser quirks + SDG&E residential schedules + San Diego
  Community Power overlay (dad's bills). The CCA + version-splitting machinery transfers.
