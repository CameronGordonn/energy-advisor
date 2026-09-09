# HANDOFF — read this first, with SESSION_NOTES.md

_Rewrite this whole file whenever you finish a milestone or pause. Keep it short and
current: state, how to run, open decisions, exact next action._

## Status: **M0, M2, M4 done. Public site is a working tool. M1 and M3 have complete engines, DoDs blocked on data.**
_(2026-09-08, session 12)_

> **Sessions 8-10.** **418 tests green** (was 166 at session 7), ruff clean, **11/11 PG&E
> golden bills reconcile with byte-identical residuals** (worst +$0.22), M2 verdict unchanged.
> Full detail in SESSION_NOTES §§ Session 8, 8b, 8c, 8d, 9, 10, 11, 12.
>
> - **The repo and site are live and public.** https://github.com/CameronGordonn/energy-advisor
>   (AGPL-3.0) and https://camerongordonn.github.io/energy-advisor/ — see Publishing below.
> - **The site is an interactive TOOL, not a writeup.** Drop a Green Button CSV, get load-shape
>   analysis in plain English. It runs the real Python parsers under Pyodide/WebAssembly, so
>   nothing is uploaded and there is one tested implementation. The M4 writeup moved to
>   `/methodology.html`. **The tool prices nothing, deliberately** — see below.
> - **SDG&E TOU-DR1 has four 2026 vintages, both layers** (1/1, 4/1, 5/1, 6/1). Every cell
>   reconstructs SDG&E's printed Total Electric Rate and Total Adjusted CARE Rate exactly.
>   Rates changed 1/1, 4/1 and 6/1, but the weekday 10:00-14:00 super-off-peak window went
>   year-round **2026-05-01**, inside the 4/1 rate vintage, and SDG&E published **no 5/1
>   table** (that URL 404s) — so the 4/1 rates are committed twice, with the March/April
>   window (governs April) and the year-round one (governs May). **Do not "simplify" this
>   away**; the rationale and dollar impact are in `sdge_tou_dr1_delivery_2026-05-01.yaml`.
> - **⭐ Delivery and generation change on DIFFERENT dates.** EECC moved 4/1 then held; the
>   6/1 filing moved delivery only (UDC 0.34061 -> 0.32948). A tool treating "the rate changed
>   on 6/1" as one event misprices a layer on every bill spanning it. Pinned by test.
> - **CCA overlay opened (session 9).** Clean Energy Alliance generation authored; the PCIA is
>   now **vintaged** and supplied at bill time. `load_specs` now requires a **`provider`**
>   whenever more than one supplier offers a schedule/layer. **⭐ CEA is not uniformly cheaper
>   than SDG&E — it is seasonally OPPOSITE** (+59% summer on-peak, -56% winter off-peak), so
>   which supplier wins is a function of the household's seasonal shape and PCIA vintage.
> - **CCA overlay COMPLETE (session 10).** San Diego Community Power authored — both
>   jurisdiction cohorts x both 2026 vintages — so **both** San Diego CCAs now exist and dad's
>   bill goes straight to reconciliation whichever he is on. **⭐ The manual download this file
>   asked for was NOT needed: the 403 is only on `curl`** (see "Fetching a 403-guarded PDF"
>   below; session 9 lost the whole item to that assumption). **⭐ SDCP publishes TWO rate
>   sheets by enrolment cohort** (+$0.00559/kWh for National City / unincorporated county),
>   modeled as two providers so the loader cannot guess. **⭐ The PCIA, not the CCA's rates,
>   decides**: SDCP undercuts SDG&E in every period, but a 2018-vintage exit fee flips exactly
>   summer super-off-peak — the battery-charging window — and a 2024 vintage flips 5 of 6.

> **⚠ CONTEXT: the Santa Cruz PG&E service ended in July 2026** and the last export in `data/`
> runs to 2026-07-18. The final statement and any post-move interval data are probably
> unreachable. The 11 committed golden bills are unaffected. Cameron has **no plug-in EV**, so
> EV2-A/EV-TOU-5 plans are filtered out of rankings by default.

