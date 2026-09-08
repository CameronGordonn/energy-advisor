# Session notes

Running log of decisions made and decisions pending. Newest first.

## 2026-09-07 — Session 8 (M4 published; SDG&E's earlier 2026 rate vintages)

Committed `8f45746` on `session-4-nperiod-tou-m2` (not pushed, not merged to main).

**331 tests green (was 166, +165 — mostly parametrization across four vintages), ruff
clean, 11/11 PG&E golden bills still reconcile with byte-identical residuals** (worst
+$0.22). Took HANDOFF next-actions #1 and #2.

### DONE — next-action #1: the M4 writeup is published, closing M4's DoD
`docs/index.html` is live at
https://claude.ai/code/artifact/26900439-4401-4b57-a57a-5bc3dfa43fb2 — **private until
Cameron shares it from the page's share menu.** Publishing was allowed this session; the
session-7 permission block did not recur. GitHub Pages was NOT used and remains available
as a second rail: the repo has **no git remote configured**, so that path would mean
creating and pushing a GitHub repo, which is a separate outward-facing decision and was
not taken unasked.
Before publishing, the page's numbers were re-verified against a live run rather than
trusted: all eleven rows, the +$0.22 worst case and the $1,084.26 / $1,085.81 totals match
`reconcile_report.py` exactly. Test count refreshed 166 -> 331 in `docs/index.html`,
`docs/METHODOLOGY.md` and README, and the artifact republished to the same URL.

### DONE — next-action #2: SDG&E TOU-DR1 1/1/2026 and 4/1/2026, both layers
Sources: SDG&E's published "Total Rates Table" and matching "-CARE Total Rates Table"
PDFs for each date (retrieved 2026-09-07), text-extracted locally with poppler rather
than paraphrased. Every one of the 24 new cells reconstructs SDG&E's **printed** Total
Electric Rate and Total Adjusted CARE Rate, on the same layer-identity gate the 6/1
vintage passes — e.g. 1/1 summer on-peak `0.65 x (0.34101 - 0.00864) + 0.65 x 0.34962 =
0.44329`, the printed figure. New gate file `tests/tariffs/test_sdge_vintages.py`; the
NBC list in `test_sdge_layers.py` was extended to cover the new delivery specs.

### DECISION — FOUR vintages, not three: rate dates and window dates are different things
Surfaced rather than chosen silently, per CLAUDE.md. Rates changed 1/1, 4/1 and 6/1, but
the weekday 10:00-14:00 super-off-peak window went **year-round on 2026-05-01** — and
**SDG&E published no 5/1/2026 rate table** (verified: that URL in the series returns HTTP
404). So a *period-definition* change lands in the middle of a *rate* vintage. Options:
  (a) **CHOSEN** — split the 4/1 rate vintage into two spec versions: 4/1 with the
      pre-change March/April window (governs April) and 5/1 with the year-round window
      and the same rates (governs May). Costs one duplicated rate block, made explicit.
  (b) Put the year-round window on the 4/1 spec. Numerically this happens to be right for
      every day that spec governs (April: the two rules agree; May: year-round is correct)
      — but a citation-bearing file would then assert a period definition that was not in
      force on its own effective date, and any later-inserted vintage would silently break.
  (c) Let the 4/1 spec's March/April window govern May too. Simply wrong: it prices
      weekday 10:00-14:00 in May 2026 as OFF-PEAK.
Dollar impact of (c): four hours a day across ~21 May weekdays at the off-peak/super-off-peak
EECC spread of `0.12853 - 0.04121 = 0.08732/kWh` — on the order of $7/month for a 1 kW
daytime draw, and materially more for anything deliberately charging a battery there.
(a) was taken because specs in this repo are transcriptions of a *dated tariff state*.

### ⭐ FINDING — delivery and generation change on DIFFERENT dates
EECC moved on 4/1 and then held: the 4/1 and 6/1 generation tables are identical. The
6/1/2026 filing moved **delivery only** (UDC Total 0.34061 -> 0.32948, baseline credit
(0.10892) -> (0.10663)). A tool that models "the SDG&E rate changed on 6/1" as a single
event misprices one layer or the other for every bill spanning that date. The engine
already versions layers independently — this is the first case that actually exercises it,
and it is pinned by `test_generation_held_across_the_june_delivery_change`.

### CORRECTED — the "superseded" PCIA values were not an error
The 6/1 spec headers recorded that an earlier retrieval read PCIA 2018 `0.03662` / 2026
`0.04977` and treated those as superseded by the 6/1 sheet's `0.03670` / `0.04987`. They
are in fact **the 1/1/2026 sheet's values**, correct for that vintage, and are now
committed in `sdge_tou_dr1_generation_2026-01-01.yaml` with the full table. Both 6/1 spec
headers were corrected to say so. Nothing was mispriced (PCIA is CCA-only and unbilled by
these bundled specs), but the note had recorded a transcription error that never happened.
Also confirmed: the NBC component set (PPP 0.01515 / ND 0.00000 / CTC (0.00007) /
WF-NBC 0.00591 = 0.02099) and the Base Services Charge (0.79343 / CARE 0.19713) are
unchanged across all four vintages, and the UDC total stays period- and season-flat on
every one of them — so 100% of TOU-DR1's TOU price signal remains in generation.

### CONSEQUENCE — `scripts/nem3_report.py` now runs CALENDAR 2026
Session 6 had to use 2026-06-01 .. 2027-05-31 because that was the only committed vintage
and `marginal_energy_price` refuses to price a date no spec covers. The window is now
2026-01-01 .. 2026-12-31 and crosses four rate versions per layer. Jan-April are priced by
vintages where weekday 10:00-14:00 is *not* super-off-peak, so the battery sees the real
changing daytime price instead of one year's rule projected backwards.
New output (bundled, standard, coastal_basic, **synthetic** 6,264 kWh load, 5 kW):
baseline $3,052/yr; solar only $1,867 (save $1,186, 8.9 yr); +battery greedy $514 (save
$2,539, 7.4 yr); LP $436 (save $2,617, 7.2 yr); NBC floor $86/yr. **The load is still
synthetic, so these figures stay out of every public document** — unchanged from session 7.

### Still open after this session
- **The published artifact is private.** Cameron must share it from the page's share menu
  for it to be publicly readable. Until then M4's writeup is live but not public.
