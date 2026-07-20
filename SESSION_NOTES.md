# Session notes

Running log of decisions made and decisions pending. Newest first.

## 2026-07-20 — Session 2 addendum (direction for next session)

Session-2 work **merged to main** (`2b19e28`, fast-forward). Cameron: dad's SDG&E bills
not available yet; asked whether to build CLI/API/Docker/deployment. **Decided NO** —
those are roadmap "Later" (gated behind the M5 demand verdict); building delivery infra
for one household with no validated demand is exactly what the roadmap guards against.
Instead, next session runs **two parallel, data-unblocked workstreams** (full detail in
HANDOFF.md "Plan for next session"):
- **A: Build M1 from public sources** — SDG&E Green Button parser + SDG&E residential
  schedule specs (TOU-DR1/2/-P, EV-TOU-5) + San Diego CCA generation overlay, all from
  public tariff sheets with citations. Only the reconciliation DoD is blocked (needs dad's
  bills); construction is not.
- **B: Finish PG&E for non-CARE [M2 prep]** — the engine already bills non-CARE everywhere
  except one gap: the standard (income-graduated) Base Services Charge in the 2026-03-01
  spec. Fill from the tariff sheet; verify FF/UUT are class-independent.

## 2026-07-20 — Session 2 (M0 polish + approximation cleanup)

Goal (Cameron): reconcile the remaining machine-readable bills, and resolve the flagged
approximations. Result: **8 of 8 text-readable statements now reconcile within ±$2**
(was 3), worst residual **+$0.21**. 36 tests green, ruff clean. README table has 8 rows.

### Engine change — intra-period rate-version splitting (NEW capability)
A single billing period can straddle a rate change, and **delivery and generation change
on different dates**. Added `_rate_subperiods` + `load_spec_versions`: `compute_layer`
now accepts a *list* of effective-dated versions and splits the period at the union of
season boundaries and per-layer effective dates. Backward compatible (a single spec still
works). `reconcile.py` loads all versions per layer.

**Rate-version map discovered (all derived from the bills, cited in specs):**
- E-TOU-C **delivery**: three winter versions —
  `≤2025-12-31` (Peak 0.48974 / off 0.45974 / BLC −0.10084, no BSC),
  `2026-01-01` (0.46460 / 0.43460 / −0.09566, no BSC),
  `2026-03-01` (0.39757 / 0.36757 / −0.08140 + BSC $0.19713/day, IGFC). CARE rates + PCIA
  (pre-2026 **0.00670**, 2026 **0.03679**) all on the bills.
- 3CE **generation**: winter rate changed **2026-02-15** (peak 0.15386→0.12572,
  off 0.12883→0.09930). The old gen spec was mislabeled `effective 2026-01-01`; **renamed
  to `_2026-02-15`** and an earlier `_2025-01-01` version added. The **02-15 date was
  derived from Cameron's interval data**: splitting the 01/28–02/26 period there reproduces
  the bill's split kWh (peak 75.168 / off 265.363) to within the ~0.3 kWh read residual.

### BUG FIXED — percent-surcharge double-count across same-season sub-periods
Surcharges (UUT, franchise fee) were scoped by *season tag*. When one season has two
sub-periods (a version change within winter, e.g. 3CE @ 02-15), the second run's surcharge
base summed the first run's charges too → 03-01 bill was +$4.41 (gen UUT $10.22 vs $5.97).
Fix: build each sub-period's lines in a local list and compute surcharges over just those.
Regression test added (`test_surcharge_scoped_per_subperiod_not_per_season`).

