# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it current: state,
how to run, open decisions, exact next action._

## Status _(2026-10-01, end of session 31)_

**M0, M2 (PG&E) and M4 are done. M1 and M3 have complete, tested engines whose DoDs are
blocked on data that does not exist yet. Do not fabricate a load or a bill to "finish" either.**

**Measure, don't copy:** `PYTHONPATH=src python -m pytest -q` (1,793 passed on 2026-10-02),
`ruff check .`, `git fetch -q origin && git rev-list --count origin/main..main`, `git status`.
Every session that copied a test count, a commit count or a working-tree claim forward
published a wrong one. What stays true as it ages: **11/11 PG&E golden bills within ±$2
(worst +$0.22); everything through session 30 is pushed; both CI jobs green.**

| Milestone | State | What is missing |
|---|---|---|
| M0 — PG&E reconciliation | **Done** | — |
| M1 — SDG&E + CCA overlay | **Engine + both harness paths built; DoD blocked** | M1a: 3 ordinary SDG&E bills (fee lines now built for TOU-DR1). M1b: one household's export + its own bill |
| M2 — Rate optimizer | **Done for PG&E** | the SDG&E half, gated on M1 |
| M3 — NEM 3.0 solar + battery | **Engine complete, DoD blocked** | one real household with export data |
| M4 — Public methodology + site | **Done, live; site prices for the reconciled scope** | — |
| M5 — First external users | **Materials drafted** (`RECRUITING.md`), nothing sent | gated on M1 — see the warning below |

- **Repo:** https://github.com/CameronGordonn/energy-advisor (public, AGPL-3.0)
- **Site:** https://camerongordonn.github.io/energy-advisor/ — a working tool, four pages.

> **⚠ CONTEXT.** The Santa Cruz PG&E service ended July 2026; the last export in `data/` runs
> to 2026-07-18. The 11 committed golden bills are unaffected. Cameron has **no plug-in EV**,
> so EV2-A / EV-TOU-5 are filtered out of rankings by default. Dad is **no longer** an SDG&E
> data source (decided 2026-09-16).

