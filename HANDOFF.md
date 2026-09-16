# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it current: state,
how to run, open decisions, exact next action._

## Status _(2026-09-09, end of session 24)_

**M0, M2 and M4 are done. M1 and M3 have complete, tested engines whose DoDs are blocked on
data that does not exist yet. Do not fabricate a load or a bill to "finish" either.**

**1,607 tests green · ruff clean · 11/11 PG&E golden bills within ±$2 (worst +$0.22) ·
both CI jobs green as of session 24.**

> The working tree is **not** clean: session 25's tier-2 work (fixture, README, test) and the
> CLI-PLAN phase-B notes are uncommitted. `git status` is the authority, not this line.

> **⚠ Do not read a commit count here.** Measure it: `git fetch -q origin && git rev-list
> --count origin/main..main`. Every session that copied a number forward published a wrong one
> — three times running, in both directions — because it was a cached value with no
> invalidation. **So this line states no number.** What it states instead stays true as it
> ages: **everything through session 24 is pushed**, and session 24 left nothing uncommitted.
> A later session that has committed but not pushed makes that sentence stale in the one
> direction a reader can detect by measuring.

| Milestone | State | What is missing |
|---|---|---|
| M0 — PG&E reconciliation | **Done** | — |
| M1 — SDG&E + CCA overlay | **Engine complete, DoD blocked** | one real SDG&E export + 3 bills |
| M2 — Rate optimizer | **Done for PG&E** | the SDG&E household; utility cross-check unavailable |
| M3 — NEM 3.0 solar + battery | **Engine complete, DoD blocked** | one real household with export data |
| M4 — Public methodology | **Done, live** | — |
| M5 — First external users | **Materials drafted** (`RECRUITING.md`), nothing sent | gated on M1 — see the warning below |

- **Repo:** https://github.com/CameronGordonn/energy-advisor (public, AGPL-3.0)
- **Site:** https://camerongordonn.github.io/energy-advisor/ — a working tool, four pages.

> **⚠ CONTEXT.** The Santa Cruz PG&E service ended July 2026; the last export in `data/` runs
> to 2026-07-18, and the final statement is probably unreachable. The 11 committed golden
> bills are unaffected. Cameron has **no plug-in EV**, so EV2-A / EV-TOU-5 are filtered out of
> rankings by default.

---

## THE BINDING CONSTRAINT — read before planning anything

**This project is data-starved, not code-starved.** Every engine on the SDG&E side is written
and tested; none of it has ever met a real SDG&E bill. Almost all remaining *code* work is
low-value polish — **but check that claim against the harness before believing it of a given
path.** Session 24 found the reconciliation harness still PG&E-hardcoded while this file
asserted the opposite, i.e. the "just add data" story was true of the specs and false of the
code that would have consumed them. That gap is closed; the lesson is that "ready" should be
demonstrated by a test, not by a sentence.

The one input that changes the project's state is **a real SDG&E Green
Button export plus three itemised bills**, and it unlocks M1, the SDG&E half of M2, and the
right to show any San Diego user a dollar figure.

Dad was the expected source and had not delivered as of 2026-09-09. **Treating him as the only
source is a single point of failure.** The sequencing rule in the M5 warning already says
recruit for data before sales — so the highest-leverage action available without him is to
**recruit one SDG&E household as a validation user**. That closes M1's DoD and starts M5 at
the same time.

**Session 23 searched the public internet for a substitute and there is none.** The public
corpus is now six real exports across two repos (up from one), plus one MIT-licensed corpus of
26 itemised SDG&E bills — but **the exports and the bills belong to different households**, so
nothing public can reconcile a dollar. The search is done; do not re-run it. What it bought is
a much harder-tested parser, not a milestone. See `notes/sdge_public_exports_2026-09.md`.

---

## ⚠ SESSION 25 UPDATE (2026-09-15) — read with the status above, which is otherwise unchanged

**No milestone moved.** M1 and M3 remain blocked on the same data. What changed:

1. **A second test tier exists and is live: `tests/published_impacts/`.** Utility-published
   bill-impact figures from rate-change notices. Public documents, so **committable and
   CI-runnable**, unlike `tests/golden_bills/`. **Nothing in it counts toward the ±$2 claim**
   — no meter, no period, no interval data. Its README carries the boundary and
   `test_no_src_module_references_this_tier` now enforces the half of it that can be
   enforced: nothing under `src/` may reference these figures. 25 tests (stream A).
   **The test covers the April 2026 fixture only.** Stream B's further fixtures land
   untested; generalising the test across fixtures is cheap and is the obvious next step —
   each rate change is an independent regression point on the same spec family.

2. **Next-action #2 is partially answered — by a figure, not a bill, and now by a test.**
   SDG&E's April 2026 rate alert publishes $123/month for 400 kWh on **schedule TOU-DR1**
   unbundled. Priced **through `compute_bill`** over the twelve months from the spec's own
   effective date, `sdge_tou_dr1_delivery_2026-04-01.yaml` gives **$123.48 at baseline
   territory `coastal_basic`, and no other territory lands within ±$0.50** (next nearest
   $122.35). CARE $66.79 vs published $67. So the delivery layer's energy rate, fixed charge,
   baseline allowance and baseline credit have outside corroboration — **the first ever to
   touch TOU-DR1** — and it is a permanent gate, not a one-off measurement.
   - ⚠ **The climate zone is NOT pinned by this, and an earlier draft of this entry said it
     was.** Stream B checked Jan and Jun 2026 the same way and `coastal_all_electric` wins
     both. The two coastal territories sit a stable ~$1.05–1.13 apart while the published
     figure is a whole dollar carrying a ~$0.5–0.9 band, so rounding decides the contest, not
     evidence. **What does hold: the six non-coastal territories are >$2 off in every quarter
     checked.** `coastal_basic` stands on a **domain prior** — SDG&E Sheet 29294-E makes
     All-Electric available only on application — not on arithmetic. The April test is
     correct within April and must not be copied to another quarter unedited; it would fail.
     See `notes/published_impacts_corpus.md`.
   - **Shape independence is proved by the engine**, not read off the YAML: five allocations
     spanning all-on-peak to all-super-off-peak agree to 1c (per-line rounding). That is why
     this is a point test and why invariant 6 is not in play for the delivery half.
   - **Generation stays near-zero information and now asserts its own weakness.** Envelope
     $30.73–$122.31 against an implied $71: it accepts 95.6% of its own width. Measured by
     mutation: a 10x decimal shift on one generation cell does NOT trip it; scaling every
     rate by 1/10 does.
   **This is corroboration, not reconciliation. Next-action #2 still wants a bill.**

3. **One load-bearing inference, encoded but still unsettled.** A CCA customer pays the
   vintaged PCIA, but the arithmetic only matches with PCIA excluded. The test names it —
   `PCIA_EXCLUDED_BY_INFERENCE = Service.BUNDLED` — and the test
   `test_the_pcia_exclusion_is_load_bearing` asserts that no vintage in the table reaches the
   published figure (nearest, 2009, is $6.63 out), so
   a future edit that made one match fails loudly instead of inverting the assumption
   silently. **It is still an inference about what SDG&E's number means.** Stream B settles it
   across several quarters; one quarter cannot separate policy from coincidence.

4. **CLI-PLAN phase B is half done.** Skill frontmatter written; the JSON schema and skill
   body are Cameron's and are the critical path. Decisions D1–D5 recorded. Sources for
   calibration are now on disk in `data/sources/` (gitignored).

5. **Correction to next-action #0's search note.** Session 23 settled that no public
   household publishes an export *and* its bills — still true. Session 25 re-searched and
   found a **different artifact class** (published bill-impact figures), which is what item
   1 above is built on. Do not re-run either search.

**Paste-ready prompts for the next sessions, including a parallel-stream split with model
and effort per stream: `notes/session25_handoff_prompts.md`.**