## What exists now
- **Engine**: N-period first-match-wins TOU rules with weekday/weekend/holiday day types,
  month-conditional windows, cited holiday calendars, `Baseline.allowance_multiplier`,
  `MinimumBill`, per-kWh surcharges, `NonBypassable`, `period_codes`, and
  **`marginal_energy_price`** (version-aware per-interval retail price; refuses dates no spec
  covers; rejects layers that classify an hour differently).
- **Specs (32 files, 16 schedule-layers)**: PG&E E-TOU-C (4 vintages) / E-TOU-D / EV2-A / E-1
  delivery, each with matched 3CE and PG&E-bundled generation; **SDG&E TOU-DR1 delivery +
  generation in four vintages (2026-01-01, -04-01, -05-01, -06-01)**; TOU-DR2, EV-TOU-5,
  TOU-DR-P (deliberately unloadable). Every SDG&E delivery spec carries a `non_bypassable`
  block and is covered by the NBT-settleability test. **CCA overlay: Clean Energy Alliance
  generation (`cea_tou_dr1_generation_2026-06-01.yaml`) and San Diego Community Power
  (`sdcp_{2021v,2022v}_tou_dr1_generation_{2026-01-01,2026-05-01}.yaml` — PowerOn, the default
  product; the two jurisdiction cohorts are separate providers)**, and every SDG&E TOU-DR1 delivery
  vintage carries the **vintaged PCIA** as an `applies_to: cca` adder whose vintage is
  supplied at bill time (`compute_bill(..., vintage="2018")`) and raises if omitted.
  **`load_specs`/`load_spec_versions` now take `provider`** and raise when several suppliers
  match — bundled EECC and a CCA are both "TOU-DR1 generation".
- **M2 optimizer**: `scripts/rate_optimizer.py` — ranking, verdict, component-level *why*,
  sensitivity, assumption audit.
- **M3 NEM 3.0 engine** (`src/nem3/`): `acc.py`, `netting.py`, `solar.py`, `pvwatts.py`,
  `battery.py` (greedy + cvxpy LP, both always returned), `payback.py`;
  `uncertainty/montecarlo.py`. Driver: `scripts/nem3_report.py`, **now calendar 2026**.
- **M4 writeup**: `docs/METHODOLOGY.md` + `docs/methodology.html` (published, see above).
- **Public site, four pages** (`docs/`): `index.html` (the tool), `methodology.html`,
  `privacy.html`, `terms.html`, sharing `site.css` (tokens + chrome) and `fonts.css`
  (`@font-face` only — methodology takes fonts without the chrome, whose `th{width:44%}`
  would wreck its tables). **Fonts are self-hosted in `docs/fonts/`; the site requests
  nothing from Google.**
  **Session 12 redesigned it as the document it is about — a tariff sheet:** two-colour
  print on manila (oxblood + sulphur), **zero border-radius anywhere**, a left rail of
  mono section numbers, ledger rows instead of stat cards, and a `NOT A BILL` stamp.
  Type is Archivo (variable width axis) + Space Mono. `--sul` is a FILL, never text;
  `--ox` means "the expensive hours" and nothing else. Read `.claude/skills/design-system`
  before touching `docs/` — the colour rules and the chart geometry are load-bearing. Overhauled in session 11: landing vs report states, plain language,
  disclosure panels, and accessibility fixed (contrast solved for, chart data tables added,
  heading order repaired). Two committed project skills in `.claude/skills/` describe the
  system and its contracts — read them before touching `docs/`.
  The tool is a Green Button inspector running the
  real parsers in the browser. Engine: `src/report/inspect.py`; CLI: `scripts/inspect_export.py`.
  Sample data `docs/sample-usage.csv` is SYNTHETIC, from `scripts/make_sample_export.py`.

## How to run
```bash
conda activate energy-advisor    # env prefix: /home/cameron/miniforge3/envs/energy-advisor
pytest -q                                                   # 418 tests; golden tests skip if data/ absent
ruff check . && ruff format --check .
PYTHONPATH=src python scripts/reconcile_report.py           # 11 line-item comparisons (the trust artifact)
PYTHONPATH=src python scripts/reconcile_report.py --write-readme
PYTHONPATH=src python scripts/rate_optimizer.py             # M2 ranking + sensitivity + assumption audit
PYTHONPATH=src python scripts/nem3_report.py                # M3 solar+battery (REAL SDG&E rates, synthetic load)
PYTHONPATH=src python scripts/inspect_export.py FILE.csv    # inspect any Green Button export (no pricing)
PYTHONPATH=src python scripts/build_web_engine.py           # regenerate docs/engine.js after touching src/
npm install --prefix tools && node tools/test_engine_wasm.mjs && node tools/test_tool_render.mjs
pip install playwright && python -m playwright install chromium   # optional, not in CI
PYTHONPATH=src python scripts/screenshot_site.py            # LOOK at the pages; jsdom does no layout
PYTHONPATH=src python scripts/build_acc_tables.py --utility 'SDG&E' --vintage 2026 --source FILE.csv --citation '...'
```

