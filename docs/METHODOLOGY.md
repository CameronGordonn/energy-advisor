# Methodology and case study

_How this engine computes a California electricity bill, how accurate it is against real
bills, and one household worked end to end — including the parts that are still assumptions._

This document is the M4 deliverable. It is written to be checkable: every dollar figure
below is produced by a script in this repo, and every rate behind it traces to a published
tariff sheet. Where something is fitted, assumed, or unverified, it says so in the same
sentence as the number.

---

## 1. The claim, and the one number that backs it

Most consumer-facing energy calculators cannot tell you whether they would have reproduced
your last bill, because they never try. They price a modeled load profile against a
simplified rate, and the error is invisible — it is absorbed into a "typical savings"
headline that has no residual to inspect.

This engine takes the opposite constraint as its foundation:

> **No feature that produces a dollar figure ships until the underlying bill engine
> reproduces real utility bills from real interval data within ±$2/month.**

Against one household's twelve months of PG&E statements, using that household's own
hourly interval data:

| | |
|---|---|
| Statements reconciled | **11 of 11** within ±$2 |
| Worst single-statement error | **+$0.22** (0.43% of that bill) |
| Mean error | **+$0.14** |
| Total across all 11 statements | **$1,085.81 modeled vs $1,084.26 actual — 0.14% high** |

The full per-statement table is in the [README](../README.md); the line-item comparison that
produces it is `scripts/reconcile_report.py`.

**The residual is one-sided, and that is not an accident.** Every one of the eleven errors is
positive — the model is consistently a little high. Two known causes, both bounded and both
recorded:

1. **Meter-read boundary.** Interval sums and the utility's billed kWh differ by roughly
   0.3 kWh per period, because a billing period ends at a meter read time, not at a calendar
   day boundary. At residential rates that is about $0.10–$0.25 — most of the residual.
2. **The 2025-vintage franchise fee** is still modeled as a percent-of-energy approximation.
   (The 2026 specs use the exact per-kWh rate from Schedule E-FFS; see §5.) On the two
   August/September 2025 statements this shows up as a visible +$0.04–$0.05 on that single
   line.

A model that was curve-fitted would have a residual centered on zero. This one has a small,
explained, one-directional bias, which is the signature you want: the errors are physical,
not tuned away.

---

## 2. Engine design

### 2.1 The bill is a pure function

```
compute_bill(interval_series, [tariff_spec_versions], billing_period) -> itemized Bill
```

No I/O, no network, no hidden state, deterministic. Every utility-specific irregularity
lives in either a parser or a spec file, never in the billing logic. This is what makes the
counterfactual honest: re-simulating the household on a different schedule is the *same
function* with a different spec, not a different code path with different simplifications.

Bills are computed in **layers** — `delivery`, `generation`, `adjustment` — because that is
how California actually bills: the utility delivers, and a Community Choice Aggregator may
supply the generation. Modeling the layers separately is what makes the CCA question in §4
answerable at all.

### 2.2 Tariff specs are data, with citations

Each schedule is a versioned YAML file under `src/tariffs/specs/`, carrying an effective
date and a `citation` field naming the exact Cal. P.U.C. sheet number and advice letter each
number came from. **A spec without a citation is invalid.** A value that is not known is
written `UNVERIFIED`, and the loader *raises* rather than defaulting — so an unfinished spec
cannot silently produce a plausible-looking dollar figure.

That rule has already paid for itself twice:

- Schedule **TOU-DR-P** is committed and deliberately does not load. Its period windows are
  not sourced, and it carries a **RYU Event Period Adder of $1.16/kWh** on event days that
  the engine has no concept for. Defaulting the event count to zero would make TOU-DR-P look
  like the cheapest plan on the board — a free lunch produced entirely by an unmodeled
  charge. It is excluded, and the report says why.
- Committing a genuinely incomplete spec exposed a real defect: the loader was validating
  *every* YAML in the directory before filtering by schedule, so one half-finished SDG&E
  spec broke all eleven PG&E golden bills. Filtering now happens on the raw keys before the
  UNVERIFIED gate. That bug was only visible because incomplete specs ship.

### 2.3 Rate versions split *inside* a billing period