_This is an insert, not the full rewrite CLAUDE.md asks for at a pause. The status table
above and the next-action list below remain accurate; a wholesale rewrite would have
discarded accumulated context this session did not read in full. Next session that
completes a milestone should do the real rewrite._

---

## EXACT NEXT ACTION

**0. Check for dad's SDG&E data first, every session.** `ls -lt data/` — look for anything
SDG&E-shaped. Not arrived as of 2026-09-09 (`data/` unchanged since July 19; PG&E only). If it
has landed it outranks everything below.
  - **First command:** `PYTHONPATH=src python scripts/inspect_export.py FILE.csv`. It
    auto-detects the utility and reports interval length, coverage, gaps, DST handling and any
    export register **before anything tries to price it**.
  - **The parser has now met FIVE real SDG&E exports, and refused three of the five on first
    contact.** Sessions 13 and 23. Every refusal was a stated fact about "the" SDG&E format
    being wrong: `Duration` instead of `END TIME` and 12-hour times (13); a **true 25-hour DST
    fall-back day** where PG&E sums both hours (13); a **two-digit year** `3/1/24` against a
    hardcoded `%m/%d/%Y` (23). All fixed and tested. **Expect a sixth file to break it a fourth
    way; budget the session. If it refuses the file, fix the parser, not the file.**
  - **What session 23's corpus survey settled, so it is not re-hunted** — full detail in
    `notes/sdge_public_exports_2026-09.md`. **15-minute, spring-forward and a populated export
    register are now all exercised** against real files: a full year of 15-minute NEM data
    spanning both 2024 DST transitions, Apache-2.0, from `steevschmidt/NEC-220.87-Methods`.
    `Net` **is** pre-netted, and `Total Usage` on a solar account is the **NET** sum, not the
    consumption sum. **None of that closes M1** — no public household publishes an export
    *and* its bills.
  - **What the bills must tell us:** schedule, climate zone, CARE status, bundled vs CCA — and
    if a CCA, which one, which SDCP cohort, and the **PCIA vintage** (which moves more money
    than the choice of CCA does).
  - ⭐ **The harness is now utility-general, so the answer to "what stands between his bill and
    a reconciliation run" is: nothing but transcription.** _(Session 24. The old wording here —
    "no overlay work stands between his bill and a reconciliation run" — was **wrong**: the
    SPECS were ready, the HARNESS was not. It globbed PG&E's filename, called PG&E's parser
    regardless of the fixture's `utility:` field, and called `compute_bill` with no territory,
    no vintage and no event days, so an SDG&E fixture could not have been priced at all.)
    **Copy `tests/golden_bills/sdge_TEMPLATE.yaml.example` to `sdge_<MM-DD-YYYY>.yaml`, fill
    in the `customer:` block and the printed dollars, drop the export in `data/`, run
    `PYTHONPATH=src python scripts/reconcile_report.py`.** The harness picks the SDG&E parser
    off the fixture's `utility:`, finds the export by SDG&E's own filename patterns, and
    refuses the fixture BY NAME if the climate zone, PCIA vintage, supplier or event days are
    missing. See session 24 in SESSION_NOTES.md.
  - **If he is CARE *and* on a CCA**, check open decision 9 first, before anything else.

**1. Recruit one SDG&E validation user.** The unblock that does not depend on dad. Ask for a
13-month interval export plus three itemised bills; be explicit that they are validating an
engine, not buying a verdict. See the M5 warning for why this ordering is not optional.

