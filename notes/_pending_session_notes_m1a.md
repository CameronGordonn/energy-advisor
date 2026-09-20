# PENDING — merge this into SESSION_NOTES.md (newest first), then delete this file.

Not prepended directly because a parallel session owns `docs/` and the continuity files
this sprint; two sessions prepending to the same file is a conflict for no gain.

---

## 2026-09-20 — Session 29 (the bill-only path: M1a can be reconciled by transcription)

Full working: `notes/m1a_harness_2026-09.md`. Branch `m1a-bill-harness`, not merged.

**No milestone moved and no SDG&E dollar was earned.** `data/` is still PG&E-only. What
moved is the harness, and the reason it needed to move is a repeat of session 24's lesson
in a new place: HANDOFF said the harness was "utility-general and needs nothing but
transcription", and that was true of the *interval* path and false of the path M1a's DoD
actually requires. `reconcile()` took an `IntervalSeries` positionally,
`load_interval_series()` globbed `data/`, and every dollar test skipped when the export was
absent — so a fixture with a statement and no export could not be reconciled at all, which
is exactly the fixture M1a is defined by. **"Ready" was a sentence again, not a test.**

### ⭐ The two paths are one charge layer, and that is measured on real bills

`tariffs.bill.charge_lines` was extracted out of `compute_layer` and is now the only copy
of the per-run charge construction; `tariffs/bucketed.py` feeds it the statement's printed
kWh instead of a bucketed series. The claim that they agree is not asserted by
construction — it is measured on the eleven PG&E golden bills, the only place this repo
holds a real export **and** a real statement: bucket the real intervals, price the buckets,
and every line item, every layer total and the net land **exactly** on the interval path's,
with the statements still reconciling. Two parametrized tests, 22 cases.

Mutation-measured: collapsing the sub-period split — the single most plausible way to make
a straddling statement "work" — fails **14** tests, 12 of them parity cases on the golden
bills themselves.

### ⭐ The scope finding that belongs in the recruiting ask, not in the code

The bill-only path loses within-period timing. Charge by charge on TOU-DR1 that costs
almost nothing — the fixed charge, the baseline credit, the CARE discount, the PCIA and the
minimum bill are all functions of `(days, total kWh, per-period kWh)`. **Two exceptions:**

1. **Sub-period boundaries, and this one bites.** SDG&E filed five 2026 TOU-DR1 vintages
   (1/1, 4/1, 5/1, 6/1, 8/1) and its summer starts 6/1, so an ordinary 30-day statement
   straddles a boundary more often than not, and the two layers can change on different
   dates. Printed buckets never say which side of the change the kWh fell on. The fixture
   schema therefore takes a **list** of segments, one per block the statement itself
   prints, and a segment that spans a boundary raises `SegmentStraddlesRateChangeError`
   naming the date to split at — never split pro rata. **If a real statement spans a change
   and does not itemise its own sub-periods, that month is unreconcilable without interval
   data and no harness work fixes it.** So the ask gains two lines: prefer a period inside
   one vintage, and ask for the sub-period blocks.
2. **TOU-DR-P cannot be reconciled from printed buckets at all.** The RYU adder is billed
   on kWh inside 16:00–21:00 *on the days SDG&E called*, finer than any printed bucket.
   `TimingDependentChargeError`, by name — reading the absent number as zero was the
   obvious alternative and it is the flattering one.

### Two measurements taken while enumerating, worth keeping

- **TOU-DR1's delivery layer does not use the TOU split.** Its energy rate is 0.33539 in
  all six season/period cells, so five allocations of the same 400 kWh spanning all-on-peak
  to all-super-off-peak give delivery $120.53 every time, while generation spans
  $16.48–$139.68. **The whole information content of the printed split, on TOU-DR1, is the
  generation line.**
- **The Minimum Bill can never bind on TOU-DR1 at 2026 rates.** 30-day floor $9.87 standard
  / $4.92 CARE against a Base Services Charge of $23.80 / $5.91, with delivery monotone in
  kWh. The spec's citation flags its 2018-filing values as unconfirmed; that flag does not
  matter for an ordinary bill, because the line is structurally unreachable. It would matter
  on a NEM account in M3.

### The honest boundary on what M1a will prove

The bill-only path takes **SDG&E's own bucketing as given**. It tests our rates and charge
structure; it cannot test `tou.rules` — the year-round super-off-peak window (still
evidenced by SDG&E's customer-facing publications rather than a located tariff sheet), the
weekend table, the holiday calendar. **A green M1a does not retire that caveat.** That is
the line between M1a and M1b and it is why M1b still needs an export from the same
household. Stated because it is exactly the kind of thing a passing reconciliation makes
easy to forget.

Corollary worth recording: an M1a household is non-solar and non-NEM by definition, so
**nothing in M1a exercises the non-bypassable-charge import floor** (differentiation
invariant 4). M1a does not corroborate it.

### Refusals added, all needing no data

`NoUsageEvidenceError` (neither export nor printed kWh — an error, not a skip, because a
skip reads as a pass), `PrintedUsageDisagreementError` (both present and disagreeing beyond
0.5 kWh per period, reported per period with both numbers and never averaged — that
comparison is the only direct measurement of M1b's bucketing claim available),
`SegmentCoverageError`, `SegmentStraddlesRateChangeError`, `UnbucketedPeriodError`.

New `tests/golden_bills/sdge_BILL_ONLY_TEMPLATE.yaml.example` — `.yaml.example` for the
same load-bearing reason as the existing template. It carries no dollars **and no kWh**: a
load is an expectation too, so every bucket ships blank and is refused by period name,
asserted by test.

### ⚠ One failing test, deliberately left failing

`tests/report/test_web_engine.py::test_the_committed_bundle_matches_src`. `bill.py` is
bundled into `docs/engine.js` and this session changed it. `docs/` is owned by a parallel
session, so the rebuild was not run here. Fix on merge:
`PYTHONPATH=src python scripts/build_web_engine.py`, then regenerate `docs/case-study.json`
(it pins the bundle digest). `src/tariffs/bucketed.py` is deliberately **not** in `MODULES`
— the browser does not transcribe fixtures.

Counts, measured not copied: **1,771 passed, 1 failed** (that one), from 1,711 passed on
`main`. +61 tests. ruff clean.

### ⚠ Working-tree collision, for the record

Both sessions ran in the same checkout. Session 29 created `m1a-bill-harness`; the docs
session then checked out `site-overhaul` over it, so this work was committed from a linked
worktree instead and the shared tree was returned to the docs session untouched. **Two
concurrent sessions need `git worktree`, not one checkout.**
