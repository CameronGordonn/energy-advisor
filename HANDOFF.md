# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it current: state,
how to run, open decisions, exact next action._

## Status _(2026-09-08, end of session 12)_

**M0, M2 and M4 are done. M1 and M3 have complete, tested engines whose DoDs are blocked on
data that does not exist yet. Do not fabricate a load or a bill to "finish" either.**

**418 tests green · ruff clean · 11/11 PG&E golden bills within ±$2 (worst +$0.22) · working
tree clean · `main` pushed · both CI jobs green.**

| Milestone | State | What is missing |
|---|---|---|
| M0 — PG&E reconciliation | **Done** | — |
| M1 — SDG&E + CCA overlay | **Engine complete, DoD blocked** | one real SDG&E export + 3 bills |
| M2 — Rate optimizer | **Done for PG&E** | the SDG&E household; utility cross-check unavailable |
| M3 — NEM 3.0 solar + battery | **Engine complete, DoD blocked** | one real household with export data |
| M4 — Public methodology | **Done, live** | — |
| M5 — First external users | Not started | gated on M1 — see the warning below |

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
low-value polish. The one input that changes the project's state is **a real SDG&E Green
Button export plus three itemised bills**, and it unlocks M1, the SDG&E half of M2, and the
right to show any San Diego user a dollar figure.

Dad was the expected source and had not delivered as of 2026-09-08. **Treating him as the only
source is a single point of failure.** The sequencing rule in the M5 warning already says
recruit for data before sales — so the highest-leverage action available without him is to
**recruit one SDG&E household as a validation user**. That closes M1's DoD and starts M5 at
the same time.

---

## EXACT NEXT ACTION

**0. Check for dad's SDG&E data first, every session.** `ls -lt data/` — look for anything
SDG&E-shaped. Not arrived as of 2026-09-08 (`data/` unchanged since July 19; PG&E only). If it
has landed it outranks everything below.
  - **First command:** `PYTHONPATH=src python scripts/inspect_export.py FILE.csv`. It
    auto-detects the utility and reports interval length, coverage, gaps, DST handling and any
    export register **before anything tries to price it**.
  - **Expect the parser to be wrong.** `src/greenbutton/sdge.py` was written to the documented
    format and **has never been run on a real file**. PG&E's real export surprised us three
    ways: hourly not 15-minute, an inclusive end timestamp, and two DST edge cases. Budget a
    session for parser reality-checking *before* trusting any reconciliation number. If it
    refuses the file, fix the parser, not the file.
  - **What the bills must tell us:** schedule, climate zone, CARE status, bundled vs CCA — and
    if a CCA, which one, which SDCP cohort, and the **PCIA vintage** (which moves more money
    than the choice of CCA does). Both San Diego CCAs are authored, so **no overlay work stands
    between his bill and a reconciliation run.**
  - **If he is CARE *and* on a CCA**, check open decision 9 first, before anything else.

**1. Recruit one SDG&E validation user.** The unblock that does not depend on dad. Ask for a
13-month interval export plus three itemised bills; be explicit that they are validating an
engine, not buying a verdict. See the M5 warning for why this ordering is not optional.

**2. Confirm SDG&E ACC Plus** from an SDG&E NBT sheet. `acc.acc_plus_table` deliberately raises
for SDG&E; `acc_plus_eligible=False` is the conservative path until confirmed. Small, unblocked.

**3. Earlier 2026 vintages for TOU-DR2 and EV-TOU-5** — both exist only at 6/1/2026. Same
method as session 8: fetch `N-1-26 Schedule <ID> Total Rates Table.pdf` and its `-CARE` twin,
`pdftotext -layout`, mirror the vintage split. Only needed to rank those schedules over a
calendar year.

**4. Migrate `docs/methodology.html` onto the shared chrome.** It took the new palette and type
in session 12 but still holds its own copy of the tokens and its own nav/footer rules, which
must be reconciled with `site.css` first (`site.css` sets `th{width:44%}`, which would wreck
its tables — that is why it links `fonts.css` only). Its heading order, `<th scope>` and
200%/400% reflow have never been audited.

**5. PG&E ACC tables** — per-vintage PDFs (pge.com/energyexportcredit), not the clean MIDAS
CSVs SDG&E publishes, so a different parser. Low priority.

**6. TOU-DR-P** — needs an events model before it can be ranked. See open decision 2.