## Headline results
**M0/M4 reconciliation** — 11/11 within ±$2, worst **+$0.22** (0.43% of that bill), all
positive, total +$1.55 on $1,084.26 billed. (The one-sided residual is explained in the
writeup: ~0.3 kWh meter-read boundary + the 2025 franchise-fee approximation.)

**M2, PG&E household (4345 kWh / 328 days)** — **SWITCH to E-TOU-C + PG&E bundled generation,
$170.72/yr cheaper.** The saving is **leaving the CCA, not changing schedule**: PCIA
+$159.88/yr, UUT on it +$13.59, franchise fee +$2.54, while 3CE generation is only $4.85/yr
cheaper. Caveat printed in the report: PG&E Rules 22.1/23.1 require six months' notice, with
Schedule TBCC in between. Sensitivity: E-1 overtakes only if evening usage grew 353%, or 132%
load-neutral.

**M3 demo** (bundled SDG&E TOU-DR1, coastal_basic, **synthetic** 6,264 kWh load, 5 kW, now
**calendar 2026**, four rate versions per layer): baseline $3,052/yr; solar only $1,867;
+battery greedy $514; LP $436; NBC import floor $86/yr. **Dollar totals are real, the LOAD is
not — these figures are deliberately absent from the public writeup.**

## Publishing — LIVE

- **Repo:** https://github.com/CameronGordonn/energy-advisor (public, AGPL-3.0)
- **Site:** https://camerongordonn.github.io/energy-advisor/ — **an interactive tool**, not a
  writeup: drop in a Green Button CSV, get load-shape analysis in plain English. The M4
  writeup now lives at **/methodology.html**.
- **How it works:** the page runs the REAL Python parsers under Pyodide/WebAssembly. Nothing
  is uploaded — there is no server. `docs/engine.js` is generated from `src/` by
  `scripts/build_web_engine.py`; `tests/report/test_web_engine.py` fails if it is stale, so
  editing a parser without rebuilding is a red test rather than a stale website.
- **The tool prices nothing, by design.** Load shape needs no reconciliation gate; dollars
  do, and that gate is met for PG&E but not SDG&E. Enforced by tests, not intent.
- **CI:** two jobs, both green on `main`. `test` runs ruff + pytest; `web` runs the browser
  tool's wasm-parity and jsdom render checks (`tools/`, `npm install --prefix tools`).
  Badge in README. Golden-bill tests SKIP in CI by design — they
  need the gitignored real interval export, so the badge proves engine/schema/loader/tariff
  identities, NOT the ±$2 reconciliation. Stated in the workflow header so it cannot overclaim.

`main` is the default branch and holds everything (the old `session-4-nperiod-tou-m2` was
fast-forwarded into it and still exists on the remote as a redundant copy — safe to delete).

**Two GitHub gotchas hit while going live, recorded so the next person does not re-debug them:**
1. `pages.yml` has a `paths: ["docs/**"]` filter, and path filters do **not** reliably match
   when a branch is *created* rather than updated — the first push to `main` did not trigger
   it. `workflow_dispatch` is on the workflow for exactly this; use it after any such push.
2. Enabling Pages auto-creates a **`github-pages` environment with a deployment branch
   policy** pinned to whatever the default branch was at the time. Ours was pinned to
   `session-4-nperiod-tou-m2`, so deploys from `main` failed with "Branch main is not allowed
   to deploy to github-pages due to environment protection rules." Fixed by adding `main`:
   `gh api --method POST repos/<owner>/<repo>/environments/github-pages/deployment-branch-policies -f name=main`

⚠ `docs/index.html` carries a full `<!doctype html>` wrapper for Pages. Republishing it **as
an Artifact** requires stripping doctype/html/head/body first. Pages is the canonical home;
the artifact URL is a preview.