> **⚠ GIT STATE.** The main checkout sits on a **detached HEAD at `main`** because `main` is
> checked out in the linked worktree `../energy-advisor-m1a` (left by session 29, clean). A
> commit made here is orphaned. Either `git worktree remove ../energy-advisor-m1a` and
> `git switch main`, or work on a branch. **Two concurrent sessions need `git worktree`, not
> one checkout** (session 29/30's collision).

---

## Where things stand (sessions 25–31 in one place — detail is in SESSION_NOTES)

**This project is data-starved, not code-starved — with one exception found in session 31.**

1. **Both reconciliation paths exist.** The interval path (session 24, utility-general) and
   the **bill-only path** (session 29, `src/tariffs/bucketed.py`) share one charge layer,
   `tariffs.bill.charge_lines`. Parity is *measured*: bucketing the 11 PG&E golden bills'
   real intervals and pricing the buckets lands on every line to the cent. Fill-in forms:
   `tests/golden_bills/sdge_TEMPLATE.yaml.example` (M1b) and
   `tests/golden_bills/sdge_BILL_ONLY_TEMPLATE.yaml.example` (M1a). Bill-only refusals by name:
   a segment straddling a rate change (`SegmentStraddlesRateChangeError`), TOU-DR-P's event
   adder (`TimingDependentChargeError`), missing buckets, bad tiling.
   - **Scope limit:** the bill-only path takes SDG&E's bucketing as given, so it cannot test
     `tou.rules` (the year-round super-off-peak window, weekends, holidays). A green M1a does
     **not** retire that — it is M1b's job. M1a also never exercises the NBC import floor.
   - **Ask implication:** prefer a statement inside one rate vintage (2026 TOU-DR1 changed
     1/1, 4/1, 5/1, 6/1, 8/1; summer starts 6/1), or one that prints its sub-period blocks.

2. ⭐ **Session 31: M1a is NOT "transcription only" — a real SDCP bill would fail ±$2 today.**
   SDCP publishes a complete specimen 2026 TOU-DR1 statement (`notes/sdcp_specimen_bill_2026-10.md`).
   Every rate on it matches our specs to the fifth decimal, but it carries **~$8.41 of fee
   lines the engine did not model** (City of San Diego Franchise Fee Differential 5.78%,
   Franchise Fee Equivalent Surcharge 6.88%, State Regulatory Fee $0.001/kWh) plus the CEC
   surcharge, an Economic Development credit and SDCP Power100 (an opt-in). **The first three
   are not opt-ins, so expect them on any City of San Diego SDCP bill.** It's a specimen (placeholder IDs, internally
   inconsistent arithmetic), so it counts toward nothing — but it moved the critical path.
   **Built the same session** (next-action #2): the specimen now prices to $137.97 modelled,
   $140.71 with the three unmodelled lines observed, vs $140.64 printed.

3. **The public internet is exhausted for M1.** Session 23: six real SDG&E exports across two
   repos, none paired with bills (`notes/sdge_public_exports_2026-09.md`). Session 28: the
   26-bill `ookla-ariel-ride/SDGE-Analysis` corpus is NEM-2 true-up accruals, measured shut
   (`notes/m1_without_dad_2026-09.md`). Session 31: utility/CCA bill-explainer pages hold one
   specimen and nothing real; a second pass for a *real homeowner's solar bill* found several
   (r/solar PG&E NBT page 1, two CPUC complaint dockets) and none usable — partial, NEM-2,
   disputed-meter, or unredacted. **Do not re-run these searches.** M3 needs a recruited NBT
   household: all pages of 1–3 statements plus the matching Green Button export.

4. **Tier-2 corroboration exists and is live:** `tests/published_impacts/` prices SDG&E's
   three 2026 rate-alert figures through `compute_bill`. TOU-DR1 **delivery** is corroborated
   (vintage-over-vintage delta catches a 0.3% rate error); **generation is not**; the climate
   zone is not pinned by it; the PCIA exclusion is an inference
   (`PCIA_EXCLUDED_BY_INFERENCE`). Counts toward nothing in the ±$2 claim.

5. **Site usability overhaul (session 31):** intake on the first screen, bill-line hints on
   every pricing question, plain plan descriptions, a saving figure, no dead ends (change
   answers / analyze another file / jump to prices), plain-sentence refusals
   (`Blocker.summary`, tested in Python). Recorded in both design skills.
   **The site prices** (session 28) for households the PG&E specs can be shown to describe
   (territory T, all-electric, 3CE, PCIA 2018) and refuses by name for everyone else, with
   four blocker codes and `RECONCILED_UTILITIES` tied by test to the golden-bill corpus.
   Session 30 fixed three a11y defects and added `scripts/audit_layout.py` and
   `scripts/contrast_matrix.py`. **Session 32 (2026-10-23) replaced the whole visual
   system** at Cameron's request — see "The site and its design" below.

6. **ACC tables re-imported 2026-09-16, byte-identical.** The floating NBT00 table expires
   **2026-12-31** for both utilities; a test fails on 2027-01-01. No 2027 vintage published.

---

## EXACT NEXT ACTION

**0. Check for SDG&E data first, every session.** `ls -lt data/`. If a bill or export has
landed it outranks everything below.
  - Export → `PYTHONPATH=src python scripts/inspect_export.py FILE.csv` first. The parser has
    refused 3 of 5 real SDG&E exports on first contact; **if it refuses, fix the parser, not
    the file.**
  - Bill only → copy `sdge_BILL_ONLY_TEMPLATE.yaml.example` to `sdge_<MM-DD-YYYY>.yaml`, transcribe,
    run `PYTHONPATH=src python scripts/reconcile_report.py`. Expect it to miss by the fee
    lines in #2 until they're built.
  - **What the bill must tell us:** schedule, climate zone, CARE, bundled vs CCA, which CCA
    and cohort, **PCIA vintage**, **city** (franchise fee), and any CCA opt-up product.
  - If the household is **CARE and on a CCA**, read open decision 9 first.

**1. Get ONE ordinary SDG&E bill.** One redacted statement from one non-solar, non-NEM SDG&E
household — no export, no year of data. A friend, a colleague, one post. Three such bills
close M1a. `RECRUITING.md` Ask 1/Ask 2 is still the fuller framing. **This is the only thing
that moves a milestone.**

**2. SDG&E fee lines — BUILT (session 31, branch `sdge-fee-lines`); what is left.**
The City of San Diego Franchise Fee Differential, the CCA Franchise Fee Equivalent Surcharge
(on imputed EECC) and the CEC surcharge are modelled, cited and tested
(`tests/tariffs/test_sdge_franchise_fees.py`). **`jurisdiction` is now a required customer
fact** for TOU-DR1 (`city_of_san_diego` | `other`), in both fixture templates. Remaining, in
order — detail in `notes/sdcp_specimen_bill_2026-10.md` § "Built":
  1. ✔ **Extended to TOU-DR2 / TOU-DR-P, and bundled-in-city settled (session 32).**
     Schedule EECC (Sheet 30030-E) has its own 5.78% clause, so bundled households pay it on
     generation too, as a second line. **EV-TOU-5 still refuses in the city**: its schedule
     sheet was not found. Find it, then drop `bundled` from its `unverified_for`.
  2. **State Regulatory Fee** ($0.001/kWh) — find the authority; until then it is an
     observed adjustment in fixtures (the bill-only template says so).
  3. **FFES base gap** — Schedule CCA says imputed EECC (48.76 on the specimen), the
     specimen prints 49.71. Settle against a real CCA statement; do not fit.
  4. **Refused branches** (`UnverifiedChargeError`): CARE on any franchise line; a CCA
     customer in the city on TOU-DR2 / TOU-DR-P / EV-TOU-5 (no PCIA in those specs); EV-TOU-5
     in the city. The first bundled city bill should also show whether SDG&E prints the
     delivery and generation differentials as one line or two.
  5. Economic Development Program Credit, SDCP Power100 — observed adjustments for now.

**3. Small corrections from session 31 (no data needed):**
  - `tests/tariffs/test_sdge_layers.py` — the docstring of
    `test_our_delivery_rate_less_the_import_floor_is_what_sdge_printed` over-generalises: a
    non-NEM TOU-DR1 statement prints delivery net of WF-NBC only (0.00591), not the whole
    0.02099 bundle. Scope it to NEM statements.
  - Baseline allowance: specimen prints 8.8/day Coastal winter, spec says 9.2 (a real 2024
    statement agrees with 9.2). Re-check Sheet 29294-E's current revision; change nothing
    without the sheet.

**4. TOU-DR1 GENERATION is still unvalidated by any real bill**, and 100% of the schedule's TOU
signal lives there. The first real bill must price generation, not just delivery.

**5. TOU-DR-P ranking** — engine done; session 27 decided to report a break-even instead of
forecasting event days. Gated behind an SDG&E candidate set, which is gated on M1.

**6. ACC re-import before 2027-01-01**, when the utilities republish with D.26-09-007's ACC.
If `test_sdge_vintages_are_one_table_wearing_three_labels` or
`test_pge_vintages_that_collapse_into_one_table[2026-current]` fails, restate the ⭐ vintage
findings (here, `test_acc_pge.py`'s docstring, finding 01 of `docs/METHODOLOGY.md` +
`methodology.html`) rather than patching them. `notes/acc_reimport_2026-09.md` has the commands.

> **⚠ READ BEFORE STARTING M5 — M1 and M5 are coupled.** M5 targets San Diego users, and **the
> engine has never reproduced a single real SDG&E bill.** Sending dollar figures to strangers
> before that would violate invariant 1. Sequencing rule: the first recruit who supplies bills
> closes M1a; only then does the SDG&E path earn the right to show anyone a dollar. Recruit
> for data before sales. A PG&E recruit needs no such caveat.

---

## What exists now

- **Green Button parsers** (`src/greenbutton/`): PG&E, plus **both** SDG&E CSV shapes — the
  documented `TYPE,DATE,START TIME,END TIME,...` table and the real `Meter Number,Date,Start
  Time,Duration,Consumption,Generation,Net` one. The table is located by header *signature*,
  not a literal. DST folds are resolved from **file order**, so PG&E's summed 24-label day and
  SDG&E's true 25-hour day are both correct without branching on utility — and the same logic
  handled **spring-forward** correctly on first contact with a real file (session 23).
  The **date format is elected per file** from `("%m/%d/%Y", "%m/%d/%y")` because SDG&E emits
  both year widths; the first candidate that parses *every* row wins, and a file mixing both is
  refused rather than guessed (`3/1/2024` under `%m/%d/%y` is year 24). On a solar account the
  preamble's `Total Usage` is the **NET** sum, so a mismatch equal to the export register is
  reported as the netting convention, not as "rows may be missing" — that note was a false
  alarm on every NEM export.
- **Engine** (`src/tariffs/`): N-period first-match-wins TOU rules with weekday/weekend/holiday
  day types, month-conditional windows, cited holiday calendars, `Baseline.allowance_multiplier`,
  `MinimumBill`, per-kWh surcharges, `NonBypassable`, `period_codes`, and **`marginal_energy_price`**
  (version-aware per-interval retail price; refuses dates no spec covers; rejects layers that
  classify an hour differently).
- **Specs — 50 files, 22 schedule-layers** (`src/tariffs/specs/`):
  - **PG&E**: E-TOU-C (4 vintages) / E-TOU-D / EV2-A / E-1 delivery, each with matched 3CE and
    PG&E-bundled generation.
  - **SDG&E — all three rankable residential schedules have BOTH layers across ALL of 2026**
    (sessions 16 and 18). TOU-DR1 delivery + generation in **five 2026 vintages** (1/1, 4/1,
    5/1, 6/1, 8/1); **EV-TOU-5 likewise in five** (same 5/1 window split, sourced directly for
    that schedule); **TOU-DR2 in four** — it has no super-off-peak period, so the 5/1 window
    filing cannot touch it, and the absence of a 5/1 file is asserted by test rather than
    merely true. **8/1 is the last vintage SDG&E published for 2026** — 7-1, 9-1, 10-1 and
    11-1 all 404 as of 2026-09-09 — so there is no stale Aug-Dec tail any more.
    **TOU-DR-P now has both layers too** (session 21, 6/1 only): delivery from Schedule
    TOU-DR's UDC — byte-identical to TOU-DR1's — plus Schedule EECC-TOU-DR-P generation
    carrying the RYU event adder. It is no longer excluded from any gate. Its 8/1 vintage
    is NOT authored; it is in no candidate set, so the lag cannot misrank anything yet.
    ⚠ TOU-DR2 and EV-TOU-5 had shipped **delivery-only** since session 6 — a bundled customer
    could not be priced on either — and nothing failed, because every test named its files
    explicitly. Both pairs are complete now, and `test_every_sdge_delivery_vintage_has_a_
    matching_generation_vintage` globs the directory so a half-authored schedule fails loudly.
    The NBT-settleability list is likewise a glob now, not six hand-maintained filenames.
  - **CCA overlay, complete for San Diego**: Clean Energy Alliance
    (`cea_tou_dr1_generation_2026-06-01.yaml`) and San Diego Community Power
    (`sdcp_{2021v,2022v}_tou_dr1_generation_{2026-01-01,2026-05-01}.yaml` — PowerOn, the default
    product; the two jurisdiction cohorts are **separate providers**).
  - Every SDG&E TOU-DR1 delivery vintage carries the **vintaged PCIA** as an `applies_to: cca`
    adder whose vintage is supplied at bill time (`compute_bill(..., vintage="2018")`) and
    **raises if omitted**. `load_specs`/`load_spec_versions` take `provider` and raise when
    several suppliers match — bundled EECC and a CCA are both "TOU-DR1 generation".
- **Reconciliation harness** (`src/report/reconcile.py`, `tests/golden_bills/`): **utility-general
  since session 24.** A fixture's `utility:` field selects the interval export in `data/` (by
  each utility's own filename patterns, PG&E's `pge_electric_usage_interval_data*` and SDG&E's
  `[PV_]Electric_{15,60}_Minute_*` / `sdge*`) **and** the parser that reads it — no sniffing,
  so a mislabeled fixture fails instead of being quietly re-detected. Two exports for one
  utility raise rather than being resolved alphabetically.
  Per-household facts ride in the fixture's `customer:` block — `service`, `territory`,
  `vintage`, `event_days` — and the harness asks the **loaded specs** which of them they need,
  then refuses the fixture by name if one is missing. Derived per run, so a spec that gains a
  climate-zone table or a vintaged adder immediately starts failing the fixtures that do not
  declare it. `service` used to default to `Service.CCA` inside `compute_bill`, which would
  have billed a bundled SDG&E household a PCIA it does not pay; all 11 PG&E fixtures now say
  `service: cca` explicitly. **`tests/golden_bills/sdge_TEMPLATE.yaml.example` is the fill-in
  form**, and a test asserts it still declares everything the SDG&E specs demand.