A single statement routinely straddles a rate change, and **delivery and generation change
on different dates**. `compute_layer` accepts a list of effective-dated versions and splits
the period at the union of season boundaries and per-layer effective dates.

This is not hypothetical precision. In the case-study year: PG&E delivery changed on
2025-09-01, 2026-01-01 and 2026-03-01 (the last introducing an income-graduated fixed
charge), the summer season begins 2026-06-01, and the CCA's generation rate changed on
2026-02-15 — a date that was *derived from the household's interval data* by finding the
split point that reproduces the statement's printed peak/off-peak kWh, then confirmed
against the CCA's published rate sheet.

### 2.4 Time-of-use periods are N-period, day-typed and month-conditional

`TouDef` is an ordered, **first-match-wins** rule list — `{period, hours, days, months}` plus
a `default_period`. This is required by SDG&E, whose residential schedules have three periods
(on / off / super-off-peak), different weekday and weekend windows, and month-conditional
carve-outs. Period resolution is precomputed as a 12 × 2 × 24 table, so day-type awareness
costs nothing per interval.

**Holidays are priced as weekend days, and the two utilities do not agree on which days
those are.** Both name the same eight holidays, but PG&E uses federal "legally observed"
rules (Saturday → Friday, Sunday → Monday) while SDG&E Electric Rule 1 says *"When a Holiday
falls on Sunday, the following Monday shall be defined as a Holiday. No change will be made
for Holidays falling on Saturday."* Concretely: 2026-07-04 falls on a Saturday, so a PG&E
customer gets Friday 7/3 priced off-peak and an SDG&E customer gets nothing. Each calendar is
named and cited; an unknown calendar raises at spec load.

### 2.5 Two structures that look like schema gaps and are not

**Tiered rates (PG&E E-1).** Flattening tiers to an average would destroy the marginal price
signal the optimizer exists to compare. Instead E-1 is expressed in the existing
baseline-credit machinery, which is an **algebraic identity, not an approximation**:

```
tier1·min(u,B) + tier2·max(0,u−B)  ==  tier2·u + (tier1−tier2)·min(u,B)
```

and `0.32561 − 0.40702 = −0.08141` is exactly the credit. PG&E's own unbundling confirms
this is the tariff's real structure — the tier difference *is* a named component, the
Conservation Incentive Adjustment. Limit recorded in-spec: this handles exactly two distinct
tier prices. A genuine third price needs a real `tiers` field.

**Non-bypassable charges.** On SDG&E these are already inside the published energy rate, so
the netting logic *carves them out* of the offsettable subtotal rather than adding a line —
no double count. A `volumetric` flag on each line item decides at construction time what a
credit is allowed to offset.

---

## 3. Case study: a Santa Cruz PG&E household