**2. Get an SDG&E bill in front of the TOU-DR1 specs.** Session 23 audited the one piece of
outside evidence and it came back clean — but for the wrong schedule. 26 itemised bills in
`ookla-ariel-ride/SDGE-Analysis` (MIT) turn out to be an **EV-TOU-5** household, and against
EV-TOU-5 our rates reproduce the printed ones **exactly**: six cells across three vintages
all differ by precisely 0.02099, which is the NBC/PPP bundle our specs itemise and SDG&E
prints as separate line items rather than inside the Rate/kWh row. Pinned by
`test_our_delivery_rate_less_the_import_floor_is_what_sdge_printed`.
  - **What that buys:** invariant 4's import floor (0.02099/kWh; 44.6% of EV-TOU-5's
    super-off-peak delivery charge, 6.5% elsewhere) is confirmed against a real bill, and
    open decision 1's 5/1 window-only filing gains outside corroboration.
  - **What it does NOT buy:** it is corroboration, not reconciliation — unaudited extraction,
    NEM-2-netted kWh, no interval data. And **TOU-DR1's period-flat UDC — the ⭐ fact that
    100% of its TOU signal lives in generation — is still unvalidated by any bill.** That is
    the schedule almost every SDG&E household is actually on, and the one M1 needs. Note the
    irony worth carrying: the only externally validated SDG&E schedule is EV-TOU-5, which is
    filtered out of rankings by default because Cameron has no EV.
  - ⭐ **Session 25 stream A changed what "unvalidated" means here, precisely.** TOU-DR1's
    **delivery** layer is now corroborated against SDG&E's own published figure, by a test
    that goes through `compute_bill` — energy rate, fixed charge, baseline allowance, baseline
    credit, and it pins the climate zone. **TOU-DR1 GENERATION is still unvalidated by
    anything**, and that is where 100% of the schedule's TOU signal lives, so every load-shift
    and battery conclusion on the schedule still rests on untested numbers. The feasibility
    test over the published bundled figure accepts 95.6% of its own width and must not be
    described as corroboration. **A bill is still the ask, and generation is the half it has
    to price.**

**3. Wire TOU-DR-P into a ranking — but decide the day-selection rule first.** The engine
half is done (session 21: it loads, bills, and refuses to price without an explicit event
assumption). What is missing is (b), the reporting band, and it is blocked on a modeling
decision rather than on code: a forecast has to choose WHICH days to assume, and "hottest N
days", "last year's actual dates" and "Monte Carlo over count and timing" give materially
different answers. Surface it as a decision. Note this is gated behind the SDG&E candidate
set anyway — `ALL_PGE_CANDIDATES` is still the only one — which is itself gated on a real
household. See open decision 2.

**4. The 2027 ACC vintage, when either utility publishes it.** 2027 is the last application
year that earns a nine-year lock-in, so it is the last vintage the "when to install" question
can ever turn on — and neither utility's 2027 table exists yet. Until it does,
`Vintage(application_year=2027, ...)` raises `MissingAccTableError`, which is the correct
behaviour, not a bug. Re-check `pge.com/eecvalues` and SDG&E's export-pricing page; the PG&E
zip currently served was built 2024-12-18, so PG&E has not refreshed even its floating NBT00
table since then.

> **⚠ READ BEFORE STARTING M5 — M1 and M5 are coupled.** M5 targets San Diego (SDG&E) users,
> and **the engine has never reproduced a single real SDG&E bill.** (The *parser* has now met
> one real export — session 13 — which is a different and much weaker claim.) The
> rate specs are tariff-exact across all five 2026 vintages — calendar 2026 is now covered
> end to end, 8/1 being the last vintage SDG&E published — which is necessary but **not
> sufficient**: sending dollar figures to five strangers without a reconciled SDG&E bill would
> violate invariant 1 (reconciliation-gated), which is the product's entire trust claim.
> **The consequence is a sequencing rule, and it is good news:** the FIRST recruit who supplies
> an export *plus* three bills closes M1's DoD, and only then does the SDG&E path earn the
> right to produce dollar figures for the other four. Recruit for data before sales, and tell
> the first one or two people plainly what they are. A PG&E recruit needs no such caveat —
> that path is reconciled 11/11.

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
`privacy.html`, `terms.html`. Shared `site.css` (tokens + chrome) and `fonts.css`
(`@font-face` only). **Fonts are self-hosted; the site requests nothing from Google.**