- **M2 optimizer**: `scripts/rate_optimizer.py` — ranking, verdict, component-level *why*,
  sensitivity, assumption audit.
- **M3 NEM 3.0 engine** (`src/nem3/`): `acc.py`, `netting.py`, `solar.py`, `pvwatts.py`,
  `battery.py` (greedy + cvxpy LP, both always returned), `payback.py`, plus
  `uncertainty/montecarlo.py`. Driver: `scripts/nem3_report.py`, running calendar 2026.
- **M4 writeup**: `docs/METHODOLOGY.md` + `docs/methodology.html`, live.
- **Public site, four pages** — see the next section.
- **Two committed project skills** in `.claude/skills/`: `design-system` and
  `accessibility-audit`. **Read them before touching `docs/`.** They are project-scoped so they
  load in any environment the repo reaches, including a fresh clone or a cloud sandbox.

## Facts about the tariffs that cost real money

Each of these is pinned by a test; none is obvious, and each is a way a generic calculator gets
a California bill wrong.

- **⭐ Delivery and generation change on DIFFERENT dates, and can move in OPPOSITE
  DIRECTIONS.** EECC moved 4/1/2026 then held; the 6/1 filing moved delivery only (UDC
  0.34061 → 0.32948). Then the **8/1 filing moved both, opposite ways**: UDC 0.32948 →
  0.32601 (down) while summer on-peak EECC 0.34920 → 0.35943 (up), so the all-in rate ROSE
  0.68459 → 0.69135 on a filing that cut the delivery rate. A tool treating "the rate changed"
  as one event misprices a layer on every bill spanning it and gets the *sign* wrong here.