### RESOLVED — Generation Credit is now exact TOU (was flagged APPROX #4)
The PG&E "Generation Credit" for CCA customers is a TOU-weighted avoided generation rate.
Extended `PerKwhAdder` with optional TOU fields (`per_kwh_<season>_peak/_offpeak`) and
`amount()`. Least-squares fit across bills gives an **exact** winter decomposition
(predicts every winter bill to ≤$0.01): pre-2026 peak −0.16354 / off −0.13746; 2026 peak
−0.12705 / off −0.10030. **Summer stays a single-bill blend −0.12013** (only 06/28 exists;
can't separate peak/off yet — refine with a 2nd summer bill).

### Franchise Fee — improved + bounded, still flagged
Basis is **not cleanly recoverable** from the bills: FF is $0.02–0.39/sub-block and fits
no single base consistently (0.13–0.16% of energy in 2026, ~0.23% pre-2026, and no better
against pre-FF subtotal, PCIA+gen-credit, or 3CE generation). Modeled per-era as % of
energy; residual <$0.05/bill. Kept APPROXIMATE with citation. Revisit from the PG&E
franchise-fee tariff sheet if ever material.

### OPEN — Santa Cruz "UUT Adjustment": prior "phase-out" hypothesis is WRONG
With 8 bills (vs 2 last session), the net UUT does **not** trend to 0. Instead the
*adjustment itself* is **roughly constant ~$6.5/month** (−5.55 to −7.47), largely
independent of the gross UUT (which swings $6.2–$13.8 with usage). Net effective UUT is
0.3%–48.5% with no trend. Looks like a **near-fixed monthly UUT credit/cap/exemption**,
not a percentage or phase-out. Still not derivable from the bills. Handling unchanged:
**observed per-bill input** for reconciliation; mechanism UNVERIFIED. **Needs Cameron**:
does he know of a Santa Cruz UUT cap/exemption/rebate (esp. CARE-related)? Matters for the
M2 counterfactual (can't read an adjustment off a bill that doesn't exist).
Per-bill: 01/29 −6.58, 03/01 −7.47, 03/31 −6.58, 04/29 −6.49, 05/29 −6.28, 06/28 −6.71,
11/26 −5.55, 12/28 −6.09 (delivery+generation adjustment combined).

### OCR'd the 3 image bills — full 12-month history now reconciles (11/11 within ±$2)
Cameron chose to install OCR. Added tesseract 5.5.2 + poppler + pytesseract + pdf2image
to the conda env. OCR'd the 3 image statements (300 dpi): **08/27, 09/26, 10/28 2025**
(periods 08/02–10/26). These are summer/fall and revealed a richer rate history:
- **Two summer-2025 delivery rate versions** with a step on **2025-09-01**:
  ≤08/31 Peak 0.62569 / off 0.50269 / BLC −0.10301 (CARE 0.39142 / 0.31147 / −0.06695);
  09/01+ Peak 0.61457 / off 0.49157 / BLC −0.10084 (CARE 0.38507 / 0.30512 / −0.06555).
  The existing pre-2026 delivery spec was really the 09/01 version — **renamed to
  `_2025-09-01`** and a new **`_2025-01-01`** (early-summer) added.
- **3CE summer generation** 0.21021 / 0.13233 (constant Aug–Sep; the 09/01 PG&E step did
  not move 3CE). Added to the 3CE `_2025-01-01` spec.
- **Summer Generation Credit** TOU (delivery adder) peak −0.23395 / off −0.13206
  (least-squares fit across the 2025 summer sub-blocks, ≤$0.003).
- **California Climate Credit −$58.23** on the 10/28 statement (electric). PG&E folds it
  into the account-summary "Electric Adjustments −60.97" (= climate −58.23 + UUT adj
  −2.74). Modeled as an **observed adjustment** line (like the UUT adjustment), since it's
  a fixed regulatory credit, not usage-derived. For M2, model as a versioned semiannual
  (Apr/Oct) credit line.

The 2-column bill layout doesn't survive OCR into the extractor's single-flow regexes, so
these 3 fixtures were **hand-built from OCR and verified** (line items sum to each layer
total to the cent). The extractor skips them, so `--write` won't clobber them. All rates
transcribed from OCR are validated by the reconciliation gate itself (model vs OCR'd
totals): **08/27 +$0.16, 09/26 +$0.22, 10/28 +$0.21** — all PASS. Note 2025 summer gen
credit (peak 0.234) is much higher than 2026 summer (blend 0.120): PG&E generation/avoided
cost fell year-over-year (different version specs, expected).

### Extractor generalized for the pre-IGFC bill format
Older statements use a spaced hyphen/en-dash period separator (not " to ") and `$`-prefix
every line amount. Loosened the regexes; the self-check (line items must sum to layer
total) now passes for all 8 text bills. The **3 earliest (Aug–Oct 2025) are image-only**
(pypdf yields whitespace) → need OCR; **no OCR tooling is installed** (no tesseract/
poppler/pytesseract). Decision for Cameron: install OCR vs hand-enter line items vs skip.
Note: one Oct 2025 statement likely carries an **electric** Climate Credit (needs modeling
if OCR'd; the April CCC on this account was on GAS).

## 2026-07-19 — Session 1 (M0 kickoff)

### greenbutton parser — DONE (kickoff item 1), validated on the real export
- `src/greenbutton/` — `models.py` (canonical `IntervalSeries`, `MeterMeta`,
  `ParseReport`; pydantic; tz-aware `America/Los_Angeles`; PII stripped at the
  boundary) + `pge.py` (`parse_pge_interval_csv`). 13 tests, ruff clean.
- **The real interval export is HOURLY, not 15-min.** This meter only stores hourly
  (`00:00–00:59` rows). Fine for M0 — CA TOU periods are hour-aligned. If a 15-min
  meter shows up later the parser already infers 15-min correctly (tested).
- PG&E `END TIME` is the **inclusive last minute** (`00:00→00:59` = 60 min), so
  interval = `(END−START) mod 1440 + 1`, cross-checked against the modal start step.
- **kWh cross-check passed:** interval sums vs the 11 billing-summary periods agree to
  **within ~0.5 kWh** each (residual = meter-read-time vs calendar-day boundary; not a
  parser error). Year total 4522 kWh, coverage 0.9999, 9 intervals flagged estimated.

### MAJOR FINDING — the account is a CCA + CARE bill (from bill PDFs, 2 statements)
Read both bill PDFs (statements 2026-05-29 and 2026-06-28), full line-item detail.
The account is **not a vanilla bundled-PG&E TOU account**. It is:

- **PG&E electric schedule: E-TOU-C** — "Time-of-Use (Peak Pricing 4–9 p.m. Every
  Day)", RIN `USCA-PGXX-0102-0000`. Peak 16:00–21:00 every day; off-peak all else.
  Baseline Territory **T**, Heat Source **H (all-electric)**.
- **Generation is by a CCA: Central Coast Community Energy (3CE / "3Cchoice")**,
  schedule **MBRETCH1**. PG&E does delivery only. So M0 must model the
  delivery/generation split + PCIA + generation credit **now** — the CCA overlay the
  roadmap deferred to M1 is already required for Cameron's own bills.
- **CARE enrolled** (low-income discount, renew 2027-11-02) — a large line item on
  every bill (e.g. −$53.92). Must model to reconcile, but atypical for the eventual
  solar-shopper customer, so model as a **separable modifier**, not baked into rates.
- Local tax: **City of Santa Cruz Utility Users' Tax 8.5%** on both delivery and
  generation, plus a negative "UUT Adjustment" (mechanism not yet understood —
  UNVERIFIED), Franchise Fee Surcharge (delivery), Energy Commission Tax (generation).
- **New Base Services Charge** since March 2026 (income-graduated fixed charge;
  CARE ≈ $0.19713/day). Pre-March-2026 bills predate it → spec needs effective-dating
  inside the M0 window. Seasonal rates change **June 1** (summer) — also within window.

**Ground truth correction:** the earlier billing-summary CSV **COST** column is
unreliable (e.g. it showed $5.20 for the Oct period; the PDF monthly history shows
electric $113.97 for that statement). My earlier "$5.20 = climate credit" guess was
wrong — that was the CSV's bogus cost field. **Reconciliation targets must be the PDF
bill totals / line items, not the CSV COST.** kWh from the interval CSV still cross-
checks fine (that part of the CSV is good).

**Observed electric $ per statement (PDF monthly history; delivery+generation):**
8/27=76.10, 9/26=114.44, 10/28=113.97, 11/26=87.63, 12/28=79.86, 1/29=163.46,
3/01=176.22, 3/31=100.44, 4/29=96.54, 5/29=118.48, 6/28=86.18.

**Two bills with full line-item detail (candidate first golden bills, no climate credit):**
- Statement 2026-05-29, usage 04/28–05/27, 458.359 kWh: PG&E delivery $65.62 + 3CE gen
  $52.86 − adj = electric $118.48.
- Statement 2026-06-28, usage 05/28–06/25, 283.948 kWh (spans winter→summer 6/1):
  PG&E delivery $50.06 + 3CE gen $36.12 − adj = electric $86.18.

**Key observed rates (to seed the spec, cite the bill statement; cross-ref tariff sheet):**
- E-TOU-C delivery, full rates — Winter: Peak $0.39757, Off-Peak $0.36757; Summer
  (6/1+): Peak $0.52240, Off-Peak $0.39940. Baseline Credit −$0.08140/kWh on
  min(usage, allowance). Baseline allowance Territory T: winter 12.9 kWh/day, summer
  7.1 kWh/day. Base Services Charge (CARE) $0.19713/day.
- CARE effective delivery rates — Winter: Peak 0.24804, Off-Peak 0.22854, BLC −0.05291;
  Summer: Peak 0.32918, Off-Peak 0.24923, BLC −0.05291.
- PCIA (2018 vintage) ≈ $0.03679/kWh (consistent across periods). Generation Credit and
  Franchise Fee Surcharge present (rates to be derived). UUT 8.5%; UUT Adjustment TBD.
- 3CE MBRETCH1 generation — Winter: Peak $0.12572, Off-Peak $0.09930; Summer: Peak
  $0.19573, Off-Peak $0.09376. Energy Commission Tax ≈ $0.0003/kWh; UUT 8.5%.

### M0 DoD MET — last 3 PG&E bills reconciled within ±$2 (kickoff item 3 done)
Reconciliation harness (`report/reconcile.py`) + anonymized golden fixtures
(`tests/golden_bills/pge_*.yaml`) + printed line-item comparison + README accuracy table.
`scripts/extract_golden_bills.py` parses bill PDFs -> fixtures (self-check gated);
`scripts/reconcile_report.py` prints comparisons + regenerates the README table.
**Results (electric net):** 04-29 +$0.41, 05-29 +$0.06, 06-28 +$0.12 — all PASS. 29 tests, ruff clean.
- Only the **3 most recent** statements became fixtures. Pre-March-2026 bills (01-29,
  03-01, 12-28) and the March transition bill (03-31) have the **pre-IGFC structure**
  (no Base Services Charge) -> need an earlier E-TOU-C spec version; skipped for now.
- The **3 earliest** bills (Aug–Oct 2025) are **image-based PDFs** — pypdf gets only
  whitespace; need OCR. Outside the DoD window.
- **Climate Credit:** the April CCC on this account is **−$46.26 on GAS**, not electric;
  no electric CCC in the last-3 window, so M0 didn't need to model it. Electric CCC (if
  any) would be on an Oct statement (one of the image-based ones).
