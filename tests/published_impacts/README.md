# tests/published_impacts — TIER 2. NOT golden bills. Never quote these in the ±$2 claim.

## What this tier is

Utility-published bill-impact figures from rate-change notices. Real dollar amounts,
published by the utility, for a **stated monthly kWh on a stated schedule**. Public
documents, so unlike `tests/golden_bills/` these fixtures are committable and run in CI
without a privacy review.

## What it is NOT, and why the separation is load-bearing

A golden bill is a real bill reproduced from **that same meter's real interval data for
that same period**, gated at ±$2/month. That gate is this product's trust artifact and its
marketing (CLAUDE.md invariant 1). These figures have **no meter, no period, and no
interval data**. They cannot enter that number. A fixture here never counts toward the
golden-bill pass rate and is never cited in a reconciliation claim.

## The load-shape problem, and why these are FEASIBILITY tests not reproduction tests

A published figure states "$X for N kWh/month on schedule S" and **does not state how that
N kWh distributes across TOU periods**. The bill depends entirely on that distribution —
on SDG&E TOU-DR1 the on-peak and super-off-peak generation rates differ by ~11x. So the
figure cannot be reproduced; it can only be tested for consistency.

The rigorous form is a feasibility question:

> Does there exist a non-negative allocation of N kWh across the schedule's TOU periods,
> summing to N, that this spec prices at the published figure?

- **Infeasible => the spec is provably wrong.** A decimal shift, a wrong season map, a
  missing NBC or a missing fixed charge pushes the achievable interval off the figure.
- **Feasible => the spec is not contradicted.** Weaker. Also returns the implied
  allocation, which is itself a sanity read (is the implied on-peak share plausible?).

This makes **no load-shape assumption**, which is the point. A flat-profile point estimate
would assume one, and that is the thing CLAUDE.md invariant 6 exists to prevent.

## Invariant 6 note — recorded so it is a decision, not drift

Invariant 6 bans modeled load profiles from *product computations*. A test that constructs
a degenerate interval series to probe a spec's arithmetic is not a customer-facing
computation and does not claim to be. The boundary: nothing in this directory may be
imported by `src/`, and no figure here may appear in a user-facing output.

## Per-utility usability

| Source | Schedule named? | Usable? |
|---|---|---|
| SDG&E rate-change alert | **yes** — "400 kWh/month on schedule TOU-DR1" | yes, as a feasibility test |
| PG&E electric rate advisory | **no** — "average residential bill" across all residential schedules, territories and load shapes | **no.** Not reproducible from any single spec. Kept for the climate-credit delta and the average-rate figure only |

The PG&E asymmetry is the main limitation of this corpus: PG&E publishes a class average,
SDG&E publishes a schedule. Only the schedule-specific form supports a feasibility test.

## What is in here

| File | What it is |
|---|---|
| `sdge_2026-01_tou_dr1.yaml` | SDG&E's January 2026 rate alert (AL 4757-E), against the 1/1/2026 specs |
| `sdge_2026-04_tou_dr1.yaml` | SDG&E's April 2026 rate alert (AL 4791-E), against the 4/1/2026 specs |
| `sdge_2026-06_tou_dr1.yaml` | SDG&E's June 2026 rate alert (AL 4843-E, a FERC-driven interim decrease), against the 6/1/2026 specs |
| `pge_2026-03_class_average.yaml` | PG&E's March 2026 advisory. **Non-testable**, marked so in its own header — a residential class average with no schedule and no territory. Provenance only |
| `tier2.py` | the shared probe machinery: a `Quarter` is one alert plus its two spec layers. Fixtures are found by **glob**, so one added without a test fails loudly |
| `test_sdge_tou_dr1_quarters.py` | every assertion, parameterized over all three SDG&E quarters, plus the tier-boundary test |

Each SDG&E fixture carries a `vintage:` field; that is what the harness reads to pick the spec
pair and the fixture's own `current_*` column. Jan/Apr/Jun are the only 2026 SDG&E alerts —
`sdge.com/rate-alerts` was checked directly and no alert was issued for the 8/1 vintage change.

⚠ **Three quarters of delivery evidence, but only TWO of generation.** The 6/1/2026 filing moved
the UDC and left EECC untouched, so the April and June generation layers are the same numbers
and June's generation assertions re-test April's spec. Pinned by
`test_the_april_and_june_generation_envelopes_are_identical` so "three quarters" cannot quietly
become an overstatement.

## How weak is "weak"? Measured, not asserted

The generation envelope is **$30.73–$122.31** non-CARE (all three quarters agree to a cent)
against a **$4** rounding band on the figure under test: the feasibility test **accepts 95.6%
(93.3% under CARE) of the width it
could have rejected**, and `test_the_generation_envelope_is_too_wide_to_be_evidence` asserts
that in CI so the caveat cannot quietly fall out of a summary. Mutating the committed spec:
scaling every generation rate by 1/10 trips it; a 10x decimal shift on a single rate does not,
and neither does inverting the season map. **Infeasible would prove a spec wrong. Feasible is
close to no evidence at all** — never write it up as corroboration.

Three design rules earlier drafts got wrong, recorded so the next fixture does not repeat them:

1. **Take the envelope per month over every period**, not as (all-cheapest, all-dearest) with
   the ordering hard-coded. Swapping two rates in a spec leaves the achievable set identical;
   a hard-coded ordering reported that spec *infeasible*, i.e. issued this tier's one strong
   verdict with no evidence behind it.
2. **Bands come from the publisher's rounding.** A whole-dollar figure gives ±$0.50; a figure
   derived by subtracting two of them gives ±$2. The derived band must be *inside* the
   envelope, not just its midpoint.
3. **Every unstated parameter gets the feasibility treatment, not just the obvious one.** The
   alert states neither the TOU allocation nor the **baseline territory**. Session 25 treated
   the first as unstated and the second as identified, because in April exactly one territory
   landed inside the rounding band. Across all three quarters no single territory does — June
   picks `coastal_all_electric`, January picks none — so that was one quarter's arithmetic
   read as a general fact. A parameter the document does not state is not pinned by a figure
   that happens to round its way.

## What replaced the territory point test

Ordered by how much a mutation has to move a spec before each one notices:

| assertion | strength |
|---|---|
| which territories land inside the ±$0.50 band, **cell by cell** | strongest — catches a **0.3%** energy-rate change ($0.40/month) |
| the vintage-over-vintage **delta** matches the published change | sharp, and needs **no territory at all** — differencing cancels it |
| the two nearest territories are always the coastal pair | catches allowance-table errors the delta cannot |
| the PCIA exclusion is load-bearing | order-of-magnitude margin in all three quarters |
| **some** territory prices to the published figure (±$1.00) | weakest of the delivery set; survives 5 of 7 mutations |
| generation feasibility | near-zero information by construction — see above |

The delta is the one worth understanding: the levels span $4.22–$4.31 across the eight
territories, but the *change* between two vintages agrees across all of them to within a few
cents, because the allowances are identical in both specs and only the rates moved. So the
delta tests the filing rather than the climate zone, which is exactly what makes it immune to
the ambiguity that retired the point test.