- **⭐ FIVE SDG&E vintages, not three.** Rates changed 1/1, 4/1, 6/1 and 8/1, but the weekday
  10:00–14:00 super-off-peak window went year-round **2026-05-01**, *inside* the 4/1 rate
  vintage, and SDG&E published **no 5/1 table** (that URL 404s). So the 4/1 rates are committed
  twice — with the March/April window (governs April) and the year-round one (governs May).
  **Do not "simplify" this away**; rationale and dollar impact are in
  `sdge_tou_dr1_delivery_2026-05-01.yaml`.
- **⭐ On TOU-DR1 the UDC total is period- and season-flat**, so *100% of the schedule's TOU
  price signal lives in the generation layer*.
- **⭐ CEA is not uniformly cheaper than SDG&E — it is seasonally OPPOSITE** (+59% summer
  on-peak, −56% winter off-peak). Which supplier wins is a function of the household's seasonal
  shape, not a fact about the CCA.
- **⭐ SDCP publishes two rate sheets by enrolment cohort** (+$0.00559/kWh for National City and
  the unincorporated county), invisible on its marketing pages and not electable — hence two
  providers, so the loader cannot guess.
- **⭐ The PCIA, not the CCA's rates, decides.** SDCP undercuts SDG&E in every period, but a
  2018-vintage exit fee flips exactly summer super-off-peak — the battery-charging window — and
  a 2024 vintage flips 5 of 6. **And the PCIA moves on its own schedule:** every vintage fell
  ~0.00216/kWh on the 8/1/2026 sheet (2018: 0.03670 → 0.03454), which is ~$13/yr on a 6,000 kWh
  CCA household and which **no bundled test can catch** — the layer-sum gate never touches the
  adder. Pinned by `test_the_august_filing_moved_the_pcia_too`. The CCA generation specs
  themselves need no 8/1 vintage: a CCA files its own rates on its own dates, and the PCIA a
  CCA customer pays rides on the SDG&E *delivery* spec, so it updated with this filing.
- **⭐ SDG&E's NBT25 / NBT26 / NBT00 export tables are byte-identical** for every overlapping
  year, so the nine-year lock-in currently confers *zero* dollar advantage on SDG&E. "Lock in
  before rates drop" is an empty pitch here. Now asserted directly by
  `test_sdge_vintages_are_one_table_wearing_three_labels` rather than only stated here.
- **⭐ PG&E's vintages DO differ — and the difference does not support the installer pitch.**
  _(Session 19; this is the asymmetry the SDG&E line above was waiting on.)_ PG&E publishes
  five vintage files that collapse to **two** distinct schedules: NBT23 ≡ NBT24, and
  NBT25 ≡ NBT26 ≡ NBT00. The two clusters are far apart — over $1/kWh in the extreme cells —
  so "which vintage" is a real question in PG&E territory and a non-question in SDG&E's. But
  the gap is **structural by hour of day**, and read that way it inverts the pitch:
  - **Midday 09:00–15:00, where a solar-only array actually exports:** the older NBT23/24 is
    ahead in every published year, by only $0.005–$0.020/kWh. Near enough a wash.
  - **Overnight 00:00–06:00, reachable only with a battery:** the newer NBT25/26 is ahead in
    every year, and from 2030 by **more than $0.10/kWh** — an order of magnitude more than
    the midday gap runs the other way.
  - **Evening 17:00–21:00:** NBT23/24 leads through 2029 and NBT25/26 from 2030, so a
    nine-year lock-in taken in 2023 spans the flip.

  So the vintage question in PG&E territory is really a *battery* question, and where it has
  a clear answer the answer is "later is better". Also note NBT26 ≡ NBT00: locking in the
  2026 vintage buys exactly the floating table, so the lock-in's value today is not a gain
  but **insurance against the floating table moving at the next ACC adoption** — which is a
  defensible thing to want and a different claim from the one installers make. All pinned in
  `tests/nem3/test_acc_pge.py`.
- **⭐ EV-TOU-5 collapses its super-off-peak distribution charge but not its NBCs**, so ~45% of
  the delivery charge in that window is non-bypassable versus ~6.5% elsewhere. A calculator
  netting exports against the headline rate overstates load-shifting value there by ~2×.

## The site and its design

Four pages in `docs/`, served by GitHub Pages: `index.html` (the tool), `methodology.html`,
`privacy.html`, `terms.html`. Shared `site.css` (tokens + chrome). **No web fonts at all**
(system font stack); `docs/fonts/` and `fonts.css` were deleted in session 32.

- **The tool runs the REAL Python parsers** under Pyodide/WebAssembly — not a JS port, so there
  is one tested implementation. Nothing is uploaded because there is no server.
  `docs/engine.js` is **generated** from `src/` by `scripts/build_web_engine.py`, and
  `tests/report/test_web_engine.py` fails if it goes stale. Rebuild after touching
  `src/greenbutton/` or `src/report/inspect.py`.
- **The tool prices — inside a derived scope (session 28).** `src/report/recommend.py` ranks
  plans only for households the PG&E specs can be shown to describe and refuses by name
  otherwise; `test_engine_wasm.mjs` checks dollar parity with CPython to the cent. The
  **load-shape half still never prices**: the jsdom test scans those six regions for
  `$<digit>` and separately asserts `#planTable` IS dollar-denominated, and the `Inspection`
  model may carry no money-shaped field. ⚠ `docs/case-study.json` is built from gitignored
  `data/` and pins the engine digest — **regenerate it whenever `docs/engine.js` changes**.