⚠ The `LICENSE`/README copyright line reads "Cameron Gordon" — inferred; correct if wrong.

## Fetching a 403-guarded PDF (learned the hard way, session 10)

sdcommunitypower.org returns **HTTP 403 to `curl`**, even with a browser user-agent. Session 9
concluded from that the rate sheet was unreachable and deferred the whole SDCP overlay to a
manual download by Cameron. **It was reachable the whole time.** The agent's own `WebFetch`
gets through, and although it cannot parse a PDF it **saves the raw bytes to disk anyway** and
prints the path in its result. So:

```
WebFetch <pdf-url> (any prompt)  ->  copy the saved path out of the result
  ->  /home/cameron/miniforge3/envs/energy-advisor/bin/pdftotext -layout <path> out.txt
  ->  transcribe from out.txt   # the session-8 method, just a different way to get the bytes
```

**Generalise: "curl got 403" is not "the document is unavailable."** Try the other fetcher
before asking a human, and before recording something as blocked. Also worth remembering: the
rates were additionally on the site as **HTML**, on two cohort pages the landing page links but
does not name (`/residential-rates/2021v/` and `/2022v/`) — they matched the PDFs cell for cell.

## EXACT NEXT ACTION

0. **Dad's SDG&E Green Button export + bills — NOT ARRIVED as of 2026-09-08.** Checked at
   the start of session 9: `data/` is unchanged since July and there is nothing SDG&E-shaped
   on disk. Re-check first thing; if it has landed, it outranks
   everything below. It is the ONLY input that closes M1's DoD, and M1 is the gate on every
   SDG&E dollar figure reaching another human (see the M5 warning). Expect the first real
   SDG&E file to surprise the parser — `src/greenbutton/sdge.py` has never been run on one,
   and PG&E's real export turned out to be hourly not 15-minute, with an inclusive end
   timestamp and two DST edge cases. Budget a session for parser reality-checking BEFORE
   trusting any reconciliation number. What is needed: the full 13-month export, at least
   three bill PDFs **with the itemized line-item pages**, and from those the schedule,
   climate zone, CARE status, and whether generation is SDG&E bundled or a CCA — and if a CCA,
   which one, which SDCP cohort, and the PCIA vintage. **Both San Diego CCAs are now authored
   (session 10), so no overlay work stands between his bill and a reconciliation run.**
   **First command to run on it:** `PYTHONPATH=src python scripts/inspect_export.py FILE.csv`
   — it auto-detects the utility, and reports interval length, coverage, gaps, DST handling
   and any export register before anything tries to price it. If it refuses the file, that is
   the SDG&E parser meeting reality for the first time; fix the parser, do not fix the file.
1. ~~San Diego Community Power overlay~~ — **DONE, session 10.** No manual download was
   needed; see "Fetching a 403-guarded PDF" below. Both cohorts, both 2026 vintages, PowerOn.
   The CCA overlay is now complete for San Diego: CEA + SDCP.
2. **Confirm SDG&E ACC Plus** from an SDG&E NBT sheet. `acc.acc_plus_table` raises for SDG&E;
   `acc_plus_eligible=False` is the conservative path.
3. **Other SDG&E schedules' earlier 2026 vintages** — TOU-DR2 and EV-TOU-5 still exist only at
   6/1/2026. Same method as session 8 (fetch `N-1-26 Schedule <ID> Total Rates Table.pdf` and
   its `-CARE` twin, `pdftotext -layout`, mirror the vintage split), only needed if those
   schedules are to be ranked over a calendar year.
4. **PG&E ACC tables** — per-vintage PDFs (pge.com/energyexportcredit), not MIDAS CSVs; needs
   a different parser. Low priority.
5. **TOU-DR-P** — needs an events model before it can be ranked (open decision 2).

**M5 is the next milestone** (5 strangers send Green Button CSVs, receive a report, written
go/no-go on charging). It needs no new engine work.

