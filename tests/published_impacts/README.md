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
| `sdge_2026-04_tou_dr1.yaml` | SDG&E's April 2026 rate-change alert: published figures, the derived quantities, and both the hand and engine measurements against the 4/1/2026 specs |
| `test_sdge_2026_04_tou_dr1.py` | the two tests above — a delivery point test and a generation feasibility test — plus the tier-boundary test |

## How weak is "weak"? Measured, not asserted

The generation envelope for the one fixture here is **$30.73–$122.31** against a **$4**
rounding band on the figure under test: the feasibility test **accepts 95.6% of the width it
could have rejected**, and `test_the_generation_envelope_is_too_wide_to_be_evidence` asserts
that in CI so the caveat cannot quietly fall out of a summary. Mutating the committed spec:
scaling every generation rate by 1/10 trips it; a 10x decimal shift on a single rate does not,
and neither does inverting the season map. **Infeasible would prove a spec wrong. Feasible is
close to no evidence at all** — never write it up as corroboration.

Two design rules the first draft got wrong, recorded so the next fixture does not repeat them:

1. **Take the envelope per month over every period**, not as (all-cheapest, all-dearest) with
   the ordering hard-coded. Swapping two rates in a spec leaves the achievable set identical;
   a hard-coded ordering reported that spec *infeasible*, i.e. issued this tier's one strong
   verdict with no evidence behind it.
2. **Bands come from the publisher's rounding.** A whole-dollar figure gives ±$0.50; a figure
   derived by subtracting two of them gives ±$2. The derived band must be *inside* the
   envelope, not just its midpoint.