- **The tool runs the REAL Python parsers** under Pyodide/WebAssembly — not a JS port, so there
  is one tested implementation. Nothing is uploaded because there is no server.
  `docs/engine.js` is **generated** from `src/` by `scripts/build_web_engine.py`, and
  `tests/report/test_web_engine.py` fails if it goes stale. Rebuild after touching
  `src/greenbutton/` or `src/report/inspect.py`.
- **The tool prices NOTHING, deliberately.** Load shape needs no reconciliation gate; dollars
  do, and that gate is met for PG&E but not SDG&E. **Enforced by tests, not intent** — no
  money-shaped field may exist on `Inspection`, findings may not contain `$`, `¢` or `/kWh`,
  and the jsdom test scans every computed region.
- **Design (session 12): the site is built as the document it is about — a tariff sheet.**
  Two-colour offset print on manila (oxblood + sulphur), **zero border-radius anywhere**, a
  left rail of mono section numbers, ledger rows instead of stat cards, and a rotated
  `NOT A BILL / NO AMOUNT DUE` stamp. Type is **Archivo** (variable *width* axis — one file
  gives the expanded display voice and the body) plus **Space Mono** for every number and label.
- **Two colour rules are load-bearing.** `--sul` is a **FILL, never text** (1.89:1 on paper);
  accent text is always `--ox`. And **`--ox` means "the expensive hours" and nothing else** —
  Fig. 2's month bars are `--mark` for exactly this reason.
- **`T = 64` on the hour chart is not spare whitespace.** It exists so the peak-band caption
  cannot collide with the "busiest hour" direct label, which happens whenever the busiest hour
  falls inside the band — the common case. This has been broken and re-fixed twice.
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
pytest -q                                                   # 1,582 tests; golden tests skip if data/ absent
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
- ⚠ **`privacy.html` and `terms.html` are plain-language, not lawyer-drafted.** They are
  accurate about what the site does. Get them reviewed before M5 puts them in front of
  recruited strangers.

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
   - **STILL OPEN, and it is a new decision, not this one:** *which* days a forecast should
     assume. Reporting the band (b) needs a day-selection rule — hottest N days, the
     historical dates, a Monte Carlo over count and timing — and that is a material modeling
     choice nobody has made. It is not blocking: nothing ranks SDG&E yet.
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

- **M1 DoD** — dad's last 3 SDG&E bills within ±$2, plus the README SDG&E rows. The single
  highest-leverage input in the project; everything SDG&E-facing sits behind it. **As of
  session 24 the only remaining step is transcription**: the harness dispatches, threads and
  gates; nothing in `src/` or `tests/` has to change to price an SDG&E statement.
- **M3 DoD** — one real household with solar/export interval data.
- **Full validation of `src/greenbutton/sdge.py`** — session 13 fixed it against one real
  export (60-min, November). A 15-minute file, and any file spanning March, are still unseen.
- **M2's PG&E cross-check is unavailable, not pending** — PG&E's Rate Plan Comparison returns
  "no service agreement eligible for rate enrollment" for this account. `--pge-comparison FILE`
  is built and waiting.

## Flagged approximations (all sub-$0.05, non-blocking)

- **2025 franchise fee** — 2026 specs use the exact E-FFS per-kWh rate ($0.00059); 2025-vintage
  specs still carry the percent-of-energy approximation. One of the two documented causes of the
  one-sided residual.
- **2025 summer generation credit** still bill-fitted (the 2026 one is tariff-exact).
- **California Climate Credit** modeled as an observed per-bill line (−$58.23 on 10/28). PG&E
  files $(36.18) on Aug/Sep cycles; SDG&E files $(33.50) semi-annually per Schedule GHG-ARR.
  Generalise to a versioned semiannual credit.
- **CEC surcharge on SDG&E** — PG&E specs carry $0.0003/kWh; SDG&E's Total Rates Tables show no
  such column on any 2026 vintage, so it is deliberately NOT asserted either way.
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

Do **not** build CLI / API / Docker / deployment / web UI — roadmap "Later", gated behind the
M5 verdict.