- **Design (session 32): plain and content-first.** Cameron found the session-12 "tariff
  sheet" (manila, oxblood/sulphur, uppercase wide display type, mono labels, margin rails,
  rotated stamps) overdone and distracting from the content. Now: white page, system fonts,
  one 52rem column, sentence case, modest radius. The two stamps became plain sentences in
  the same places (`.proof` in the hero, `.notabill` under the verdict). **Don't bring
  bespoke ornament back.** Details in the `design-system` skill.
- **One colour rule is load-bearing: `--accent` (= `--ox`) means "the expensive hours"** —
  peak bars and the peak caption. Links are `--link`; every other bar is `--mark`.
- **`T = 64`, `BAND_LIFT = 6` and `LABEL_LIFT = 16` on the hour chart are not spare
  whitespace.** They stop the peak-band caption and the band's own overhang colliding with the
  "busiest hour" label, which happens whenever the busiest hour falls inside the band — the
  common case. Broken and re-fixed three times.
- **The render test pins the DOM**, including *exactly* 25 `#hourChart rect` (24 bars + 1 band)
  of which exactly 5 are `var(--accent)`. Adding a decorative `<rect>` to either chart breaks
  it — use `<path>`, `<line>` or CSS. Restructure the markup and update the test **in the same
  commit**, deliberately.
- **jsdom does no layout.** It cannot see a label collision, a clipped caption or an unreadable
  bar. Chromium has caught five such defects across two sessions. **Run the screenshots and
  look.**

## How to run

```bash
conda activate energy-advisor    # env prefix: /home/cameron/miniforge3/envs/energy-advisor
PYTHONPATH=src python -m pytest -q                          # measure the count; golden tests skip if data/ absent
ruff check . && ruff format --check .
PYTHONPATH=src python scripts/reconcile_report.py           # 11 line-item comparisons (the trust artifact)
PYTHONPATH=src python scripts/reconcile_report.py --write-readme
PYTHONPATH=src python scripts/rate_optimizer.py             # M2 ranking + sensitivity + assumption audit
PYTHONPATH=src python scripts/nem3_report.py                # M3 solar+battery (REAL SDG&E rates, SYNTHETIC load)
PYTHONPATH=src python scripts/inspect_export.py FILE.csv    # inspect any Green Button export (no pricing)
PYTHONPATH=src python scripts/build_web_engine.py           # regenerate docs/engine.js after touching src/
npm install --prefix tools && node tools/test_engine_wasm.mjs && node tools/test_tool_render.mjs
pip install playwright && python -m playwright install chromium   # optional local extra, NOT in CI
PYTHONPATH=src python scripts/screenshot_site.py            # LOOK at the pages; jsdom does no layout
PYTHONPATH=src python scripts/audit_layout.py               # reflow, heading order, th/scope (Playwright)
python scripts/contrast_matrix.py                           # contrast derived from site.css tokens
PYTHONPATH=src python scripts/build_case_study.py           # after build_web_engine.py; needs data/
PYTHONPATH=src python scripts/build_acc_tables.py --utility 'SDG&E' --vintage 2026 --source FILE.csv --citation '...'
PYTHONPATH=src python scripts/build_acc_tables.py --utility 'PG&E'  --vintage 2026 --source FILE.csv --citation '...'
```

One importer serves both utilities: SDG&E and PG&E publish the same MIDAS shape and differ
only in the RateLookupID prefix and the capitalisation of the unit string. Sources —
**SDG&E** `sdge.com/solar/solar-billing-plan/export-pricing` (one zip per vintage), **PG&E**
`pge.com/eecvalues` (**one 36 MB zip holding all five vintages**). `pge.com/energyexportcredit`
is a *different* bundle — the printed PDF price sheets, one calendar year each — and is the
cross-check, not the import source.

## Headline results

**M0/M4 reconciliation** — 11/11 within ±$2, worst **+$0.22** (0.43% of that bill), all
positive, total +$1.55 on $1,084.26 billed. The one-sided residual is explained rather than
hidden: ~0.3 kWh meter-read boundary plus the 2025 franchise-fee approximation.

**M2, PG&E household** (4,345 kWh / 328 days) — **SWITCH to E-TOU-C + PG&E bundled generation,
$170.72/yr cheaper.** The saving is **leaving the CCA, not changing schedule**: PCIA +$159.88/yr,
UUT on it +$13.59, franchise fee +$2.54, while 3CE generation is only $4.85/yr cheaper. Caveat
printed in the report: PG&E Rules 22.1/23.1 require six months' notice, with Schedule TBCC in
between. Sensitivity: E-1 overtakes only if evening usage grew 353%, or 132% load-neutral.

**M3 demo** (bundled SDG&E TOU-DR1, coastal_basic, **synthetic** 6,264 kWh load, 5 kW, calendar
2026, **five** rate versions per layer): baseline $3,056/yr; solar only $1,870; +battery greedy
$512; LP $433; NBC import floor $86/yr. **The dollar totals are real; the LOAD is not** — these
figures are deliberately absent from every public document. (Session 18's 8/1 vintage moved
these ~0.1% and reordered nothing; paybacks 8.9 / 7.4 / 7.2 yr are unchanged. Worth noting the
baseline rose while delivery *fell* — a summer-peaked load feels the generation increase more.)

## Publishing and CI

- **CI:** two jobs, both green on `main`. `test` runs ruff + pytest; `web` runs the browser
  tool's wasm-parity and jsdom render checks. **Golden-bill tests SKIP in CI by design** — they
  need the gitignored real export — so a green badge proves engine/schema/loader/tariff
  identities, **not** the ±$2 reconciliation. Said in the workflow header so it cannot overclaim.
- `main` is the default branch and holds everything. The old `session-4-nperiod-tou-m2` still
  exists on the remote as a redundant copy — safe to delete.
- ⚠ `docs/index.html` carries a full `<!doctype html>` wrapper for Pages. Republishing it **as
  an Artifact** requires stripping doctype/html/head/body first. Pages is canonical.
