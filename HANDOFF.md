# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it short and
current: state, how to run, open decisions, exact next action._

## Status: **M0 COMPLETE** (2026-07-20). DoD met.

The bill engine reproduces the **last 3 real PG&E electric bills within ±$2** from the
customer's own 15-min (actually hourly) interval data. This account is a **CCA (3CE) +
CARE** account, so M0 already implements the delivery/generation-layer + PCIA + CCA
machinery the roadmap had deferred to M1.

Reconciliation (electric net, modeled − bill): 04-29 **+$0.41**, 05-29 **+$0.06**,
06-28 **+$0.12** — all PASS. 29 tests green, ruff clean. See README table.

## What exists
- `src/greenbutton/` — PG&E interval CSV parser → canonical tz-aware `IntervalSeries`
  (PII stripped, DST-handled, gap-explicit). `parse_pge_interval_csv`.
- `src/tariffs/` — `schema.py` (effective-dated, citation-mandatory, UNVERIFIED-raises),
  `loader.py`, `bill.py` (pure billing fn: season proration, CARE discount, adders,
  surcharges). Specs: `specs/pge_etou_c_delivery_2026-03-01.yaml`,
  `specs/cce_mbretch1_generation_2026-01-01.yaml`.
- `src/report/reconcile.py` — compares modeled bill vs golden fixture, printed table.
- `tests/golden_bills/pge_*.yaml` — anonymized fixtures (3). `test_reconciliation.py`
  is the merge gate. Raw PDFs live git-ignored in `data/` and `tests/golden_bills/raw/`.
- `scripts/extract_golden_bills.py` (PDF→fixture, self-check gated),
  `scripts/reconcile_report.py` (print comparisons + regenerate README table).

## How to run
```bash
conda activate energy-advisor
pytest -q                                      # 29 tests; golden tests skip if data/ absent
ruff check . && ruff format --check .
PYTHONPATH=src python scripts/reconcile_report.py            # print line-item comparisons
PYTHONPATH=src python scripts/reconcile_report.py --write-readme   # refresh README table
```

## Open decisions / flagged approximations (all sub-$2, see SESSION_NOTES for detail)
1. **Santa Cruz UUT Adjustment** — not derivable (cancels 68% of tax one month, ~100%
   the next; looks like a municipal true-up). Fed as an **observed per-bill line**, not
   computed. Cameron hasn't confirmed a UUT change. Revisit for the M2 optimizer.
2. **Franchise Fee** — modeled ~0.14% of energy (residual <$0.05); exact basis unconfirmed.
3. **Non-CARE base-services daily rate** — not on the (CARE) bills; left `null`. Billing a
   non-CARE customer raises until filled from the E-TOU-C tariff sheet (~$24.15/mo).
4. **Generation Credit** — flat-seasonal approx of a TOU-weighted PG&E generation rate
   (worst single-line residual $0.29). Fine for M0; refine from PG&E generation tariff.
5. **DST** — PG&E exports nominal wall-clock; fall-back folds to 1 grid gap, spring-forward
   `02:00`→`03:00`. TOU-neutral (super-off-peak).

## Data facts
- Interval export is **hourly** (this meter has no 15-min). Fine for TOU.
- 3 earliest bills (Aug–Oct 2025) are **image-based PDFs** → need OCR to fixture.
- Pre-March-2026 bills use the **pre-IGFC** structure (no Base Services Charge) → need an
  earlier E-TOU-C spec version before they can reconcile.

## Nothing is committed yet
Cameron commits only when asked. A first commit of the M0 work is a reasonable next step
(everything PII is git-ignored; verified clean).

## Suggested next actions (pick with Cameron)
- **Commit M0.** (branch off `main`; the repo is on `master` with no commits yet.)
- **M0 polish (optional):** author the pre-IGFC E-TOU-C spec version + OCR the 3 image
  bills → reconcile all ~8–11 statements, filling out the README table.
- **M1 (ROADMAP):** SDG&E parser quirks + SDG&E residential schedules + San Diego
  Community Power overlay. The CCA layering from M0 transfers directly.
- Get **non-CARE** E-TOU-C rates + the exact franchise-fee basis from the PG&E tariff
  sheet so the engine serves the general (non-CARE) solar-shopper customer (needed by M2).
