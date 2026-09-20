# The M1a bill-only reconciliation path (2026-09-20, session 29)

Written for: Cameron, and the next session that touches `tariffs/` or the golden-bill gate.

Branch: `m1a-bill-harness`. Nothing merged to `main`.

**What changed:** the reconciliation harness grew a second entry point that prices a
statement from **its own printed per-TOU-period kWh**, with no interval export anywhere in
the loop. That is what M1a's DoD says it needs ("from the statements' own per-TOU-period
kWh, no interval data required" — ROADMAP, amended 2026-09-16), and until now it was not
possible: `reconcile()` took an `IntervalSeries` positionally, `load_interval_series()`
globbed `data/`, and every dollar test skipped when the export was absent.

**What did not change:** no SDG&E dollar figure is asserted anywhere, no fixture was
committed, no spec moved, and the eleven PG&E golden bills reconcile exactly as before.
M1a is still blocked on one ordinary SDG&E statement. What is no longer blocked is the
*harness*, which can now consume that statement the day it arrives, by transcription.

---

## 1. The scope finding, first: what printed buckets can and cannot price

CLAUDE.md's working style says to surface a modeling tradeoff rather than choose it
silently. The bill-only path loses within-period timing, so here is every charge in the
SDG&E TOU-DR1 delivery + generation specs, and whether "kWh in TOU period P over N days"
is enough for it.

### 1a. Charge by charge

| Charge (spec block) | Depends on | Printed buckets enough? |
|---|---|---|
| Base Services Charge (`fixed_per_day`) | days × rate | **Yes.** Needs only the period length. |
| Energy per TOU period (`energy`) | kWh_P × rate(season, P) | **Yes** — provided no segment spans a season or rate-version boundary. That proviso is §1b and it is the real constraint. |
| Baseline Credit (`baseline`) | `min(total kWh, days × allowance(season, zone) × 1.30) × credit` | **Yes.** A function of *total* kWh and days; the TOU split never enters. The climate zone does, and it is a customer fact the fixture must state (unchanged). |
| CARE Discount | Σ kWh_P × (care_P − std_P) + credited kWh × (care − std) | **Yes.** Per-period kWh is exactly its input. |
| PCIA, vintaged (`adders`, CCA only) | flat $/kWh × total kWh | **Yes.** Flat per kWh, so total kWh suffices; the *vintage* is a customer fact, unchanged. |
| CEA's Clean Impact credit (`adders`) | flat $/kWh × total kWh | **Yes.** |
| Minimum Bill (`minimum_bill`) | days × $/day vs the layer total | **Yes** — and see §1c, where it turns out it can never bind on TOU-DR1. |
| Non-bypassable charges (`non_bypassable`) | — | **Not applicable.** `included_in_energy_rate: true`: the block changes no line on an ordinary bill. It exists so the NEM netting model can carve the NBCs out of what export credits may offset, and that carve-out is `total imported kWh × 0.02099`, which printed buckets give. But an M1a household is non-solar and non-NEM by definition, so nothing on its statement touches this. **The ~2.5¢ import floor of differentiation invariant 4 is not exercised by M1a at all, and M1a does not corroborate it.** |
| Tiering | — | **Not applicable.** TOU-DR1 is not tiered; the schema has no tier concept. The baseline is a *credit* against an allowance, not a rate tier, and it is handled above. |
| Energy Commission Tax | total kWh × rate | **Yes** (PG&E generation only; no SDG&E TOU-DR1 spec carries it). |
| Percent surcharges (`surcharges`) | % of a sub-period subtotal | **Yes** — linear in the lines above. No SDG&E TOU-DR1 spec has one: the Franchise Fee Differential is deliberately unmodeled (City-of-San-Diego-only, a customer fact), and that is unchanged by this work. |
| California Climate Credit | flat per household, by month | **Yes.** Independent of usage entirely. |
| **RYU Event Period Adder** (`event_adder`, TOU-DR-P only) | kWh inside 16:00–21:00 **on the days SDG&E called** | **NO.** Strictly finer than any bucket a statement prints. |

### 1b. The one that actually bites: sub-period boundaries

A printed bucket says how much energy fell in each TOU period. It never says **on which
side of a rate change** it fell, and the two sides are priced differently.