- Biggest single line residual: 04-29 Generation Credit +$0.29 (flat-seasonal approx vs
  the bill's TOU-weighted PG&E generation). Net still +$0.41. All sub-$2.

### RESULT — full CCA+CARE bill reconciled within $0.12 (kickoff item 2 done)
`tariffs/` schema + loader + pure billing function built and validated end-to-end:
- **Bill A** (stmt 2026-05-29, all winter): model $112.26 vs bill $112.20 — **Δ +$0.06**.
- **Bill B** (stmt 2026-06-28, spans winter→summer 6/1): model $79.59 vs $79.47 — **Δ +$0.12**.
Both **well within the ±$2 gate**, per layer: delivery Δ ≤$0.06, generation Δ ≤$0.06.
Residuals come from (a) the ~0.3 kWh read-boundary offset and (b) the flagged franchise-
fee approximation — both sub-dollar. UUT Adjustment supplied as an observed per-bill line
(see OPEN DECISION). This validates the delivery/generation layering, season proration,
baseline credit, CARE-discount derivation, PCIA, and the CCA generation-credit model.

### RECONCILIATION MAP — both bills reverse-engineered (evidence for the spec)
Validated against interval data + printed line items. Everything below is exact
(matches the bill to the cent) unless noted:
- **TOU split** (peak 16:00–21:00 every day) computed from intervals matches the bill's
  peak/off-peak kWh within ~0.3 kWh (same read-time boundary residual; ≈$0.25).
- **Base Services Charge** (CARE): $0.19713/day × billing days. ✓
- **Energy (full rates)** Winter: Peak 0.39757, Off 0.36757. Summer: Peak 0.52240,
  Off 0.39940. ✓
- **Baseline Credit** = min(usage, allowance) × −0.08140. Allowance = days ×
  {winter 12.9, summer 7.1} kWh/day (Territory T, all-electric). ✓
- **CARE Discount** = Σ_component (full_rate − CARE_rate) × kWh over peak/off/baseline-
  credit. Verified = −$53.92 on bill A to the cent. (CARE rates W: 0.24804/0.22854/
  −0.05291; S: 0.32918/0.24923/−0.05291.) ✓
- **PCIA (2018 vintage)** = $0.03679/kWh flat. ✓ (rock-solid across all 3 sub-periods)
- **Generation Credit (PG&E)** ≈ 0.1071/kWh winter, 0.1201/kWh summer (seasonal, likely
  TOU-weighted PG&E generation rate). Derive per season; cross-ref PG&E generation tariff.
- **3CE MBRETCH1 generation** W: Peak 0.12572, Off 0.09930. S: Peak 0.19573, Off 0.09376.
  + Energy Commission Tax ≈ $0.0003/kWh. ✓
- **Franchise Fee Surcharge**: small ($0.02–0.27); basis not cleanly derivable as a % of
  any single subtotal (~0.34–0.45% of energy). Model as small % adder, mark rate
  UNVERIFIED; residual is well under $2.
- **Gross UUT** = 8.5% × pre-tax subtotal (delivery and generation separately). ✓ exact.

### OPEN DECISION — Santa Cruz "UUT Adjustment" (dollar impact up to ~$6/bill)
The bills carry a **"Utility Users' Tax Adjustment"** that cancels most of the gross UUT,
**inconsistently**: bill A (stmt 5/29) net UUT ≈ 32% of gross (adj −$3.47 delivery /
−$2.81 gen); bill B (stmt 6/28) net UUT ≈ **0** (adj −$3.93 / −$2.78, ~100% cancel).
Effective UUT swung 2.7% → ~0% in one month. This is **not a per-kWh rate** — it looks
like a **retroactive municipal true-up / UUT phase-out** (net trending to 0). Web search
inconclusive; couldn't confirm a Santa Cruz UUT change.
**Handling (flagged, revisit):** compute gross UUT at 8.5% exactly; treat the *adjustment*
as a per-bill **observed** correction read from the golden fixture (not predicted), and
mark its mechanism UNVERIFIED. For the counterfactual optimizer (M2), hold net UUT at the
latest observed effective rate (~0) with a stated assumption. **Cameron: do you know of a
Santa Cruz UUT reduction/refund? If not, I'll leave it as an observed per-bill adjustment.**

### DECISION MADE — DST handling (flagged per kickoff; sub-dollar, TOU-neutral)
PG&E does **not** export true wall-clock local time across DST. What the real file does:
- **Fall-back (2025-11-02): 24 rows** for a 25-hour day — the two physical 01:00 hours
  are summed into one `01:00` reading. Policy: localize the lone `01:00` as PDT
  (earlier fold); the missing PST hour surfaces as exactly **one** expected-grid gap.
- **Spring-forward (2026-03-08): 23 rows** — file includes `02:00` (which doesn't exist
  in LA) and omits `03:00` (which does). Policy: `nonexistent='shift_forward'` maps the
  `02:00` label → `03:00`, giving a correct contiguous real-time sequence.

Both affected slots are early-morning super-off-peak, so at most ~1 hour of night
energy is misplaced per transition — **zero TOU impact** under current schedules.
**Revisit if** any schedule ever prices the 01:00–03:00 window specially, or for a
15-min meter (finer folds). Cameron: flag if you disagree with folding vs. gap.

### Done (scaffold)
- Read CLAUDE.md, ROADMAP.md, KICKOFF_PROMPT.md. Scope confirmed: **M0 only**.
- Scaffolded repo: flat package layout under `src/` (`greenbutton`, `tariffs`,
  `tariffs/specs`, `nem3`, `scenarios`, `uncertainty`, `report`), `pyproject.toml`
  (ruff + pytest config, `pythonpath=src`), `.gitignore`, README stub whose first
  section is the reconciliation-accuracy table placeholder.
- `.gitignore` excludes `data/`, `tests/golden_bills/raw/`, and `*.pdf` — the real
  PG&E data already sitting in `data/` (name, address, account #, bill PDFs) must
  never be committed.

### Data on hand (from `data/`, git-ignored)
- **Billing summaries, not interval data yet:** `pge_electric_billing_*.csv` (11
  monthly bills, kWh + $) and a gas equivalent. These are golden-bill *targets* for
  reconciliation (M0 item 3), not the 15-min interval input. The real Green Button
  interval export is still to be provided (per kickoff note).
- Two bill PDFs — presumably the itemized bills backing those summaries.

### Observations flagged for reconciliation (billing summary)
- Electric period **2025-09-25 → 2025-10-26: 436 kWh but only $5.20**; gas period
  **2026-03-31 → 2026-04-28: $0.00**. These align with PG&E applying the **California
  Climate Credit in April and October**. The bill engine must model the climate
  credit as a line item or reconciliation will miss by ~$30–60 in exactly those two
  months. Logged as a billing-mechanic decision point for the tariff-spec work.
- Account is an apartment (`APT A`), Santa Cruz — need to confirm the exact electric
  schedule (E-1 tiered vs. E-TOU-C vs. E-TOU-D) from the bill PDF before writing the
  spec. **Pending: confirm schedule from PDF.**

### Decisions pending (for Cameron)
1. **Confirm the 15-min interval Green Button export** will be provided so the parser
   can be validated against a real file (currently written to PG&E's documented
   format).
2. **Climate Credit handling** — model explicitly as a versioned line item (needs the
   credit amount + which schedules/months). Values are UNVERIFIED until you supply the
   tariff/credit figures.
3. **Electric schedule** for the Santa Cruz account (see above).

### Decisions made (defaults, reversible)
- Canonical interval series does **not** store PII (name/address). Metadata keeps
  utility, masked account (last 4), service id, unit, interval length, tz. Privacy is
  an invariant, so the parser strips PII at the boundary rather than downstream.
- Interval timestamps are stored as the **interval start**, tz-aware
  `America/Los_Angeles`. DST: spring-forward gap → the missing wall-clock hour must be
  absent (a present nonexistent time raises); fall-back duplicate hour resolved by
  monotonic-order fold inference.