> **⚠ READ THIS BEFORE STARTING M5 — the two milestones are coupled.** M5 targets San Diego
> (SDG&E) users, and **the engine has never been validated against a single real SDG&E bill or
> a real SDG&E Green Button export.** `src/greenbutton/sdge.py` was written to the documented
> format and never run on a real file; no SDG&E golden bill exists. The rate specs are now
> tariff-exact across four 2026 vintages, which is necessary but **not** sufficient: sending
> dollar figures to five strangers without a reconciled SDG&E bill would violate invariant 1
> (reconciliation-gated), which is the product's whole trust claim.
> **The consequence is a sequencing rule, and it is good news:** the FIRST recruit who supplies
> an SDG&E export *plus* three bills closes **M1's DoD**, and only then does the SDG&E path
> earn the right to produce dollar figures for the other four. So recruit for data before
> recruiting for sales, and tell the first one or two people plainly that they are validating
> the engine, not buying a verdict. A PG&E recruit needs no such caveat — that path is already
> reconciled 11/11.

## Open decisions
1. **SDG&E TOU-DR1 super-off-peak window — RESOLVED, and now modeled per-vintage.**
   Year-round effective 2026-05-01; vintages before that date carry `months: [3, 4]` on the
   weekday 10:00-14:00 rule, and both forms are pinned by `tests/tariffs/test_sdge_vintages.py`.
   Residual caveat unchanged: the superseding advice letter / revised P.U.C. sheet were not
   located; the evidence is SDG&E's customer-facing publications.
2. **TOU-DR-P is deliberately unloadable.** Period windows unsourced, and the **RYU Event
   Adder ($1.16/kWh, 4-9 p.m. on event days)** is event-contingent with no engine concept. Do
   **not** default it to zero events. Preferred: caller-supplied event days, report as a
   range, or exclude and say why.
3. **SDG&E baseline allowances — RESOLVED.** Full climate-zone table (Sheet 29294-E) in every
   TOU-DR1 vintage; `territory` supplied **at bill time**. Omitting it raises rather than
   defaulting.
4. **CARE rates on PG&E counterfactual schedules are DERIVED, not printed**
   (`care = 0.65 x standard - 0.01038`). Validated to ≤1e-5 on E-TOU-C, cross-checked against
   E-1's printed tier pair, corroborated by SDG&E's printed "CARE Discount 35%". `--no-care`
   is the tariff-only ranking. (On SDG&E the split is not merely consistent but exact, now on
   **all four** vintages.)
5. **Santa Cruz UUT Adjustment — RESOLVED as a modeling assumption**, mechanism still
   UNVERIFIED. Adopted **$0.21649/day**. Schedule-independent, so it cannot reorder the
   ranking; the optimizer re-ranks under all three mechanisms to prove it.
6. **Which CCA and which SDG&E schedule dad is on** — still unresolvable without a bill, but
   **no longer blocking**: both San Diego CCAs are authored, so whichever he is on, his bill
   goes straight to reconciliation. What his bill must still tell us: schedule, climate zone,
   CARE status, bundled vs CCA, and — new since session 10 — **which SDCP cohort** if he is on
   SDCP (2021V: San Diego / Chula Vista / Encinitas / Imperial Beach / La Mesa; 2022V:
   National City / unincorporated county), and his **PCIA vintage**, which decides more than
   the choice of CCA does.
7. **Privacy posture — RESOLVED session 7.** Self-attributed case study, CARE disclosed,
   exact dates and amounts kept, personal-tenancy detail scrubbed.
8. **Rate-date vs window-date splitting — RESOLVED session 8.** When a period-definition
   change lands inside a rate vintage, split the vintage and duplicate the rates rather than
   backdating the new window onto a citation-bearing spec. See SESSION_NOTES §Session 8.