This is not a corner case on SDG&E. SDG&E filed **five** 2026 TOU-DR1 vintages — 1/1, 4/1,
5/1, 6/1, 8/1 — and its summer season starts 6/1 and ends 10/31, and delivery and
generation can change on different dates (as PG&E's 2026-03-01 and 3CE's 2026-02-15
already do in this repo's own fixtures). A routine 30-day statement straddles a boundary
more often than not. The 2026-05-01 vintage also changed the TOU rules themselves (the
super-off-peak window went year-round), so the two halves of a late-April statement are
not even bucketed the same way.

**What the bill-only path returns instead:** `SegmentStraddlesRateChangeError`, naming the
boundary date and telling the transcriber to split there. The fixture schema therefore
carries a **list** of segments, one per block the statement itself prints — which is how
CA utilities print a mid-cycle rate change. Several segments may share a run (harmless,
they are summed exactly as the interval path sums days); a segment that spans one is
refused. Nothing is split pro rata, because pro rata would be a guess with a dollar
attached.

**This is an M1a scope finding, and it is the one that can bite on the day a bill
arrives.** If a real SDG&E statement spans a rate change and does **not** itemise its own
sub-periods, that month is not reconcilable without interval data, and no amount of harness
work fixes it. Two consequences for the ask in `RECRUITING.md`:

1. Prefer statements whose billing period lies inside one rate vintage. For the 2026
   vintages that means periods contained in 1/1–3/31, 4/1–4/30, 5/1–5/31, 6/1–7/31 or
   8/1 onward, and not spanning 10/31.
2. When asking for the bill, ask for **the usage-by-time-of-use table including any
   sub-period blocks**, not just the totals.

### 1c. Two things measured while enumerating, both worth keeping

**The delivery layer does not use the TOU split at all.** TOU-DR1's delivery energy rate is
0.33539 in every one of the six season/period cells, so delivery dollars are a function of
total kWh, days, season and climate zone only. Measured through the engine — June 2026,
400 kWh, coastal_basic, bundled:

| allocation (on / off / super-off) | delivery | generation |
|---|---|---|
| 400 / 0 / 0 | $120.53 | $139.68 |
| 0 / 400 / 0 | $120.53 | $51.41 |
| 0 / 0 / 400 | $120.53 | $16.48 |
| 100 / 200 / 100 | $120.53 | $64.75 |
| 133 / 134 / 133 | $120.53 | $69.14 |

Delivery is constant to the cent across allocations spanning the whole simplex; generation
spans $16.48–$139.68 on the same 400 kWh. **So the entire information content of the
printed TOU split, on TOU-DR1, is the generation line.** A statement that printed only
total kWh would still pin the delivery half exactly — useful to know if a transcription
turns out to be partial.

**The Minimum Bill can never bind on TOU-DR1, at 2026 rates.** Probed at 30 days: the
floor is $9.87 standard / $4.92 CARE, while the Base Services Charge alone is $23.80 /
$5.91, and delivery is monotone increasing in kWh (the 0.33539 energy rate exceeds the
0.10663 baseline credit). The `minimum_bill` block is modeled and carries a citation that
already flags its 2018-filing values as unconfirmed; **this says that flag does not matter
for an ordinary TOU-DR1 bill, because the line is structurally unreachable.** It would
matter on a NEM account whose delivery total is driven down by credits — i.e. in M3, not
M1a.

---

## 2. What was built

### `src/tariffs/bill.py` — the charge layer extracted, not duplicated

Two pure extractions, no behaviour change (the eleven golden bills and all 1,439
`tests/tariffs` + `tests/golden_bills` tests were green immediately after, before anything
new was added):

- `charge_lines(spec, season, *, days, usage, event_kwh, care, service, territory, vintage)`
  — every line one `(spec version, season)` run bills. `compute_layer` now derives `usage`
  from the interval series and calls this; the bucketed path passes the statement's kWh to
  the same function. **This is deliberately the only copy.** A second implementation would
  let the bill-only path pass its gate while the interval path was wrong, or the reverse.
- `minimum_bill_line(items, meta, days, *, care)` — the SDG&E floor, likewise shared.
- `TimingDependentChargeError` — raised by `charge_lines` when a spec carries an
  `event_adder` and `event_kwh is None`. Reading the absent number as zero was the obvious
  alternative and it is the flattering one; TOU-DR-P is exactly the schedule where zero
  events versus the 18-day cap is the difference between a recommendation and its opposite.

### `src/tariffs/bucketed.py` — new

`UsageSegment`, `compute_layer_from_usage`, `compute_bill_from_usage`, and the refusals:
`SegmentCoverageError`, `SegmentStraddlesRateChangeError`, `UnbucketedPeriodError`.

Also `segments_from_series(...)`, which buckets a real interval export into the segments a
statement would have printed. That is a **test instrument**: it is what makes the bill-only
path measurable against the PG&E golden bills before any bill-only fixture exists.

### `src/report/reconcile.py` — the second entry point

`reconcile(fixture, series=None, ...)` now dispatches on the evidence the fixture carries:

| fixture carries | what happens |
|---|---|
| interval export only | today's path, unchanged (M1b) |
| `printed_usage:` only | the bill-only path (M1a) |
| both | cross-checked per TOU period, then reconciled from the intervals |
| neither | **`NoUsageEvidenceError`**, not a skip |

The "neither" case is an error rather than a skip on purpose: a skipped reconciliation
reads as a passing one in a green run, which is the exact failure mode `tests/golden_bills`
already had for SDG&E.

The "both" case is `PrintedUsageDisagreementError`, reported **per period with both
numbers** and never averaged. It is worth more than a validation check: a fixture holding
both is the only place M1b's central claim — that `greenbutton` + `tou.rules` reproduce the
utility's own bucketing — can be measured against the utility's own answer. Tolerance is
`printed_usage.tolerance_kwh`, default **0.5 kWh** per period, which is exactly SDG&E's
printing granularity (it prints whole kWh). Widening it needs a written reason.

`ReconResult` gained `usage_source` (`interval` | `printed`) and `format_comparison` prints
it, because the two carry different claims and a printed comparison that did not say which
one it was would overstate itself.

### `tests/golden_bills/sdge_BILL_ONLY_TEMPLATE.yaml.example`

New template, `.yaml.example` for the same load-bearing reason as the existing one: the
gate globs `*.yaml`, so a template cannot be mistaken for evidence. It keeps
`sdge_TEMPLATE.yaml.example`'s habit of refusing by name for each missing customer fact,
and extends it: **every printed kWh ships blank and is refused by period name**, because a
load is an expectation too and an unfilled bucket read as zero is a fabricated usage figure
that lowers the bill.

---

## 3. Evidence

### Parity: the two paths are one charge layer

The eleven PG&E golden bills are the only place this repo holds a real interval export
**and** a real statement, so they are the only place the bill-only path can be validated
today. Bucketing their real intervals and pricing the result reproduces the interval path
**exactly** — every line item, every layer total, the net — not within the ±$2 gate, and
the statements themselves still reconcile through the bill-only path.

Two parametrized tests over all eleven fixtures:
`test_the_two_paths_produce_identical_dollars_on_every_golden_bill` and
`test_reconcile_dispatches_to_the_bill_only_path_and_lands_on_the_same_residual`.

PG&E's specs pin one territory and carry no minimum bill, so they never reach
`Baseline.allowances` or `minimum_bill_line` — the two blocks SDG&E adds. A third test,
`test_the_two_paths_agree_on_the_sdge_charge_structure`, drives both paths over a synthetic
SDG&E month so those blocks are covered. **It asserts no amount**, only that the two paths
agree and that the two blocks were reached.

### Mutation measurements

Four mutations, all tripped, measured rather than assumed (`tests/golden_bills`, 125 tests):

| mutation | tests failed |
|---|---|
| bill the whole statement as one run — drop the per-run split | **14** — 12 of the 22 parity cases (6 of 11 fixtures, both tests), plus the 2 straddle refusals |
| read an absent event-adder kWh as 0 instead of raising | 1 (`test_tou_dr_p_cannot_be_reconciled_from_printed_buckets_at_all`) |
| allow a segment to straddle a rate change | 2 |
| read an omitted TOU period as 0 | 1 |

The first is the one that matters: collapsing the sub-period split is the single most
plausible way to make the bill-only path "work" on a straddling statement, and it is caught
by the golden bills themselves rather than by a hand-written assertion.

### Counts

- Full suite: **1,771 passed, 1 failed** (§4), from **1,711 passed, 0 failed** on `main` at
  the start of this session. **+61 tests.** Measured, not copied.
- `ruff check src/ tests/` clean; `ruff format` clean.

### Re-run commands

```bash
conda activate energy-advisor          # plain `python` is not on PATH
cd /home/cameron/repos/energy-advisor
git checkout m1a-bill-harness

PYTHONPATH=src python -m pytest -q                      # full suite (~2 min)
PYTHONPATH=src python -m pytest tests/golden_bills -q   # the gate, 125 tests
ruff check src/ tests/ && ruff format --check src/ tests/
```

The parity tests need the PG&E export in `data/` (gitignored). Without it they skip and
say so; every other test in this work needs no data at all.

---

## 4. ⚠ One failing test, and it is not this work's to fix

```
FAILED tests/report/test_web_engine.py::test_the_committed_bundle_matches_src
```

`scripts/build_web_engine.py` bundles `src/tariffs/bill.py` into `docs/engine.js`, and this
session changed that file. The drift test is doing exactly its job.

**It was not fixed here because `docs/` is owned by a parallel session** and regenerating
`docs/engine.js` would collide with that work. The fix is mechanical and belongs to
whoever merges:

```bash
PYTHONPATH=src python scripts/build_web_engine.py
```

Notes for that merge:

- `docs/case-study.json` records the engine bundle's digest and
  `tests/report/test_case_study.py` compares it to the shipped bundle, so after rebuilding
  the bundle the case study must be regenerated too
  (`PYTHONPATH=src python scripts/build_case_study.py`, which needs the gitignored `data/`).
  Until the bundle is rebuilt, that test passes, because nothing has moved *in `docs/`*.
- `src/tariffs/bucketed.py` is **deliberately not in `MODULES`**. The browser tool does not
  transcribe fixtures, so the bill-only path is not part of what it needs; bundling it would
  add code to the page that nothing there calls. If that changes, add it to `MODULES` in
  `scripts/build_web_engine.py` — and note that
  `test_every_third_party_import_in_the_bundle_is_a_package_the_page_loads` will then
  require nothing new, since it imports only stdlib, pydantic and local modules.
- The changes to `bill.py` are a pure extraction plus one new exception class. The browser's
  behaviour after a rebuild is identical: `compute_layer` computes what it computed before,
  which is why the eleven golden bills were green immediately after the refactor and before
  anything new existed.

---

## 5. What this does and does not claim

**Does:** the harness can reconcile an SDG&E statement from printed buckets alone; the two
paths are one charge layer, measured on real bills; every case printed buckets cannot reach
raises by name instead of guessing.

**Does not:** no SDG&E bill has been reconciled. Not one. Invariant 1 is unchanged — no San
Diego user is shown a dollar figure — and `report/recommend.py`'s `RECONCILED_UTILITIES`
gate is untouched and still refuses SDG&E.

**And one boundary worth stating plainly, because it is easy to overclaim:** the bill-only
path takes **SDG&E's own bucketing as given**. It tests this repo's rates and charge
structure. It cannot test `tou.rules` — the year-round super-off-peak window (whose
evidence is SDG&E's customer-facing publications rather than a located tariff sheet), the
weekend table, the `sdge_residential` holiday calendar. If our TOU rules were wrong, an
M1a reconciliation would still pass. **That is not a defect in the path; it is precisely
the line between M1a and M1b**, and it is the reason M1b still needs an export from the
same household. A green M1a does not retire the super-off-peak caveat in
`sdge_tou_dr1_delivery_2026-06-01.yaml`.

---

## 6. Next actions

1. **Unchanged and still the binding constraint:** one ordinary (non-solar, non-NEM) SDG&E
   residential statement. Three of them close M1a. The harness is now genuinely
   transcription-only — the claim `notes/m1_without_dad_2026-09.md` made about session 24's
   work was true of the interval path and false of the bill-only one, and that gap is what
   this session closed.
2. When asking, add the two items from §1b: prefer a period inside one rate vintage, and
   ask for the sub-period blocks if the statement spans a change.
3. Rebuild `docs/engine.js` after the parallel docs session lands (§4).