> **⚠ READ BEFORE STARTING M5 — M1 and M5 are coupled.** M5 targets San Diego (SDG&E) users,
> and **the engine has never been validated against a single real SDG&E bill or export.** The
> rate specs are tariff-exact across four 2026 vintages, which is necessary but **not
> sufficient**: sending dollar figures to five strangers without a reconciled SDG&E bill would
> violate invariant 1 (reconciliation-gated), which is the product's entire trust claim.
> **The consequence is a sequencing rule, and it is good news:** the FIRST recruit who supplies
> an export *plus* three bills closes M1's DoD, and only then does the SDG&E path earn the
> right to produce dollar figures for the other four. Recruit for data before sales, and tell
> the first one or two people plainly what they are. A PG&E recruit needs no such caveat —
> that path is reconciled 11/11.

---

## What exists now

- **Engine** (`src/tariffs/`): N-period first-match-wins TOU rules with weekday/weekend/holiday
  day types, month-conditional windows, cited holiday calendars, `Baseline.allowance_multiplier`,
  `MinimumBill`, per-kWh surcharges, `NonBypassable`, `period_codes`, and **`marginal_energy_price`**
  (version-aware per-interval retail price; refuses dates no spec covers; rejects layers that
  classify an hour differently).
- **Specs — 32 files, 16 schedule-layers** (`src/tariffs/specs/`):
  - **PG&E**: E-TOU-C (4 vintages) / E-TOU-D / EV2-A / E-1 delivery, each with matched 3CE and
    PG&E-bundled generation.
  - **SDG&E**: TOU-DR1 delivery + generation in **four 2026 vintages** (1/1, 4/1, 5/1, 6/1);
    TOU-DR2, EV-TOU-5 (6/1 only); TOU-DR-P (deliberately unloadable). Every delivery spec
    carries a `non_bypassable` block and is covered by the NBT-settleability test.
  - **CCA overlay, complete for San Diego**: Clean Energy Alliance
    (`cea_tou_dr1_generation_2026-06-01.yaml`) and San Diego Community Power
    (`sdcp_{2021v,2022v}_tou_dr1_generation_{2026-01-01,2026-05-01}.yaml` — PowerOn, the default
    product; the two jurisdiction cohorts are **separate providers**).
  - Every SDG&E TOU-DR1 delivery vintage carries the **vintaged PCIA** as an `applies_to: cca`
    adder whose vintage is supplied at bill time (`compute_bill(..., vintage="2018")`) and
    **raises if omitted**. `load_specs`/`load_spec_versions` take `provider` and raise when
    several suppliers match — bundled EECC and a CCA are both "TOU-DR1 generation".
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

- **⭐ Delivery and generation change on DIFFERENT dates.** EECC moved 4/1/2026 then held; the
  6/1 filing moved delivery only (UDC 0.34061 → 0.32948). A tool treating "the rate changed on
  6/1" as one event misprices a layer on every bill spanning it.
- **⭐ Four SDG&E vintages, not three.** Rates changed 1/1, 4/1 and 6/1, but the weekday
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
  a 2024 vintage flips 5 of 6.
- **⭐ SDG&E's NBT25 / NBT26 / NBT00 export tables are byte-identical** for every overlapping
  year, so the nine-year lock-in currently confers *zero* dollar advantage on SDG&E. "Lock in
  before rates drop" is an empty pitch here — the opposite of the PG&E vintage story installers
  cite.
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
pytest -q                                                   # 418 tests; golden tests skip if data/ absent
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
```

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
2026, four rate versions per layer): baseline $3,052/yr; solar only $1,867; +battery greedy
$514; LP $436; NBC import floor $86/yr. **The dollar totals are real; the LOAD is not** — these
figures are deliberately absent from every public document.

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
   Residual caveat: the superseding advice letter was never located; the evidence is SDG&E's
   customer-facing publications, now corroborated by **two independent CCAs** whose own dated
   sheets change on the same date.
2. **TOU-DR-P is deliberately unloadable.** Period windows unsourced, and the **RYU Event Adder
   ($1.16/kWh, 4–9 p.m. on event days)** is event-contingent with no engine concept. **Do not
   default it to zero events.** Preferred: caller-supplied event days, report as a range, or
   exclude and say why.
3. **SDG&E baseline allowances — RESOLVED.** Full climate-zone table (Sheet 29294-E) in every
   TOU-DR1 vintage; `territory` supplied at bill time, and omitting it raises.
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
  highest-leverage input in the project; everything SDG&E-facing sits behind it.
- **M3 DoD** — one real household with solar/export interval data.
- **Validation of `src/greenbutton/sdge.py`** against a real SDG&E export.
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

- SDG&E ACC Plus unconfirmed; settle with `acc_plus_eligible=False`.
- PG&E ACC tables not imported (PDFs, not MIDAS CSVs).
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