**Disclosure.** This is the author's own account, published deliberately and with
attribution. Anonymizing it would be theater — the repository carries my name — and blurring
the dates or amounts would destroy the one property that makes the reconciliation worth
reading, which is that a third party can check the rates against the tariff sheets for
themselves. The account is CARE-enrolled (California's low-income rate discount), which is
disclosed here because the CARE modeling in §3.2 is one of the more interesting technical
results and cannot be presented honestly with the household's rate class hidden.

### 3.1 The account

| | |
|---|---|
| Utility / schedule | PG&E, **E-TOU-C** (peak 4–9 p.m. every day) |
| Generation | **Central Coast Community Energy (3CE)**, schedule MBRETCH1 — a CCA, so PG&E does delivery only |
| Rate class | **CARE** (low-income discount) |
| Baseline territory | T, all-electric |
| Local tax | City of Santa Cruz Utility Users' Tax, 8.5% on both layers |
| Meter data | hourly (not 15-minute) — this meter does not store finer |
| Analysis window | 2025-08-02 → 2026-06-25 — **4,345 kWh over 328 days** |

This is not a vanilla bundled account, and that turned out to be the point. The CCA overlay,
PCIA, generation credit and CARE discount that the roadmap deferred to a later milestone were
all required immediately, just to reproduce the first bill.

### 3.2 CARE rates are derived, and then independently checked

PG&E does not print residential CARE rates in its tariff book. They were solved from the
CARE rates appearing on the household's own statements:

```
care_energy   = 0.65 × standard − 0.01038
care_baseline = 0.65 × standard
```

Two parameters, five independent constraints, fitting to ≤1e-5. The question is whether that
relationship is a coincidence of one schedule or a real statewide rule. Three checks say it
is real:

1. Applying it to E-1's two *printed* tier rates yields a CARE tier differential of
   **−0.05291**, which is exactly the CARE Baseline Credit printed on the E-TOU-C statements
   — a different schedule, a number not used in the fit.
2. SDG&E, unlike PG&E, prints its CARE tables explicitly, and they state **"CARE Discount
   35%"** — confirming 0.65 as a statewide factor.
3. On SDG&E the split is not merely consistent but *exact*: delivery and generation layers
   re-sum to SDG&E's own published Total Electric Rate **and** Total Adjusted CARE Rate on
   all twelve season × period cells.

It remains an assumption on PG&E. `rate_optimizer.py --no-care` produces the fully
tariff-grounded ranking with no derived rate in it.

### 3.3 The result: switch — but not for the reason anyone expects

Re-simulating the same 4,345 kWh of real intervals under every eligible schedule, at rates
in effect today, with the CCA on and off:

```
1  E-TOU-C + PG&E               933.50/yr    −170.72   <- recommended
2  E-1 (tiered) + PG&E          990.57/yr    −113.65
3  E-TOU-D + PG&E              1038.50/yr     −65.72
4  E-TOU-C + 3CE               1104.22/yr      +0.00   <- current
5  E-1 (tiered) + 3CE          1160.91/yr     +56.69
6  E-TOU-D + 3CE               1208.80/yr    +104.58
```

(Two EV-only schedules are **excluded, not merely flagged**, because this household has no
plug-in vehicle. Flagging an ineligible plan still lets it become the headline; filtering
cannot.)

**The $170.72/yr saving has almost nothing to do with the rate schedule.** The recommended
plan is the schedule the household is already on. The entire saving comes from *leaving the
CCA*, and it decomposes cleanly:

| component | annual |
|---|---:|
| Power Charge Indifference Adjustment (2018 vintage) | **+$159.88** |
| Utility Users' Tax levied on that PCIA | +$13.59 |
| Franchise fee | +$2.54 |
| 3CE generation being cheaper than PG&E's | −$4.85 |

The mechanism is checkable on the sheets: a **2018-vintage** CCA customer pays a PCIA of
**0.03679/kWh**, while the **2026 bundled** PCIA is **−0.01011** — a credit. That ~4.7¢/kWh
gap is larger than the CCA's generation discount, so the CCA has quietly become the more
expensive option for this specific vintage. Nothing about the household's *usage* is
unusual; the finding is entirely an artifact of when service started, and no generic
calculator surfaces it because generic calculators do not model PCIA vintages.

### 3.4 What would have to be true for this to be wrong

Reporting a recommendation without its failure conditions is the thing this project exists
not to do. So:

- **The saving is not immediate.** PG&E Rules 22.1/23.1 require **six months' advance
  notice** to elect bundled service, with **Transitional Bundled Service** (Schedule TBCC,
  short-term market prices) in the interim. A saving realized months later, after an unpriced
  TBS window, is not the annual figure above. This caveat is printed in the report itself,
  not just here.
- **3Cflex is unpriced.** The CCA's discount product is 5.264¢/kWh cheaper than the default
  3Cchoice modeled here. Staying on the CCA and switching products is a plausible option this
  engine cannot currently rank.
- **Rates are a snapshot.** No escalation, no pending rate cases. PCIA vintages are re-set
  annually; the gap that drives this result can narrow.
- **The ranking is robust to the sensitivity tests run.** E-1 overtakes E-TOU-C only if
  evening (4–9 p.m.) usage grew 353%, or 132% as a load-neutral shift. E-TOU-D never
  overtakes it on a load-neutral shift at any tested magnitude.
- **The largest single driver between *schedules* is the baseline credit**, which E-TOU-C
  and E-1 have and E-TOU-D does not — not the peak/off-peak spread most rate advice focuses
  on.

### 3.5 The unverified assumption, and why it cannot change the answer

The statements carry a **"Utility Users' Tax Adjustment"** — a municipal credit that cancels
most of the gross 8.5% UUT, and whose mechanism is not derivable from the bills and could not
be confirmed from public sources. Five candidate mechanisms were fitted across all eleven
statements; a **fixed credit of $0.21649 per billing day** had the tightest fit (coefficient
of variation 0.080, versus 0.207 for per-kWh and 0.330 for a fraction of the net bill).

That is adopted, and its mechanism is still marked UNVERIFIED. What makes it safe is not the
fit quality but the *shape*: a per-day credit is schedule-independent, so it adds the same
constant to every candidate plan and cannot reorder a ranking. The optimizer does not assert
this — it **re-ranks under all three rival mechanisms and prints all three orders**, which
are identical. An assumption you cannot verify should be handled by demonstrating it does not
matter, not by arguing it is probably right.

### 3.6 The cross-check that is still missing

M2's definition of done asks for a comparison against the utility's own free rate-comparison
tool. It could not be completed: PG&E's Rate Plan Comparison is behind an account login, and
for this account it returns *"This account has no service agreement eligible for rate
enrollment"* — most likely because generation is with a CCA. The harness is built and waiting
(`--pge-comparison FILE`), and the report prints the exact steps to close it. It is listed as
open rather than quietly dropped.

Four cross-checks that *are* complete:

- Every rate traces to a Cal. P.U.C. sheet, and the unbundled components sum to the printed
  total rate **exactly** on all four schedules — an arithmetic check the utility's own sheet
  must pass.
- The E-TOU-C generation credit **derived from the tariff** (−0.12699 / −0.10031) reproduces
  the value independently least-squares-fitted from the bills (−0.12705 / −0.10030) to 6e-05.
  This is the strongest evidence that M0 was not curve-fitting: two independent routes to the
  same number.
- 3CE's published rate sheet reproduces the bill-derived MBRETCH1 rates exactly, and its
  2026-02-15 effective date matches the changeover date derived from interval data.
- The E-TOU-C leg of the ranking is the same engine that reproduces all eleven statements
  within $0.22.

---

## 4. Findings a generic calculator would miss

These came out of building the engine, not out of looking for marketing copy. Each is
checkable from public documents.

**1. On SDG&E, the nine-year NEM 3.0 vintage lock-in is currently worth nothing.**
Export rates under the Net Billing Tariff lock for nine years by application vintage, and the
standard installer pitch is to sign before rates drop. SDG&E's published NBT2025, NBT2026 and
current-year export tables were parsed in full and compared cell by cell: they are
**byte-identical for every overlapping year** — 0.0 maximum absolute difference across 23,040
cells. On SDG&E today, "lock in before rates drop" has no dollars behind it. This is the
opposite of the PG&E vintage story the pitch is borrowed from.

**2. Export rates rise within a locked vintage, so treating a lock as a flat number is
wrong.** The same tables show a 2026 mean full export rate of 0.0883 rising to 0.1432 by
2035. The lock fixes a *576-values-per-year schedule*, not a constant. Code that models a
locked vintage as one number misprices every year after the first.

**3. On SDG&E EV-TOU-5, roughly 45% of the super-off-peak delivery charge is
non-bypassable.** That schedule collapses its super-off-peak distribution charge (0.04114
versus 0.31711 elsewhere) but does **not** discount the non-bypassable charges. So in the
window a battery or EV actually charges in, 0.02099 of the 0.04705 total is a charge no
export can ever offset — against about 6.5% in the schedule's other windows. A calculator
that nets exports against the headline delivery rate overstates the value of shifting imports
into super-off-peak on this schedule by roughly 2×.

**4. On SDG&E TOU-DR1, 100% of the time-of-use price signal lives in the generation layer.**
The delivery (UDC) total is 0.32948 for *every* period in *both* seasons — perfectly flat.
All of the summer on-peak-to-super-off-peak spread (0.30799/kWh) is in the generation
component. Any tool that approximates generation from delivery — a tempting shortcut, since
delivery rates are easier to obtain — produces a flat price signal and systematically
understates every load-shift and battery-arbitrage conclusion. This engine made exactly that
mistake internally before the generation layer was authored, and the correction was large:
a hand-entered super-off-peak price of 0.22 against a real total of **0.37660**, a 71%
understatement of the cost of importing in precisely the hour a battery charges — an error
biased toward recommending the battery.

**5. A perfect-foresight optimizer can settle *worse* than a dumb controller.** The battery
module always reports both a greedy time-of-use controller and a cvxpy linear program. The LP
optimizes a marginal-price proxy; actual dollars come from the Net Billing Tariff settlement,
whose export credit caps and non-bypassable floor the LP does not see. Which one wins in
settled dollars is a per-case result, not a fixed ordering. Reporting only the LP — labeling
it a "theoretical maximum" — would overstate achievable savings on some configurations and
understate them on others.

---

## 5. What is still assumed, approximate, or unknown

Presented in full, because a methodology writeup that lists only its strengths is marketing.

**Blocked on data, not on code.** Two milestones have complete, tested engines whose
definitions of done cannot be demonstrated:

- The **SDG&E reconciliation** needs three real SDG&E bills. The specs are tariff-exact and
  the layers re-sum to SDG&E's published totals, but no household is currently able to supply
  bills or a Green Button export.
- The **NEM 3.0 payback** needs one real household with solar/export interval data. None
  exists. The demonstration driver therefore runs on a **clearly labeled synthetic load**,
  and for that reason **no payback figure from it appears in this document.** The rates, the
  non-bypassable charge set and the ACC export tables it uses are all real and cited; the
  load is not, and a payback number computed on a fabricated load is exactly the kind of
  figure that survives out of context. The engine is done; the claim is not.

**Assumptions carried into published numbers.**

- PG&E CARE rates are derived, not printed (§3.2). `--no-care` removes them.
- The Santa Cruz UUT Adjustment mechanism is unverified (§3.5), handled by demonstrating
  ranking-invariance.
- The SDG&E super-off-peak window was extended from March/April-only to year-round effective
  2026-05-01. This is sourced from **SDG&E's own customer-facing publications** and
  corroborated by contemporaneous local news coverage; the superseding advice letter and
  revised Cal. P.U.C. sheet were **not located**. Any spec vintage effective before
  2026-05-01 must restore the March/April restriction.

**Known approximations, all sub-$0.05 per bill.**

- The 2025-vintage franchise fee uses a percent-of-energy approximation; 2026 specs use the
  exact per-kWh rate from Schedule E-FFS.
- The 2025 summer generation credit is bill-fitted from a single summer sub-period; the 2026
  one is tariff-exact.
- The California Climate Credit is modeled as an observed per-bill line rather than a
  versioned semiannual credit.
- The California Energy Commission surcharge is asserted on PG&E specs and **deliberately not
  asserted either way** on SDG&E, whose rate tables show no such column. Adding it unsourced
  would break the layer-identity test.

**Schema limits.** `Rate` has only `standard` and `care` variants, so FERA and the
affordable-housing rate class are not modelable. Per-kWh adders have no CARE variant. There
is no `tiers` concept (see §2.5 for why that is currently correct).

**Modeling choices with dollar impact are surfaced, not chosen silently.** Netting order,
true-up handling and baseline allowances are stated as decisions with their consequences.
SDG&E baseline allowances are per climate zone, so `territory` must be supplied at bill time
and omitting it **raises** rather than defaulting — a wrong zone silently mis-sizes the
largest credit on a California bill.

---

## 6. Reproducing this

```bash
conda env create -f environment.yml && conda activate energy-advisor
pytest                                              # 719 tests

PYTHONPATH=src python scripts/reconcile_report.py   # the 11 line-item comparisons
PYTHONPATH=src python scripts/rate_optimizer.py     # ranking, why, sensitivity, assumption audit
PYTHONPATH=src python scripts/nem3_report.py        # NEM 3.0 engine (real rates, synthetic load)
```

The golden-bill reconciliation is the merge gate: nothing touching `src/tariffs/` or
`src/nem3/` lands without all eleven statements still green. Real interval exports and bill
PDFs are gitignored and never committed; the committed fixtures carry no name, address or
account number.