- Next-actions #3-#6 unchanged (CCA overlay, SDG&E ACC Plus, PG&E ACC tables, TOU-DR-P).
- M1 and M3 DoDs unchanged: data-gated, not code-gated. M5 still sequenced behind an
  SDG&E validation recruit — see HANDOFF's warning block.


## 2026-09-07 — Session 7 (M4: public methodology + case study; privacy decision)

Committed `b0df750` on `session-4-nperiod-tou-m2` (not pushed, not merged to main).

**166 tests green, ruff clean, 11/11 PG&E golden bills still reconcile** (worst +$0.22 —
unchanged; nothing in this session touches `tariffs/` or `nem3/`). Took the M4 milestone
rather than HANDOFF next-action #1, on the reasoning below.

### DECISION — M4 before the SDG&E rate vintages
M4 is the only milestone whose DoD is reachable (M1 and M3 are data-gated, and no data is
coming). Next-action #1 was deliberately NOT done first: none of M4's headline material
depends on it. The byte-identical NBT finding comes from `src/nem3/acc_tables/`, the
EV-TOU-5 non-bypassable finding is a structural fact off the 6/1/2026 table, and the
reconciliation and M2 results are PG&E. #1 only matters if a calendar-year SDG&E cost table
is wanted, and it stays the smallest well-defined unit of work for next session.

### DECISION — the case study is SELF-ATTRIBUTED, not anonymized (asked and answered)
Reframed the privacy question before starting: the subject of the case study is the repo's
author, so this is a self-disclosure decision, not an anonymization one. Blurring buys little
(the repo carries his name) and costs the property that makes the work worth reading — a
third party being able to check the rates against the tariff sheets. Cameron chose, on both
questions put to him:
1. **Keep CARE visible.** README rows keep the `(CARE)` label; the writeup carries the full
   `care = 0.65 x standard - 0.01038` derivation as a case-study result. The alternative
   (bucketing the discount line) would have kept every dollar exact but cost the strongest
   technical section, and CARE was already implicit in the published kWh and totals.
2. **Scrub the session logs, then keep them public.** Removed from committed docs: the unit
   number (`APT A`), the CARE renewal date, and the tenancy/lease dates (HANDOFF and
   SESSION_NOTES now say the service ended in July 2026). The session-1 raw statement-total
   list was replaced with a pointer to the README table — the reconciled electric-net figures
   there are the canonical artifact, and publishing two overlapping sets of amounts served
   nothing. `tests/greenbutton/conftest.py`'s synthetic address lost its city.
Kept deliberately: city, schedule, rate vintages, exact bill dates and amounts, and the whole
reasoning trail. ROADMAP's M4 line was amended from "anonymized" to "honest" with the
rationale inline, so the DoD does not contradict what shipped.

### DECISION — no M3 payback figure appears in the writeup
Flagged rather than chosen silently. The M3 driver's payback numbers ($1,168/yr solar saving,
7.3-9.0 yr) run on a **synthetic load**. Publishing a payback dollar figure computed on a
fabricated load, in a document whose thesis is invariant 6, would be self-refuting, and it is
exactly the number that survives being screenshotted out of context. M4 therefore presents M3
as engine + structural findings only, and says plainly that no payback figure ships until a
real household with export data exists. The rates, NBC set and ACC tables behind it are real
and cited; the load is not, and the writeup says which is which.

### DONE — `docs/METHODOLOGY.md` and `docs/index.html`
Six sections: the gate (§1), engine design (§2), the household end to end (§3), five findings
(§4), what is still assumed (§5), reproducing it (§6). `docs/index.html` is the same material
as a standalone static page with a residual chart (11 bars, modeled-minus-billed, against the
$2.00 gate) — the DoD's "small static demo of outputs". README now links both and its M4 row
is marked done.

**One honest observation surfaced by writing it up, not previously recorded: the residual is
one-sided.** All eleven errors are positive (mean +$0.14, total +$1.55 on $1,084.26 = 0.14%
high). A curve-fitted model would centre on zero. The bias is explained — the ~0.3 kWh
meter-read boundary offset plus the 2025-vintage franchise-fee percent approximation — and
stating it first is stronger than letting a reader find it. Worth keeping as the answer to
"how do you know you didn't fit this?"

Also refreshed against a live run rather than carried from HANDOFF: the E-1 sensitivity is
**353% / 132%** (HANDOFF said 358% / 133%).

### Still open after this session
- **The writeup is not yet "live" in the published sense.** The Artifact publish was blocked
  by the session's permission classifier; `docs/index.html` is committed and ready to serve
  (GitHub Pages on `docs/`, or an Artifact publish once permitted). M4's DoD is otherwise met.
- Next-action #1 (SDG&E 1/1/2026 and 4/1/2026 vintages, `months: [3, 4]` pre-2026-05-01)
  remains the smallest unblocked unit of work.
- M1 and M3 DoDs unchanged: data-gated, not code-gated.


## 2026-09-07 — Session 6 (SDG&E generation layer; open decision 1 closed)