- ⚠ The `LICENSE`/README copyright line reads "Cameron Gordon" — inferred; correct if wrong.
- **`privacy.html` and `terms.html` are plain-language and will never be lawyer-reviewed.**
  **Cameron's standing decision (2026-09-16): treat "no lawyer, ever" as a constant, not a
  pending task.** This is a personal project for his own use, so a legal review was never
  going to happen and leaving it on the list made M5 look blocked on something nobody
  intended to do. Both pages were completed to the best of the assistant's ability in session
  28 — terms gained the counterparty, acceptable use, third-party services, governing law and
  venue, severability/waiver/entire-agreement and an age line; privacy gained the controller,
  CCPA/CPRA, DNT/GPC and retention. **What remains true and must stay on the pages: they say
  plainly that they were written by the author and not by a lawyer.** Keep them accurate as
  the site changes; that is the whole maintenance obligation now.
  - ⚠ Both pages now **name "Cameron Gordon" as the counterparty and controller**, following
    the README copyright line — which the note below still marks as *inferred*. If that name
    is wrong it is now wrong in three places.

**Two GitHub gotchas, recorded so nobody re-debugs them:**
1. `pages.yml` has a `paths: ["docs/**"]` filter, and path filters do **not** reliably match
   when a branch is *created* rather than updated. `workflow_dispatch` is on the workflow for
   exactly this.
2. Enabling Pages auto-creates a `github-pages` environment whose deployment branch policy is
   pinned to the then-default branch, which made `main` deploys fail with "Branch main is not
   allowed to deploy to github-pages due to environment protection rules". Fix:
   `gh api --method POST repos/<owner>/<repo>/environments/github-pages/deployment-branch-policies -f name=main`

## Field note — fetching a 403-guarded PDF

sdcommunitypower.org returns **HTTP 403 to `curl`**, even with a browser user-agent. Session 9
concluded the sheet was unreachable and deferred the whole SDCP overlay to a manual download.
**It was reachable the whole time.** The agent's own `WebFetch` gets through and, although it
cannot parse a PDF, it **saves the raw bytes to disk anyway** and prints the path:

```
WebFetch <pdf-url> (any prompt)  ->  copy the saved path out of the result
  ->  /home/cameron/miniforge3/envs/energy-advisor/bin/pdftotext -layout <path> out.txt
```

**Generalise: "curl got 403" is not "the document is unavailable."** Try the other fetcher
before asking a human or recording something as blocked. The rates were *also* on the site as
HTML, on two cohort pages the landing page links but does not name — they matched the PDFs
cell for cell.

## Open decisions