9. **CARE on a CCA — SHARPENED session 10, and the two sources now CONFLICT. Still open.**
   Settled: what the CCA charges. Both CEA's mapping table and SDCP's Rate Key ("will not
   impact service, billing, or CARE/FERA status", base schedule codes only, no CARE column on
   any table) say the CCA bills one generation rate regardless of CARE status, so both specs
   set `care == standard`. That part is read off the sheets.
   **Unsettled, and worth ~$170-210/yr: how SDG&E COMPOSES the discount for a CCA customer.**
   - The engine today discounts SDG&E's own charges only, which implies a CARE CCA customer
     gets a *smaller* absolute discount than a bundled one (by 0.35 x EECC).
   - **SDG&E's own SDCP Joint Rate Comparison (1/1/2026) implies otherwise**: `(CCA total -
     SDG&E total) $/kWh` is **invariant to CARE/FERA status** across DR, TOU-DR, TOU-DR1,
     TOU-DR2 and all three SDCP products (<=2e-5 in 11 of 12 rows). That can only hold if the
     discount is computed on the bundled-equivalent bill, with the CCA swap and PCIA added
     undiscounted on top.
   - **Against it: 11 real PG&E bills** for a CCA (3CE) + CARE household reconcile within
     +$0.22 with the discount on the delivery layer only. A reconciled bill outranks a
     comparison document — and the JRC's per-line allocation is provably presentational (its
     SDG&E *generation* line is identical across CARE and non-CARE, which the tariff denies),
     so only its totals carry information. The class-invariance is a totals-level fact, so it
     survives that caveat; PG&E and SDG&E may simply compose it differently.
   **The engine was deliberately NOT changed.** Resolve against a real SDG&E CCA CARE bill.
   (Dad may well be the test case — if he is CARE *and* on a CCA, this is the first thing to
   check on his bill, before anything else about it.) Both spec headers carry both sides.
10. **`PerKwhAdder` has no CARE variant**, so the vintaged PCIA is billed class-independently.
   That matches what SDG&E's CARE table prints (it restates the same PCIA table with no CARE
   adjustment), so it is not currently wrong — but it is unmodelable if a future sheet
   differentiates.

## Blocked on data (not on work)
- **M1 DoD** (dad's last 3 SDG&E bills within ±$2) and the README SDG&E rows. As of
  2026-09-08 the data is **expected but not yet supplied** — Cameron was collecting it. This
  is the single highest-leverage input in the project; everything SDG&E-facing is behind it.
- **M3 DoD** needs one real household with solar/export interval data. Same situation.
- Validation of `src/greenbutton/sdge.py` against a real SDG&E export.
- **M2's PG&E cross-check** is unavailable, not pending: PG&E's Rate Plan Comparison returns
  "no service agreement eligible for rate enrollment" for this account. `--pge-comparison
  FILE` is built and waiting.

## Flagged approximations still open (all sub-$0.05, non-blocking)
- **2025 franchise fee**: 2026 specs use the exact E-FFS per-kWh rate ($0.00059); the
  2025-vintage specs still carry the percent-of-energy approximation. (One of the two
  documented causes of the one-sided residual.)
- **2025 summer generation credit** still bill-fitted (the 2026 one is tariff-exact).
- **California Climate Credit** modeled as an observed per-bill line (−$58.23 on 10/28). PG&E
  files $(36.18), Aug/Sep cycles; SDG&E files $(33.50) semi-annual per Schedule GHG-ARR.
  Generalise to a versioned semiannual credit.
- **California Energy Commission surcharge on SDG&E**: PG&E specs carry $0.0003/kWh; SDG&E's
  Total Rates Tables show no such column on any of the four 2026 vintages, so it is
  deliberately NOT asserted either way.
- **SDG&E minimum bill** ($0.329/day, CARE $0.164) comes from the 2018 sheet; none of the
  2026 Total Rates Tables restate it. Confirm before shipping a figure that depends on the
  floor binding.

## M3 open items (recorded, none blocking)
- SDG&E ACC Plus unconfirmed; settle with `acc_plus_eligible=False`.
- PG&E ACC tables not imported (PDFs, not MIDAS CSVs).
- **LP dispatch is a marginal-price optimum, not a settled-dollar optimum** — under NBT caps
  it can settle below greedy. Documented and reported honestly, not a bug.
- **CCA export terms** — netting excludes the CCA generation credit by default (Schedule NBT
  SC 2.a), so a CCA customer's result is a lower bound until supplied.

## Schema gaps (recorded, none blocking today)
- `PerKwhAdder` has no CARE variant (worked around on SDG&E by folding WF-NBC/DWR-BC into the
  energy `Rate`).
- **FERA / DRAH** (0.39688/day on both IOUs, printed on every SDG&E 2026 sheet) unmodelable —
  `Rate` has only `standard`/`care`.
- No `tiers` concept. Correct for E-1 today (exact identity via the baseline credit); required
  if a third distinct tier price appears.

Do **not** build CLI/API/Docker/deployment/web UI — roadmap "Later", gated behind M5.