**166 tests green (was 133, +33), ruff clean, 11/11 PG&E golden bills still reconcile**
(worst +$0.22 — unchanged; all of this session's work is additive). Took HANDOFF
next-actions #1, #2 and #3.

### RESOLVED — open decision 1, the TOU-DR1 super-off-peak window
The two SDG&E sources did not actually conflict; **the tariff changed**. SDG&E extended the
weekday 10:00-14:00 super-off-peak window from March-and-April-only to **year-round,
effective 2026-05-01**. Sources (SDG&E's own, retrieved 2026-09-07):
sdgetoday.com/NewSuperPeakHours and sdge.com/super-off-peak-residential — "previously only
available in March and April. Now ... all year long" — naming TOU-DR-1, TOU-DR, TOU-DR-P,
EV-TOU-5, DR-SES and TOU-ELEC; corroborated by KPBS/NBC7/CBS8 coverage dated 2026-05-01.
So the existing specs (which followed the current pricing page) were **already right**, and
the 2018 tariff-book sheet is superseded, not contradictory.
**Honest caveat recorded in-spec:** the superseding advice letter and revised Cal. P.U.C.
sheet were NOT located — the evidence is SDG&E's customer-facing publications, not a tariff
sheet. Any spec vintage effective before 2026-05-01 must restore `months: [3, 4]`.
Pinned by `test_super_off_peak_is_year_round_on_weekdays_not_march_april_only`.
**This unblocks every SDG&E dollar figure.**

### DONE — `sdge_tou_dr1_generation_2026-06-01.yaml` (bundled EECC), next-action #1
The missing half of SDG&E. Values read off the 6/1/2026 Total Rates Table EECC column:
summer on 0.34920 / off 0.12853 / super-off 0.04121; winter 0.27475 / 0.19304 / 0.10228.
CARE is **derived and then proved**, not assumed: SDG&E prints no CARE EECC rate, only
`Total Adjusted CARE = (UDC + EECC - 0.00864) x 0.65`. Splitting that across layers gives
generation CARE = 0.65 x EECC, and delivery + generation then rebuilds SDG&E's printed
totals on **all twelve cells** (6 season x period, standard and CARE) — new gate file
`tests/tariffs/test_sdge_layers.py`, 23 tests.
**Structural finding worth keeping: on TOU-DR1 the UDC total is 0.32948 for every period
and both seasons, so 100% of the schedule's TOU price signal lives in the generation layer**
(summer on/super-off spread 0.30799/kWh; winter 0.17247). Every SDG&E load-shift, battery
and export-timing conclusion rests on those six numbers — which is exactly why reusing
delivery as a generation stand-in produced a *flat* price signal and understated arbitrage.
Also corrected in passing: the delivery spec's comment quoted PCIA 2018/2026 as
0.03662/0.04977; the 6/1/2026 sheet prints **0.03670 / 0.04987**. Full vintage table is now
recorded in the generation spec header for whenever the CCA overlay is written.

### DONE — NBC blocks on TOU-DR2 and EV-TOU-5, next-action #3
Both verified against their own 6/1/2026 tables rather than copied from TOU-DR1: the
component set is identical and **period- and season-invariant** (PPP 0.01515 + ND 0.00000 +
CTC (0.00007) + WF-NBC/DWR-BC 0.00591 = 0.02099 std; 0.00980 CARE). Every SDG&E delivery
spec can now be settled under NBT; a test asserts none may reach the NEM engine without a
declared import floor.
**⭐ FINDING — EV-TOU-5 is the interesting schedule for NEM.** It collapses its
super-off-peak distribution charge (UDC 0.04114 vs 0.31711 elsewhere) but does NOT discount
the NBCs, so in that window **~45% of the entire delivery charge is non-bypassable**
(0.02099 of 0.04705 std; 0.00980 of 0.02113 CARE) versus ~6.5% in the other windows. A
calculator netting exports against the headline delivery rate overstates the value of
shifting imports into super-off-peak on this schedule by roughly 2x.
Also fixed a wrong comparison in the EV-TOU-5 spec header that compared the CARE rate
against the STANDARD NBC total and concluded "essentially the entire delivery charge";
the like-for-like figures are above. Conclusion unchanged, magnitude corrected.

### DONE — `marginal_energy_price` / `period_codes` in `tariffs/bill.py`
`scripts/nem3_report.py` was arbitraging against a **hand-typed** price vector
(0.62 / 0.40 / 0.22 on / off / super-off). With both layers real, the price now comes from
the specs the biller uses. The typed vector was wrong in the direction that matters:
**TOU-DR1's real super-off-peak total is 0.37660, not 0.22 — a 71% understatement of the
cost of importing in exactly the window a battery charges in**, which biased arbitrage
toward buying the battery. The helper is version-aware (picks the spec in effect on each
day, as `compute_bill` does), excludes fixed charges / baseline credit / minimum bill
(marginal, not average), and **raises rather than extrapolating** to a date no spec version
covers, and rejects layers that classify an hour differently.

### CONSEQUENCE — the M3 demo window moved to 2026-06-01 .. 2027-05-31
Because the helper refuses to invent rates, the report can no longer run over calendar 2026:
the only committed SDG&E vintage starts 2026-06-01. Rather than fake the first five months,
the analysis window is now the twelve months the specs actually cover. Transcribing SDG&E's
1/1/2026 and 4/1/2026 tables (with the pre-May Mar/Apr super-off-peak window) would restore
a calendar-year run — recorded as an open item, not done.
New report output (bundled, standard, coastal_basic, synthetic 6,264 kWh load, 5 kW array):
baseline $3,022/yr; solar only $1,855 (save $1,168, 9.0 yr); solar+battery greedy $505
(save $2,518, 7.5 yr); LP $427 (save $2,595, 7.3 yr); NBC floor $86/yr. Dollar totals are
now REAL for a bundled SDG&E household — only the LOAD is still synthetic.

### Still open after this session
- CCA generation overlay (which CCA is unknown) — the one remaining SDG&E layer.
- SDG&E ACC Plus unconfirmed; `acc_plus_eligible=False` remains the conservative path.
- TOU-DR-P still deliberately unloadable (RYU Event Adder, open decision 2).
- Earlier-2026 SDG&E rate vintages not transcribed (see the window note above).


## 2026-07-25 — Session 5 (M3 groundwork: NEM 3.0 solar + battery, all four items)

**133 tests green (was 96, +37), ruff clean, 11/11 PG&E golden bills still reconcile**
(worst +$0.22 — the M3 work is purely additive to the engine, so the gate output was
unchanged). All four HANDOFF next-actions landed with tests. No item depended on dad's data.

### DONE — real ACC export tables, by vintage, from primary sources (`src/nem3/acc.py`)
Pulled SDG&E's actual **Net Billing Tariff (Solar Billing Plan) MIDAS export-pricing files**
(sdge.com/solar/solar-billing-plan/export-pricing): Current(NBT00), Legacy-2025(NBT25),
Legacy-2026(NBT26). Each is ~40 MB / 350,640 rows covering a 20-year horizon. `scripts/
build_acc_tables.py` collapses each to the **576 distinct values/year** the tariff actually
defines (12 months × weekday/weekend × 24 h, split delivery vs generation) and **verifies
the collapse** — it raises if any (year, month, day-type, hour, component) cell holds >1
value rather than averaging. Output: one gzipped CSV + a **mandatory citation manifest**
per vintage, committed under `src/nem3/acc_tables/` (304 KB total, real public data, not
gitignored). RIN prefix map from SDG&E's readme: `USCA-SDXX`=delivery, `USCA-XXSD`=generation.

**⭐ STRIKING REAL FINDING — SDG&E's NBT25, NBT26 and NBT00 tables are BYTE-IDENTICAL for
every overlapping year (verified: 0.0 max abs diff across 23,040 cells).** So the nine-year
lock-in currently confers **zero** dollar advantage on SDG&E — "lock in before rates drop"
is an empty pitch here, opposite to the PG&E vintage story installers cite. The tool states
this outright (honest-broker). Export rates DO rise with calendar year within a vintage
(2026 mean full rate 0.0883 → 2035 0.1432), which is why the table is modeled as
576-per-year, not one constant — code treating a locked vintage as a flat number would
misprice every year after the first.

### DONE — the 9-year lock-in, modeled from Schedule NBT (PG&E Sheets 55440-57375-E)
Read the full NBT tariff (PG&E ELEC_SCHEDS_NBT.pdf, 48 sheets). Key rules encoded:
- **Vintage = APPLICATION year; the 9-year clock runs from PTO** (Sheet 57352-E). Two
  different dates — `Vintage(application_year, pto_date)` keeps them separate so "apply in
  Dec, energise in March" (different vintages) is answerable. `table_vintage(year)` returns
  the application vintage inside the lock-in, `CURRENT` after.
- Lock-in only for applications **2023-04-15 … 2027-12-31**; later applicants take the
  current-year table every year (`has_lock_in`).
- **ACC Plus** adder (Sheet 57353-E): PG&E's table encoded (2023 .022 → 2027 .0044
  residential; low-income .09 → .018). **SDG&E ACC Plus deliberately NOT reused** — a blog
  claims SDG&E residential may not get it at all; `acc_plus_table` RAISES for SDG&E, and the
  conservative path is `acc_plus_eligible=False`. Confirm from an SDG&E NBT sheet if it ever
  matters.

### DONE — NBT settlement + the NBC import floor (`src/nem3/netting.py`, invariant 4)
Schedule NBT SC 2 is **"no netting"**: four separate ledgers, all encoded:
1. Imports billed at full retail via the **same `compute_layer` that reconciles the golden
   bills** — the solar analysis is anchored to a bill the engine reproduces.
2. Exports credited at ACC, **accrued separately for delivery and generation** (SC 2.d) —
   the two buckets do NOT fungibly combine; stranded credit carries forward (SC 2.e).
3. **NBCs billed on GROSS imports, never offsettable by exports** (SC 2.f: PPP, Nuclear
   Decommissioning, CTC, Wildfire Fund) — the import floor. Added a `non_bypassable` block
   to the schema + authored it on **TOU-DR1** (0.02099/kWh std, reproduces the documented
   figure). It is `included_in_energy_rate: true`, so netting CARVES it out of the
   offsettable subtotal rather than adding a line (the NBCs are already inside the energy
   rate) — no double-count. Added a `volumetric` flag to `LineItem` (metadata only, changes
   no amount) so "what a credit may offset" is decided at construction.
4. **ACC Plus** is the one credit that offsets ANY charge (SC 2.c).
- **CCA generation credit EXCLUDED by default** (SC 2.a + SDG&E's file note: posted
  generation rates are non-CCA only). A CCA customer's result is a lower bound until their
  CCA's own export terms are supplied. Credits **can't drive a period negative**; fixed
  charges/minimum bill/taxes are `protected`. Net-surplus and lock-in caveats emitted as
  `notes` (invariant 2).

### DONE — PVWatts, meter split, battery dispatch
- `pvwatts.py`: real NREL v8 client + **disk cache + never-fabricate guard**. No key/network
  in this env, so it RAISES with the signup URL rather than inventing a profile. Cache keyed
  on the full system spec; deterministic offline once fetched. (Modeling *production* is
  fine — invariant 6 forbids modeling *load*, which stays the customer's real intervals.)
- `solar.py`: behind-the-meter physics — `import=max(0,load−prod)`, `export=max(0,prod−load)`
  per interval; self-consumption falls out of the max, load shape untouched. Conserves
  energy exactly (tested).
- `battery.py`: **greedy TOU controller AND cvxpy LP**, both always returned (CLAUDE.md).
  Greedy is causal (charge from surplus solar, discharge into above-median-price hours, no
  grid charge). LP is perfect-foresight over four energy flows.
  **⭐ FINDING: under the full NBT settlement the LP can settle WORSE than greedy** (demo:
  greedy $2,807/yr vs LP $3,088/yr — LP wins there, but the test fixture shows the reverse).
  The LP optimizes a *marginal-price proxy*; real dollars come from the settlement whose
  credit caps and NBC floor the LP ignores, so which wins in settled dollars is a finding,
  not a fixed ordering. Labels reframed honestly (no "unreachable ceiling" claim).

### DONE — payback + Monte Carlo (`nem3/payback.py`, `uncertainty/montecarlo.py`, invariant 3)
`evaluate()` ranks solar-only / +battery(greedy) / +battery(LP) vs the no-solar baseline
(the baseline uses the reconciled `compute_bill`). `compare_vintage_timing()` answers
install-this-year-vs-next by changing ONLY the `Vintage` — for SDG&E it correctly reports
"immaterial" (identical tables) and refuses 2026-vs-2027 (**NBT2027 not published — will not
extrapolate an avoided-cost forecast**). `simulate_payback()` is a 10k-sample Monte Carlo
over rate escalation / degradation / load drift → payback P10/P50/P90 + P(never pays back) +
median cumulative savings. `scripts/nem3_report.py` prints the whole honest-broker report.

**Scope note (honest):** no real household has export data (Cameron: PG&E, no solar; dad:
no data), so the driver runs on a **clearly-labeled synthetic load**; the tariff rates, NBC
set and ACC tables it uses are all real and cited. The M3 DoD's "one real household payback
distribution" is **data-gated exactly like M1** — the engine is complete and tested, the
real-household run needs interval+export data that does not exist for either household.

**PG&E ACC tables NOT imported:** PG&E publishes EEC values as per-vintage **PDFs**
(pge.com/energyexportcredit), not the clean MIDAS CSVs SDG&E uses — a fragile parser, and
Cameron's PG&E account is closing, so it was not chased. `build_acc_tables.py` works for any
utility that publishes the MIDAS format.

## 2026-07-23 — Session 4 (N-period TOU engine; M2 opened on PG&E; SDG&E specs)

**91 tests green, ruff clean, 11/11 PG&E golden bills still reconcile** (worst +$0.22).
Constraint this session: dad's SDG&E data unavailable indefinitely — nothing below depends
on it.

### DONE — the tariff engine is now N-period and day-type aware (the blocker)
Implemented exactly the design carried in HANDOFF, no redesign.
- `TouDef` is an ordered **first-match-wins** rule list: `{period, hours [[start,end)],
  days: all|weekday|weekend, months:[...]}` + `default_period`. `peak_hours` survives as
  sugar normalising to `peak`/`offpeak`, so **every PG&E spec and its YAML keys were left
  untouched**.
- `energy` is now `dict[str, Rate]` keyed `f"{season}_{period}"` — the existing
  `summer_peak:` / `winter_offpeak:` YAML maps over verbatim. A model validator rejects
  unknown keys and missing season x period combinations (typos can no longer pass).
- `_usage()` returns **kWh per period**; energy / CARE-discount / TOU-adder loops iterate
  periods. Period resolution is a precomputed 12 x 2 x 24 table, so day-type awareness
  costs nothing per interval.
- `Baseline.allowance_multiplier` (PG&E 1.0, SDG&E 1.30).
- New `tariffs/holidays.py`: named, **cited** holiday calendars. Unknown or UNVERIFIED
  calendar => raises at spec load.
- **REGRESSION GATE PASSED: `reconcile_report.py` output was byte-identical before and
  after the refactor.**

### DONE — M2 opened on the PG&E household (deliberate roadmap override)
M1's DoD is blocked by an external data dependency, not by unfinished work, so M2 was
opened on the PG&E side rather than idling. Recorded here as the override it is.

**Authored from published tariff sheets, every rate cited to a Cal. P.U.C. sheet number:**
E-TOU-D, EV2-A, E-1 (PG&E delivery) + matched 3CE generation specs for each.
`scripts/rate_optimizer.py` is the one command.

**Result — VERDICT: STAY on E-TOU-C + 3CE** (4345 kWh, 328 days, current rates):
`E-TOU-C 1104.22 < EV2-A 1130.52 (conditional) < E-1 1160.91 < E-TOU-D 1208.80`.
The interesting part is *why*: the gap is driven almost entirely by the **baseline
credit**, which E-TOU-C and E-1 have and E-TOU-D and EV2-A do not — not by peak/off-peak
spreads. Sensitivity: E-1 overtakes E-TOU-C only if evening (4-9 p.m.) usage grows ~358%
(or +133% as a load-neutral shift); E-TOU-D never overtakes it on a load-neutral shift.

### RESOLVED from primary sources (three flagged approximations retired)
1. **Franchise Fee — was APPROXIMATE, now exact.** It is not a percentage of anything;
   Schedule E-FFS (Sheet 60706-E) prices it **flat per kWh by PCIA vintage**: Residential
   2018 vintage **$0.00059/kWh**. That is why no percentage basis ever fit. Checks:
   458.359 kWh -> $0.270 (bill $0.27), 243.56 -> $0.144 ($0.14), 40.388 -> $0.024 ($0.02).
2. **Generation Credit — was bill-fitted, now tariff-derived.** Schedule E-TOU-C Special
   Conditions: CCA customers pay everything in the Unbundling table **except the
   generation charge and the Bundled PCIA**, so the credit is `-(Generation + Bundled
   PCIA)`. From Sheet 61126-E that is winter **-0.12699 / -0.10031** against the
   least-squares fit from Cameron's bills of **-0.12705 / -0.10030** — agreement to 6e-05,
   a genuine primary-source confirmation that M0 was not curve-fitting.
3. **Summer generation credit** was a single-bill blend (-0.12013); now the exact TOU pair
   **-0.19771 / -0.09471**. Consistency check: the blend implies a 24.7% peak share for
   that June sub-period, which is right for a 5-of-24-hour peak window.
Arithmetic check applied to all four schedules: the unbundled components sum to the
printed Total rate **exactly** (e.g. E-TOU-D winter peak 0.16539 + 0.16492 + ... - 0.01011
= 0.38747).

### DECISION — CARE rates for counterfactual schedules (STATED ASSUMPTION)
PG&E does not print residential CARE rates in the tariff book. Solved from the CARE rates
on Cameron's own E-TOU-C bills: **care = 0.65 x standard - 0.01038** for energy, and
**0.65 x standard** for the baseline credit. Two parameters, five independent constraints,
fits to <=1e-5. Cross-check that it transfers across schedules: applying it to E-1's two
printed tier rates yields a CARE tier differential of **-0.05291**, which is exactly the
CARE Baseline Credit printed on the E-TOU-C bills. **Further corroboration found later in
the session:** SDG&E's CARE rate tables print the discount explicitly as **"CARE Discount
35%"**, confirming 0.65 is the statewide factor, not a coincidence of one schedule.
Still an assumption for PG&E; `--no-care` gives the fully tariff-grounded ranking.

### DECISION — Santa Cruz UUT Adjustment (was open decision 4, blocking M2)
Fitted all 11 statements against five candidate mechanisms; coefficient of variation:
`per day 0.0802` < `per bill 0.0839` << `fraction of gross UUT 0.194` < `per kWh 0.207`
< `fraction of net bill 0.330`.
**ADOPTED: a fixed credit of $0.21649 per billing day** — tightest fit and the only
near-constant form that copes with the 24-32 day spread in period lengths. Mechanism
remains UNVERIFIED.
**Why it is safe despite being unverified:** a per-day credit is *schedule-independent*,
so it adds the same constant to every candidate and cannot reorder the ranking. The
optimizer proves this rather than asserting it — it re-ranks under all three mechanisms
(per-day / none / proportional) and reports that **the order is identical under all
three**. Sub-$0.05 line-item effects only.

### DECISION — E-1 tiered rates are NOT a second schema gap
Surfaced rather than silently flattened, per CLAUDE.md. Rejected flattening to an average
outright (it destroys the marginal price signal M2 exists to compare). Rejected adding a
`tiers` concept as unnecessary, because expressing E-1 in the existing baseline-credit
machinery is an **algebraic identity, not an approximation**:
`tier1 x min(u,B) + tier2 x max(0,u-B) == tier2 x u + (tier1-tier2) x min(u,B)`
and `0.32561 - 0.40702 = -0.08141` is the credit. PG&E's own unbundling confirms this is
the tariff's real structure: the tier difference IS one component, the Conservation
Incentive Adjustment (-0.04052 / +0.04089). E-TOU-C's printed "Baseline Credit" (-0.08140)
is the identical construction (CIA -0.02786 / +0.05354). Tested by
`test_e1_baseline_credit_reproduces_explicit_tier_arithmetic`.
**Limits recorded in the spec:** handles exactly two distinct tier prices (E-1 has three
tier rows but only two prices); a genuine third price requires a real `tiers` field. Bill
*presentation* differs, so a future E-1 golden bill must be compared at the layer total.

### M2 DoD — the PG&E cross-check is the one part still open
PG&E's Rate Plan Comparison is behind an account login (pge.com/rateanalysis-pge) and
cannot be fetched here; it must be run by the account holder. The harness is built and
waiting: `--pge-comparison FILE` takes a small YAML of PG&E's output and prints a
side-by-side plus a ranking-agreement verdict. The script prints the exact instructions
when the flag is absent. Note the expected level difference: PG&E's tool prices **bundled**
service while this household buys generation from 3CE, so the **ranking and spreads** are
what must agree, not the totals.

### DONE — SDG&E delivery specs (TOU-DR1, TOU-DR2, EV-TOU-5, TOU-DR-P)
Re-pulled **current** numbers as instructed; the 2018 values in these notes were never
used. Note the trap: the 1-1-26 tables are NOT current — **6-1-26 tables exist** and are
what shipped.
- Layer split maps straight onto SDG&E's own table: **UDC Total + WF-NBC/DWR-BC =
  delivery**, **EECC = generation**. EECC and PCIA values are recorded in each spec's
  comments for the future CCA overlay (deliberately not authored — see out-of-scope).
- **NBC set modeled explicitly** (invariant 4): PPP 0.01515 + ND 0.00000 + CTC (0.00007)
  + WF-NBC/DWR-BC 0.00591 = **0.02099/kWh**, plus PCIA for a CCA customer.
- **Baseline credit at 130% of baseline** now expressible (`allowance_multiplier: 1.30`).
- **CARE is READ OFF THE TARIFF here, not assumed.** The CARE tables print "CARE Discount
  35%" applied after a $(0.00864) CARE-surcharge exemption, and CARE customers are exempt
  from WF-NBC/DWR-BC. The per-layer split was *verified additively*:
  `0.65 x (0.32948 - 0.00864) + 0.65 x 0.34920 = 0.43553` = the printed summer on-peak
  Total Adjusted CARE Rate.

**RESOLVED — open decision 1, the holiday calendar.** From **SDG&E Electric Rule 1
(Definitions), HOLIDAYS**: the same eight days PG&E names, but a **different observance
rule** — "When a Holiday falls on Sunday, the following Monday shall be defined as a
Holiday. No change will be made for Holidays falling on Saturday." PG&E uses "legally
observed" (federal: Sat -> Fri, Sun -> Mon). Real money: 2026-07-04 is a Saturday, so PG&E
takes Friday 7/3 off peak and SDG&E takes nothing. Both calendars are registered and
tested against each other.

**RESOLVED — open decision 2, minimum bill vs NBC floor. It was a false dichotomy.** They
are not competing rules and never "both bind": the Minimum Bill (Sheet 29955-E) is a
$/day floor on the **UDC/delivery layer** ($0.329, CARE $0.164), while the NBC floor is
not a tariff rule at all but a consequence of NEM netting, in which the per-kWh NBCs are
billed on gross imports. They compose. `MinimumBill` added to the schema and applied at
layer level.

**Also resolved from the tariff:** SDG&E seasons — Schedule EECC, "Seasonal Periods ...
All Customer Classes: **Summer: June 1 - October 31, Winter: November 1 - May 31**".
Materially different from PG&E's Jun-Sep summer.

**Shipped incomplete, on purpose (loader raises):** TOU-DR1, TOU-DR2 and TOU-DR-P carry
`UNVERIFIED` baseline allowances — SDG&E baseline quantities are per climate zone
(Coastal/Inland/Mountain/Desert) and per Basic vs All-Electric, and are not on the rate
tables. EV-TOU-5 loads today because it has **no** baseline credit. TOU-DR-P additionally
has UNVERIFIED period windows (see below).

### ⚠ NEW CONFLICT FOUND — SDG&E TOU-DR1 super-off-peak window
Two SDG&E sources disagree. The **tariff-book sheet** (Advice 3167-E, last revised 2018)
says weekday super-off-peak 10:00-14:00 in **March and April only**. SDG&E's **current
pricing page**, showing pricing effective 6/1/2026 — the same vintage as the rate table
used — shows weekday super-off-peak 10:00-14:00 with **no month restriction**. The specs
follow the current published table (year-round) because it matches the rate vintage, and
the conflict is flagged in-spec. **Confirm against a current tariff sheet before any
dollar figure ships**; it is material for ten months of the year.

### TOU-DR-P deliberately does not load — two gaps, both recorded in-spec
1. Period windows not sourced (no discoverable tariff sheet; SDG&E's pricing page renders
   its window table inconsistently against the sibling schedules). Not guessed.
2. The **RYU Event Period Adder, $1.16/kWh, 4-9 p.m. on event days** — an event-contingent
   rate the engine has no concept for. Modeling TOU-DR-P without it would systematically
   understate its cost and make it look like a free lunch, which is exactly the
   installer-tool failure mode invariant 2 exists to prevent. Preferred fixes, in order:
   caller-supplied event days; report as a RANGE (0 .. historical max events); or exclude
   it and say why. **Do not default it to zero events silently.**

### BUG FIXED — one UNVERIFIED spec used to break every other schedule
`load_specs` / `load_spec_versions` parsed *and validated* every YAML in the directory in
order to filter by `schedule_id`, so the first half-finished SDG&E spec made all 11 golden
bills fail. Filtering now happens on the raw `schedule_id`/`layer` keys **before** the
UNVERIFIED gate; the gate still fires for the schedule actually requested. Regression test
added. This defect only became visible because a genuinely incomplete spec was committed —
worth remembering as an argument for shipping UNVERIFIED specs rather than withholding them.

### Schema gaps still open
- `PerKwhAdder` has no CARE variant (only floats), so a per-kWh line that CARE customers
  are exempt from cannot be expressed as an adder. Worked around on SDG&E by folding
  WF-NBC/DWR-BC into the energy `Rate` (which does have standard/care).
- FERA / DRAH (0.39688 BSC on both IOUs) is still unmodelable — `Rate` has only
  `standard`/`care`.
- No `tiers` concept; fine for E-1 today (see above), required if a third tier price appears.

## 2026-07-23 — Session 3 (Workstream B complete; Workstream A step 1 complete)

Committed `70677c2`. **56 tests green, ruff clean, all 11 PG&E golden bills still
reconcile** (worst +$0.22) after the parser refactor.

### DONE — Workstream B: non-CARE PG&E billing unblocked
Pulled the real PG&E E-TOU-C tariff sheet (`ELEC_SCHEDS_E-TOU-C.pdf`, **Cal. P.U.C.
Sheet 61364-E**, Advice 7846-E, effective 2026-03-01). It is a **primary-source
cross-check of M0**: the sheet's Total Usage rates (S 0.52240/0.39940, W 0.39757/0.36757)
and Baseline Credit (−0.08140) **match the values M0 derived from the bills exactly**.
Good independent confirmation the reconciliation wasn't curve-fitting.

**The March-2026 Base Services Charge is income-graduated (IGFC), $ per customer per day:**
- **Income Tier 1** (0–200% FPG / CARE): **0.19713** ← matches Cameron's bill to the cent
- **Income Tier 2** (200–250% FPG / FERA, or affordable-housing ≤80% AMI): **0.39688**
- **Income Tier 3** (everyone else — the non-CARE default): **0.79343** (~$24.13/mo)

Filled `standard: 0.79343` (Tier 3). All three tiers documented in the spec; **FERA
(Tier 2) is a distinct customer class the engine does not yet model** — the `Rate` type
only has `standard`/`care`. Add a third variant if a FERA customer ever appears.

**FF/UUT class-independence — VERIFIED.** The IGFC is the *only* income-graduated
component. Franchise Fee and UUT are percentages of a subtotal and their rates do not
vary by CARE/FERA/income tier, so non-CARE billing reuses them unchanged. Noted in-spec.

Also on that sheet, for the still-open Climate Credit item: **California Climate Credit
$(36.18) per household, semi-annual, paid in the August and September bill cycles**
(PG&E E-TOU-C). That's the versioned-credit figure M2 needs — note it is Aug/Sep on this
schedule, not the Apr/Oct the earlier notes assumed.

### DONE — Workstream A step 1: SDG&E Green Button parser
**Both IOUs run the same Opower "Download My Data" platform**, so the file skeleton and
all the hard parts (interval inference, DST folding policy, PII masking, gap accounting)
are identical. Extracted them into **`src/greenbutton/_common.py`** and refactored
`pge.py` onto it — behavior byte-identical, verified by the 13 PG&E tests *and* the
11-bill reconciliation. `sdge.py` then only carries what genuinely differs:
- **`M/D/YYYY` unpadded dates** (vs PG&E's ISO) — wrong-format input is rejected clearly.
- **IMPORT/EXPORT register split** for NEM/solar accounts. M1 bills **grid import**; a
  non-zero export register is surfaced in `ParseReport.notes` rather than silently
  dropped (NEM export netting is M3). Non-solar accounts use the single USAGE column.
16 tests. Built to the documented format — **validate against dad's first real export.**

### BLOCKER FOUND — the tariff engine is 2-period; SDG&E needs 3-period + day-type TOU
This is the reason Workstream A steps 2–3 (specs + CCA overlay) did **not** land. Pulled
SDG&E **Schedule TOU-DR1, Cal. P.U.C. Sheets 29952–29955-E**. SDG&E residential TOU is
structurally richer than anything the engine can currently express:

1. **Three TOU periods** (On-Peak / Off-Peak / Super-Off-Peak). `TouDef` has a single
   `peak_hours` list and treats off-peak as the complement — it cannot represent a third.
2. **Weekday vs weekend/holiday schedules differ.** Weekday super-off-peak is
   midnight–6am; weekend/holiday super-off-peak is **midnight–2pm**. The engine's
   `_usage()` keys off hour only, never the day type.
3. **Month-conditional periods.** Winter weekday **10am–2pm in March and April only** is
   super-off-peak, carved out of off-peak.
4. Per public reporting, **SDG&E expands weekday super-off-peak to 10am–2pm year-round
   from 2026-05-01** — i.e. this needs its own effective-dated version (the engine's
   version-splitting already handles that part).

**TOU-DR1 periods as filed** (all local time):
- *Weekdays* — On-Peak 16:00–21:00; Off-Peak 06:00–16:00 + 21:00–24:00 (winter excluding
  10:00–14:00 in Mar/Apr); Super-Off-Peak 00:00–06:00 (+ winter 10:00–14:00 in Mar/Apr).
- *Weekends & holidays* — On-Peak 16:00–21:00; Off-Peak 14:00–16:00 + 21:00–24:00;
  Super-Off-Peak 00:00–14:00.
  (The filed sheet mislabels the second table "Weekdays and Holidays"; context and the
  period definitions make clear it is **weekends** and holidays.)

**Proposed engine design (backward compatible — carry into next session):** replace
`TouDef.peak_hours` with an ordered, first-match-wins rule list —
`{period, hours: [[start,end)], days: all|weekday|weekend, months: [...]}` plus a
`default_period`. Legacy `peak_hours` stays as sugar that normalizes to periods
`peak`/`offpeak`, so **every existing PG&E spec and its YAML energy keys
(`summer_peak`, `winter_offpeak`, …) keep working untouched**; SDG&E specs use periods
`on_peak`/`off_peak`/`super_off_peak` with keys `summer_on_peak`, etc. Then `energy`
becomes `dict[str, Rate]` keyed `f"{season}_{period}"`, `_usage()` returns kWh **per
period** instead of `(peak, off)`, and the energy/CARE/TOU-adder loops iterate periods.
**The 11-bill golden reconciliation is the regression gate for this refactor.**

### SDG&E structural facts captured (from Sheets 29952–29955-E) — for the specs
- **Delivery/generation split is explicit in the tariff**, which maps cleanly onto our
  layer model: **UDC Total** (delivery) + **DWR-BC** (bond charge) + **EECC** (commodity
  = the generation layer a CCA replaces) = Total Rate. This is the SDG&E analog of the
  PG&E/3CE split and is exactly how the CCA overlay should be layered.
- **UDC components** (and therefore the non-bypassable charges, invariant #4):
  Transmission, Distribution, **PPP** 0.01347, **ND** (0.00005), **CTC** 0.00165, LGC,
  RS, TRAC. With **DWR-BC 0.00549**, the NBC set (PPP + ND + CTC + DWR-BC) ≈ **0.0206/kWh**
  on this sheet — the documented core of the ~2.5¢ import floor (wildfire-fund and other
  components to be added from current sheets).
- **Minimum Bill $0.329/day**, CARE/FERA 50% discount → **$0.164/day**. NOTE this is a
  *second, distinct* floor from the NBC import floor — **decide which governs** when both
  bind (see open decisions).
- **Baseline credit applies up to 130% of baseline** — materially different from PG&E's
  100%. `Baseline` in the schema currently credits `min(usage, allowance)`; SDG&E needs
  `min(usage, 1.30 × allowance)`. Add a multiplier field.
- **Franchise Fee Differential 5.78%** within the City of San Diego (cited, unlike the
  PG&E franchise fee which is still APPROXIMATE).
- **CARE surcharge $0.00437/kWh**, CARE customers exempt.
- **California Climate Credit $(33.50)** semi-annual per Schedule GHG-ARR.

**CAVEAT — these rate *values* are from the schedule's Jan-1-2018 filing (Advice 3167-E)
and are STALE.** The *structure* above is authoritative and reusable; the *numbers* must
be re-pulled from the current "Total Rates Table" regulatory PDFs before any spec ships.
TOU-DR1 is also the "experimental" pilot schedule — confirm which of TOU-DR1 / TOU-DR2 /
TOU-DR-P / EV-TOU-5 dad is actually on before treating any as the default.

### Open decisions (need Cameron / need dad's bill)
1. **Holiday calendar.** SDG&E prices holidays as weekend days, which moves 16:00–21:00
   usage from On-Peak to a cheaper period on ~6–10 days/year — real dollars. The exact
   observed-holiday list must come from the tariff (Rule 1 / the schedule's definitions),
   **not guessed**. Blocks a correct day-type implementation.
2. **Minimum bill vs NBC import floor** — which governs when both bind, and does the
   minimum bill apply to the delivery layer only or the combined bill? Affects every
   low-usage and high-solar month.
3. **Which CCA** — San Diego Community Power (City of SD) vs Clean Energy Alliance (parts
   of N. County). Unresolvable until dad's bill; drives which generation overlay to author.
4. **Which schedule** dad is actually on (TOU-DR1 vs TOU-DR2 vs TOU-DR-P vs EV-TOU-5).

### ADDENDUM — session 4b: CCA on/off, EV eligibility, SDG&E zones

**Context change from Cameron: the Santa Cruz service address is being vacated at the end
of July 2026, and he has no plug-in EV.** Told him to export the full Green Button interval data and every remaining bill PDF
before the account closes — that data is the entire trust artifact and portal access
usually dies with the account. Also: PG&E's Rate Plan Comparison returns *"This account has
no service agreement eligible for rate enrollment"* for his account, so **the M2 DoD
cross-check is UNAVAILABLE, not merely pending** — most likely because generation is with a
CCA, possibly because the account is closing.

**CCA on/off is now modeled (roadmap M2's "CCA on/off where applicable").** Added
`Service` (bundled | cca) and an `applies_to` tag on adders/surcharges, straight from the
schedules' BILLING special conditions: a bundled customer pays neither the vintaged PCIA nor
the E-FFS franchise fee. That keeps ONE delivery spec per schedule serving both service
types instead of two copies that would drift at the next rate change. Four new
`PGE-BUNDLED-*` generation specs = Generation + Bundled PCIA (the arithmetic negative of the
delivery spec's Generation Credit), so
`Total - (Gen + BundledPCIA) + (Gen + BundledPCIA) = Total` exactly — tested.

**THE VERDICT FLIPPED, and this is the most useful result the project has produced so far:**
```
E-TOU-C + PG&E   933.50   <- SWITCH, -170.72/yr
E-1      + PG&E   990.57
E-TOU-D  + PG&E  1038.50
E-TOU-C  + 3CE   1104.22   <- current
```
Decomposition: **PCIA +159.88/yr**, UUT on it +13.59, franchise fee +2.54, and 3CE's
generation is only ~$5/yr cheaper than PG&E's. The mechanism is real and checkable on the
sheets: a **2018-vintage** CCA customer pays PCIA **0.03679/kWh** while the **2026 bundled**
PCIA is **-0.01011** (a credit) — a ~4.7c/kWh gap that 3CE's generation discount no longer
covers. That is exactly the non-obvious, account-specific finding the tool exists to find,
and no generic calculator surfaces it.
Caveats now printed in the report: PG&E Rules 22.1/23.1 require **six months' advance
notice** to elect bundled service, with **Transitional Bundled Service** (Schedule TBCC,
short-term market prices) in the interim — a saving realised months later after an unpriced
TBS window is not the annual figure above. 3Cprime/3Cflex products are also unmodeled.
**Moot for Cameron personally** (the account is closing), but it validates the method.

**EV eligibility is now FILTERED, not flagged.** Cameron has no EV, so EV2-A plans are
excluded from the ranking entirely (`--ev` re-includes them). Flagging an ineligible plan
still lets it become the headline; filtering cannot. Honest-broker invariant.

**SDG&E baseline allowances — RESOLVED from the tariff.** Cal. P.U.C. Sheet 29294-E
(Schedule DR, Sheet 5, SC 3) publishes the full climate-zone table, so all eight rows now
ship in-spec. Design decision: the zone is a **customer** fact, so `Baseline` grew an
`allowances` table and `territory` is supplied **at bill time**; omitting it RAISES rather
than defaulting, because a wrong zone silently mis-sizes the largest credit on a CA bill.
**TOU-DR1 and TOU-DR2 now load.** TOU-DR-P still raises (unsourced period windows + the
unmodelable RYU event adder) — unchanged and correct.

Also confirmed here: PG&E baseline Territory **T** / Heat Source **H** was read off
Cameron's bill in session 1, so 7.1 / 12.9 kWh-per-day is sourced, not assumed.

**96 tests green, ruff clean, 11/11 golden bills still reconcile.**

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
- **CARE enrolled** (low-income discount) — a large line item on
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

**Observed electric $ per statement** (PDF monthly history, delivery+generation) were
transcribed for all 11 statements and drive the reconciliation gate. The canonical figures
are the reconciled electric-net amounts published in the README accuracy table; the raw
statement totals are not duplicated here (they differ by the account-summary adjustments).

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
- Account is an apartment in Santa Cruz — need to confirm the exact electric
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