1. **SDG&E super-off-peak window — RESOLVED, modeled per-vintage.** Year-round from 2026-05-01;
   earlier vintages carry `months: [3, 4]`. Both forms pinned by `test_sdge_vintages.py`.
   Residual caveat, **restated more sharply after the session-15 cross-check** — it is no longer
   just "the advice letter was never located":
   - **SDG&E's filed tariff sheet still says March and April.**
     `sdge.com/sites/default/files/elec_elec-scheds_tou-dr1.pdf` — the *current and effective*
     tariff-book PDF, retrieved 2026-09-08 — prints "Excluding 10:00 a.m. – 2:00 p.m. in March
     and April" on Cal. P.U.C. Sheets 29952–29955-E, Advice 3167-E, eff. Jan 1 2018. **That is
     why no superseding letter was ever found: the tariff book was never updated.** It is not
     proof the window did not change (the same PDF still carries 2018 *rates* — SDG&E moves
     rates via Total Rates Tables and the book lags), but no filed document supports 5/1.
   - **The change itself is now corroborated by a fourth, non-CCA party.** `corruptbear/my_sdge`
     held an `is_march_or_april` condition for years and deleted it in commit `be51c303`
     (2026-06-10, "apply extended super-offpeak hours").
   - **The 5/1 DATE is not corroborated by them** — their windows live in code with no effective
     date, so they cannot distinguish 5/1 from 6/1. The date still rests on SDG&E's
     customer-facing publications plus dated CCA sheets (SDCP's, whose body reads "Effective
     May 1, 2026", is the strongest single document).
   Our per-vintage split is right *because* it survives being wrong about the date: one file
   changes. Full detail in `notes/spec_crosscheck_2026-09.md`.
2. **TOU-DR-P — RESOLVED session 21, both halves.** It loads and bills; the schedule now has
   delivery *and* generation layers and is inside every structural gate.
   - **Windows: sourced, not inferred.** The old note said the sheet was undiscoverable. It
     was the wrong filename: TOU-DR-P is not its own UDC schedule. Its rate table's note 1
     says "the UDC rates associated with service under **Schedule TOU-DR** and the generation
     rates associated with **Schedule EECC-TOU-DR-P**", and both sheets are public
     (`elec_elec-scheds_tou-dr.pdf`, `elec_elec-scheds_eecc-tou-dr-p.pdf`). They agree with
     each other and turn out to equal TOU-DR1's; all 576 hour-cells are pinned.
   - **Events: option (a)+(b).** `EventAdder` on the generation layer, and `event_days` is a
     **required** argument to `compute_bill` that raises `MissingEventDaysError` when
     omitted — the `territory`/`vintage` pattern. `[]` prices the zero-event case explicitly.
     Supplying more than the tariff's 18/year cap also raises.
   - ⚠ **The tariff book's RYU hours are STALE.** Sheets 29436-E / 29437-E still print
     2–6 p.m.; the window moved to **4–9 p.m. on 2022-06-01**. Confirmed by SDG&E's
     pricing-plans page and by every TOU-DR-P event row in its monthly CPUC DR filings. Do
     not "correct" `hours: [[16, 21]]` off the sheet — a test fails if you do.
   - ⭐ **What SDG&E actually called**, from its own year-end CPUC filings: 2020 **9**, 2021
     **0**, 2022 **0**, 2023 **0**, 2024 **3** (Sep 5/6/9), 2025 **0**, 2026 **0** through
     July. Against a cap of 18. That gap *is* the modeling problem: zero is both the most
     likely single year and the assumption that makes the schedule look free.
   - ⭐ **The event count decides the verdict, not the rates.** One summer event day cancels
     ~6.7 ordinary summer days of on-peak saving (1.00928 / 0.15072 per kWh); a winter one
     cancels ~47. On a flat load over one summer, TOU-DR-P beats TOU-DR1 at zero events and
     loses by >10× that margin at the cap. Pinned by test.
   - ⭐ **TOU-DR-P is bundled-only** (EECC-TOU-DR-P is closed to DA/CCA), so it must be
     dropped for any SDCP/CEA customer *before* any event modeling. And **no Bill
     Protection** for anyone enrolling now — SC 1 closed to new requests on 2015-12-31.
   - **RESOLVED session 27 — by deciding NOT to forecast.** `src/scenarios/tou_dr_p.py`
     (+ 9 tests). All three candidate rules were rejected: *hottest N days* needs a
     temperature feed and conflates "hot" with "an event was called" (2021-23 and 2025-26
     all had hot days and zero events); *last year's dates* flips the whole answer on which
     year it lands on; *Monte Carlo* is right in spirit but six complete years is a thin
     base and a Poisson fit puts ~14% on zero where the data shows two thirds. Each commits
     to a number the evidence cannot support.
     Instead the engine selects **no days** and reports the break-even: the saving at zero
     events, the cost per event day, the count at which they cancel, and how often SDG&E has
     historically exceeded that count. `BreakEven` has no field capable of expressing a
     forecast, which is stronger than choosing not to make one.
   - ⭐ **The finding that made this worth more than a forecast: break-even RISES with
     evening load**, so TOU-DR-P splits households into three genuinely different
     situations — *little evening load* loses at zero events (don't switch); *moderate*
     gains but a lawful event year can cancel it; *heavy* gains and even the 18-event cap
     cannot cancel it. A flat load breaks even at ~15 events, inside the cap. A single
     forecast number would have collapsed all three into one answer.
   - ⚠ **A stated, unquantifiable bias.** Per-event cost uses the household's MEAN weekday
     16:00-21:00 load, but an event is called on a hot day when that load is higher. So the
     true break-even is strictly lower and every figure is optimistic for TOU-DR-P. The
     direction is asserted by test; quantifying it would require the forecast this decision
     rejects.
   - **Also corrected here:** the event history is now machine-readable
     (`EVENTS_CALLED`), and the counts are **four zeros in six complete years, mean 2.0** —
     HANDOFF previously implied five in seven by counting partial 2026 as a year.
3. **SDG&E baseline allowances — RESOLVED, and re-verified session 15.** Full climate-zone table
   (Sheet 29294-E) in every TOU-DR1 vintage; `territory` supplied at bill time, and omitting it
   raises. All sixteen cells re-read off Schedule DR SC 3 on 2026-09-08 and matched exactly.
   Worth knowing: an independent transcription got the **All-Electric** rows wrong while getting
   Basic right (it had winter coastal all-electric *below* Basic, which is backwards). The
   all-electric rows are the ones nothing in this repo currently exercises — do not assume they
   are load-bearing-tested just because `coastal_basic` is.
4. **CARE rates on PG&E counterfactual schedules are DERIVED, not printed**
   (`care = 0.65 × standard − 0.01038`). Validated to ≤1e-5 on E-TOU-C, cross-checked against
   E-1's printed tier pair, corroborated by SDG&E's printed "CARE Discount 35%". `--no-care`
   gives the tariff-only ranking. On SDG&E the split is exact on all four vintages.
5. **Santa Cruz UUT Adjustment — RESOLVED as a modeling assumption**, mechanism still
   UNVERIFIED. Adopted **$0.21649/day**. Schedule-independent, so it cannot reorder the ranking;
   the optimizer re-ranks under all three mechanisms to prove it.
6. **Which CCA and which schedule dad is on** — unresolvable without a bill, but **no longer
   blocking**: both San Diego CCAs are authored. Still needed from the bill: schedule, climate
   zone, CARE status, bundled vs CCA, **which SDCP cohort**, and the **PCIA vintage**.
7. **Privacy posture — RESOLVED session 7.** Self-attributed case study; CARE disclosed; exact
   dates and amounts kept; personal-tenancy detail scrubbed.
8. **Rate-date vs window-date splitting — RESOLVED session 8.** When a period-definition change
   lands inside a rate vintage, split the vintage and duplicate the rates rather than backdating
   a new window onto a citation-bearing spec.
9. **CARE on a CCA — OPEN, and the two sources CONFLICT. Worth ~$170–210/yr.**
   *Settled:* what the CCA charges. Both CEA's mapping table and SDCP's Rate Key say the CCA
   bills one generation rate regardless of CARE status, so both specs set `care == standard`.
   Read off the sheets, not assumed.
   *Unsettled:* how SDG&E **composes** the discount for a CCA customer.
   - The engine today discounts SDG&E's own charges only, implying a CARE CCA customer gets a
     *smaller* absolute discount than a bundled one (by 0.35 × EECC).
   - **SDG&E's own SDCP Joint Rate Comparison implies otherwise**: `(CCA total − SDG&E total)`
     is **invariant to CARE/FERA status** across four schedules and all three SDCP products
     (≤2e-5 in 11 of 12 rows), which can only hold if the discount is computed on the
     bundled-equivalent bill.
   - **Against it: 11 real PG&E bills** for a CCA + CARE household reconcile within +$0.22 with
     the discount on the delivery layer only. A reconciled bill outranks a comparison document,
     and the JRC's per-line allocation is provably presentational — but the class-invariance is
     a totals-level fact, so it survives. PG&E and SDG&E may simply compose it differently.
   **The engine was deliberately NOT changed.** Resolve against a real SDG&E CCA CARE bill.
   Both spec headers carry both sides.
10. **`PerKwhAdder` has no CARE variant**, so the vintaged PCIA is billed class-independently.
    That matches what SDG&E's CARE table prints, so it is not currently wrong — but it is
    unmodelable if a future sheet differentiates.

## Blocked on data (not on work)

- **M1 DoD — SPLIT IN TWO on 2026-09-16 (session 28), at Cameron's decision.** Dad is no
  longer a source, and a DoD naming one person was unreachable by anyone else. See ROADMAP.
  - **M1a — charge layer:** three real SDG&E statements' printed dollars within ±$2 **from
    their own per-TOU-period kWh**, no interval data. Needs bills only — *one ordinary
    non-solar household*. ⚠ The public 26-bill corpus **cannot** meet this: its statements
    are NEM-2 true-up accruals, measured in `notes/m1_without_dad_2026-09.md`.
  - **M1b — interval layer:** one household's export priced end to end against its own bill.
    The half that tests the parser and the interval→TOU-bucket step.
  - Both harness paths exist (sessions 24 and 29). What still stands between a real SDCP
    bill and a pass is the **fee lines** in next-action #2 (session 31).
- **M3 DoD** — one real household with solar/export interval data.
- **Full validation of `src/greenbutton/sdge.py`** — five real exports met (sessions 13, 23),
  including 15-minute, both DST transitions and a populated export register. Still unseen:
  any export paired with its own bill (M1b).
- **M2's PG&E cross-check is unavailable, not pending** — PG&E's Rate Plan Comparison returns
  "no service agreement eligible for rate enrollment" for this account. `--pge-comparison FILE`
  is built and waiting.

## Flagged approximations (all sub-$0.05, non-blocking)

- **2025 franchise fee** — 2026 specs use the exact E-FFS per-kWh rate ($0.00059); 2025-vintage
  specs still carry the percent-of-energy approximation. One of the two documented causes of the
  one-sided residual.
- **2025 summer generation credit** still bill-fitted (the 2026 one is tariff-exact).
- **California Climate Credit — RESEARCHED AND TABULATED session 27; still an observed line,
  deliberately.** `src/tariffs/climate_credit.yaml` (cited, CPUC + both utilities, retrieved
  2026-09-16) + `tests/tariffs/test_climate_credit.py`.
  - ⚠ **The old note here was wrong twice.** "SDG&E files $(33.50) semi-annually" is stale —
    2026 is **$49.36 × 2 = $98.72**. And "generalise to a versioned semiannual credit" would
    have built the wrong thing: **the CPUC moved the residential ELECTRIC credit out of
    April/October into AUGUST/SEPTEMBER for 2026** (voted 2026-04-30). A model carrying the
    old months forward applies 2026's credit to the wrong bills.
  - **PG&E 2025 $58.23 (Oct) · PG&E 2026 $36.18 ×2 (Aug/Sep) · SDG&E 2026 $49.36 ×2.**
  - ⭐ **Two independent cross-checks, both hold and both are now tests.** The published PG&E
    2025 figure equals the observed line on the real 10/28/2025 statement **to the cent**;
    and SDG&E's $98.72/yr is $8.23/average month, which is exactly the **$8/month** all three
    2026 rate alerts imply — outside corroboration of a figure the tier-2 corpus could only
    derive. ($33.50 × 2 would give $5.58, which rounds to $6 and fails.)
  - ⭐ **The "missing" second credit was never missing.** 11 golden bills span 11 months and
    carry exactly ONE credit. Correct: April 2026 had none (schedule moved) and the Aug/Sep
    2026 payments fall after the last bill (2026-06-25). A test asserts the corpus still
    ends before 2026-08-01, so adding a later bill forces this to be revisited.
  - **NOT wired into `compute_bill`, and that is a decision.** It is **ranking-neutral** —
    a flat per-household amount, independent of schedule, usage, CARE and climate zone — so
    it cannot reorder an M2 comparison; it only moves an absolute annual figure, by $72–99.
    Modeling it needs a rule for WHICH statement receives a credit "applied in October", and
    exactly one credited bill exists, which cannot distinguish the candidate rules. Settle
    that against a second credited bill before wiring it in.
- **CEC surcharge on SDG&E** — PG&E specs carry $0.0003/kWh; SDG&E's Total Rates Tables show no
  such column. ⚠ **Session 31: the SDCP specimen bills it** ("State Surcharge Tax", 251 x 0.0003
  = $0.08, on the CCA side). Build it with next-action #2.
- **SDG&E minimum bill** ($0.329/day, CARE $0.164) comes from the 2018 sheet; no 2026 table
  restates it. Confirm before shipping a figure that depends on the floor binding.

## M3 open items (recorded, none blocking)

- ~~SDG&E ACC Plus unconfirmed~~ — RESOLVED session 14: $0.000/kWh, all segments, D.22-12-056 Table 7. Encoded as a cited zero table, not a raise.
- ~~PG&E ACC tables not imported (PDFs, not MIDAS CSVs)~~ — RESOLVED session 19. **PG&E does
  publish MIDAS CSVs**, at `pge.com/eecvalues` (one 36 MB zip, all five vintages); the PDFs at
  `pge.com/energyexportcredit` are a separate customer-facing bundle. One parser now serves
  both utilities. All five PG&E vintages (2023/2024/2025/2026/current) are committed.
  Remaining gap: **no 2027 vintage for either utility** — 2027 is the last application year
  that qualifies for a lock-in at all, so a "should I apply in 2027?" question still raises
  `MissingAccTableError` rather than answering. SDG&E likewise has no 2023/2024 table; nobody
  has needed one.
- **LP dispatch is a marginal-price optimum, not a settled-dollar optimum** — under NBT caps it
  can settle below greedy. Documented and reported honestly; not a bug.
- **CCA export terms** — netting excludes the CCA generation credit by default (Schedule NBT
  SC 2.a), so a CCA customer's result is a lower bound until supplied.

## Schema gaps (recorded, none blocking today)

- `PerKwhAdder` has no CARE variant (worked around on SDG&E by folding WF-NBC/DWR-BC into the
  energy `Rate`).
- **FERA / DRAH** (0.39688/day, printed on every SDG&E 2026 sheet) unmodelable — `Rate` has only
  `standard`/`care`.
- No `tiers` concept. Correct for E-1 today (an exact identity via the baseline credit);
  required if a third distinct tier price appears.

---

Do **not** build CLI / API / Docker / deployment — roadmap "Later", gated behind the M5
verdict. (The web UI half of that rule was formally overridden in session 28: the site prices.)
