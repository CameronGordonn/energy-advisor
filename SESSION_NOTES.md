# Session notes

Running log of decisions made and decisions pending. Newest first.

## 2026-09-09 — Session 20 (methodology.html onto the shared chrome)

HANDOFF action 2. `docs/methodology.html` now links `docs/site.css` and carries **no palette
tokens of its own**; all four published pages are on one stylesheet. Render test green, wasm
test green, ruff clean, 1498 tests green.

> ⚠ Sessions 18, 19 and 20 all ran in the same working tree at once. The test count moved
> under me mid-session (719 → 860 → 1498) and another session edited `docs/methodology.html`
> after I had rewritten it. Nothing was lost, but **do not run parallel sessions in one
> checkout** — use worktrees.

### The stated blocker did not exist; the real ones were different
HANDOFF warned that `site.css` sets `th{width:44%}`, which would wreck methodology's tables,
and that this was why the page linked `fonts.css` only. **That rule is gone** — it is now
`.ledger th{width:auto}`, class-scoped, so it never reaches a methodology table. The genuine
conflicts were:

1. **A `.masthead` class-name collision.** In `site.css` `.masthead` is the sticky nav bar; in
   methodology it was the article title block. Fixed by dropping the page's own header entirely
   and using the shared `.row.heavy` + `.rail` hero, as `index.html` does.
2. **A fourth colour with no token behind it.** The page carried `--warn` (#7A5410 / #D9A63F)
   for caveat flags and the "current plan" row. The shared palette is deliberately two-colour —
   ink plus oxblood, sulphur as a fill — so `--warn` was **deleted**, not aliased. Caveat flags
   now take a 2px `--ink` rule with an `--ink-2` tag; the current-plan row takes a `--paper`
   tint against the plate's `--paper-2`. Both already state their status in words, so no
   meaning was carried by the hue alone.
3. **Parallel devices for the same job.** `.block`/`.block-hd` → shared `.plate`/`.plate-head`;
   the pull-quote `.rule-box` → shared `.gate`, which on `index.html` already carries the exact
   same sentence. `h2.sec` moved out of `index.html`'s inline block into `site.css` so both
   pages share one definition.

### Colour decisions, recorded because they are the ones that will get re-litigated
- **The reconciliation chart's bars were all `--ox`.** They are now `--mark`. Oxblood means
  "the expensive hours" in this system, and spending it on eleven plain data bars drains it —
  the design-system skill says exactly this about the month chart. `--mark` on the plate is
  3.02:1 light / 3.01:1 dark, clear of the 3:1 graphics threshold.
- `--ox` is **kept** for links, rail numbers, `h3`, the pass tick and the stamp, which is how
  `site.css` itself already uses it. The "expensive hours and nothing else" rule is scoped to
  chart data colours; read literally site-wide it contradicts the shared stylesheet.
- **No `--sul` text anywhere.** It stays a fill; 1.89:1 on paper.
- Rounded bar ends and the `border-radius:2px`/`3px` on `code` and the tooltip are gone. There
  is no radius on the site.

### Accessibility — audited, with two defects only a real browser could find
Closed from the audit skill's open list:
- **Heading order**: was `h2 → h4` (block titles) and `h2 → h5` (findings). Block titles are
  not sections, so they became `<p>` inside `.plate-head`; findings became `h3`. 27 headings,
  one `h1`, **zero skips**.
- **`<th scope>` and captions**: all four tables now have a `<caption>` (visually hidden — the
  plate header shows the same words) and every `th` carries a scope. Row headers added: the
  billing period, the plan name, the component.
- **The pass tick is no longer a bare glyph** — `✓<span class="vh"> within tolerance</span>`.
- **The tooltip stopped being a live region.** It was `role="status"` and fired on hover, so a
  screen reader announced eleven statements on mouse-over. It is `aria-hidden` now; the table
  below is the text equivalent, and the chart's `aria-labelledby` points at its visible caption
  so the description cannot drift from the words beside it.

**Reflow (WCAG 1.4.10) — two real failures, both invisible to jsdom:**
1. At 200% and 400% the whole **page** scrolled sideways instead of the block. A grid item's
   `min-width` is `auto` = min-content, so one `<pre>` or wide table dragged the column past the
   viewport and `overflow-x:auto` on `.scroll`/`<pre>` never got to contain anything.
   `.row>*{min-width:0}` in `site.css` fixes it for both pages.
2. Then a **1px visually-hidden caption** still made the page 498px wide at 320px. `.vh` is
   `position:absolute`, so with no positioned ancestor its containing block was the page and it
   escaped `.scroll`'s clipping at x=512. `.scroll{position:relative}`.
3. `index.html` was **also** failing 1.4.10 at 400% — the hero `h1`'s clamp floor (2.6rem) made
   "ELECTRICITY" 349px wide in a 285px column. Floor lowered to 1.95rem. Pre-existing, not
   caused by this migration, fixed because it was measured.

All three widths (1280 / 640 / 320) now report `scrollWidth == clientWidth` on both pages.

### Two stale numbers on the live site, corrected
`index.html` claimed **418 tests** and methodology **719**. A clean run is **1,498**. Both
updated. `index.html`'s figure had drifted by 3.5× and nothing checks it — worth a test.

### Prose correction forced by a concurrent session
§2 said TOU-DR-P does not load because "its period windows are unsourced". Session 18 sourced
them the same day; the spec still deliberately does not load, but now for the schema reason
(no concept of an event-contingent charge). The sentence now leads with the RYU event adder,
which is true under both states of the spec.

---

## 2026-09-09 — Session 19 (PG&E ACC export tables, and the vintage asymmetry)

HANDOFF action "PG&E ACC tables". **Full suite green** (1498 at the time this ran; session 18
was landing tests in the same tree concurrently), ruff clean. Five new tables + one new test
file; the only source change is two constants in `scripts/build_acc_tables.py`.

### ⭐ FINDING — the premise of the task was wrong, and that saved the work
HANDOFF said "PG&E publishes per-vintage PDFs at pge.com/energyexportcredit, so this needs a
different parser rather than a new argument to the existing one. Build it alongside
`scripts/build_acc_tables.py` rather than inside it." **PG&E publishes MIDAS CSVs too.** The
PDF page footnotes them: "For a complete list of EEC values, please visit pge.com/eecvalues",
which redirects to a single 36 MB zip holding **all five vintages** as MIDAS uploads —
2023, 2024, 2025, 2026 and Floating.

So there is no second parser. The existing one needed exactly two changes:

- `RIN_COMPONENT` gains `USCA-PGXX` (delivery) / `USCA-XXPG` (generation).
- The unit check is case-insensitive: SDG&E writes `export $/kWh`, PG&E `Export $/kWh`. The
  unit is still *checked* — a file in $/MWh would misprice every export by 1000x.

That is the whole diff. **Generalising the lesson from the session-9 field note ("curl got 403"
is not "the document is unavailable"): "the utility publishes a PDF" is not "the utility
publishes only a PDF."** Follow the PDF's own footnotes before writing a PDF parser.

The PDFs are not wasted — they became the *cross-check*, which is stronger than either source
alone. See below.

### ⭐ FINDING — PG&E's vintages differ; SDG&E's do not; and the difference inverts the pitch
This was the open question the task named, and it has a clear answer with a twist.

Five published PG&E files collapse to **two** distinct schedules: **NBT23 ≡ NBT24** and
**NBT25 ≡ NBT26 ≡ NBT00**, cell-for-cell on every overlapping year. The clusters are far apart
(>$1/kWh in the extreme cells), so unlike SDG&E — where all three tables are one table wearing
three labels — the vintage is a real fork in PG&E territory. **That asymmetry is real and it is
the first territory-specific vintage finding in the repo.**

But the direction is not the installers' one. The gap is **structural by hour of day**:

| weekday band | who leads | size |
|---|---|---|
| midday 09–15 (where a solar-only array exports) | **older** NBT23/24, every year | $0.005–0.020/kWh |
| overnight 00–06 (battery only) | **newer** NBT25/26, every year | up to **+$0.14/kWh** by 2033 |
| evening 17–21 | older through 2029, newer from 2030 | flips mid-lock-in |

Read together: for a **solar-only** customer the PG&E vintage is nearly immaterial, same
practical answer as SDG&E. For a customer who can **shift the export hour with a battery**, the
vintage matters a lot and the **newer** one wins — the reverse of "get in before the rates
drop". And since NBT26 ≡ NBT00, locking in the 2026 vintage buys precisely the floating table:
its value today is not a gain but **insurance against the floating table moving at the next ACC
adoption**. That is a defensible thing to want, and a different claim from the one being sold.

**Do not compress this to "later is better".** It is band-dependent, and the evening band flips
in 2030. The parametrised tests hold each band separately for exactly that reason.

### ⭐ The cross-check found a real, bounded disagreement between PG&E's own two publications
Every printed price sheet turns out to show **calendar-2026** values for its own application
vintage, so all four are directly comparable to the imported tables. Result: **571–574 of 576
cells agree to 1e-5**, and every disagreement is a **weekend cell in March or November** — the
two DST-transition months, both transitions falling on a Sunday. The 23-hour and 25-hour days
evidently get averaged into the monthly weekend figure slightly differently by the two
pipelines.

Decision, recorded rather than silently taken: **the import follows the MIDAS CSV**, because it
is the machine-readable file PG&E uploads and the only one carrying the 20-year horizon at all.
Worth ≤$0.0005/kWh on two hours of ~9 weekend days, so it moves no recommendation. It is pinned
**in both directions** — each listed cell must still disagree, and only slightly — so that
nobody later "fixes" the importer to chase the printed number, and so a future import that
disagrees somewhere *else* fails loudly.

### Also pinned
- **The printed "Highest value for credits" band is the WEEKDAY maximum only.** In the 2025/2026
  sheets the weekend table reaches $1.04281/kWh, above the printed $0.99821 ceiling. A reader
  taking the band as a whole-sheet range is wrong. Used here as a whole-table check on 288 of
  the 576 cells rather than as a spot value.
- **"Energy Produced" is the generation component, "Energy Delivered" the delivery one** — and
  PG&E's own footnote 2 restricts Produced to bundled-generation customers, independently
  corroborating Schedule NBT SC 2.a (a CCA customer's generation credit is not PG&E's to give).
  Pinned separately, because a swapped mapping still "matches a printed number".
  Note the ordering is **not** universal: in the 2023 sheet's July 5 p.m. cell delivery is the
  larger of the two, so the check names a cell rather than asserting a rule.
- **SDG&E's three-way table identity is now asserted directly**
  (`test_sdge_vintages_are_one_table_wearing_three_labels`). It was stated in HANDOFF and
  leaned on by `test_payback.py`, but never checked — and it is exactly the kind of fact that
  quietly stops being true at the next ACC adoption.
- The zip readme **mislabels both NBT23 and NBT24** as "applications filed in 2025". The
  `RateName` column and the printed sheet titles both say otherwise; the citations record the
  discrepancy so the labels do not read as ours.

### ⚠ THE SHARED-INDEX HAZARD RECURRED — and this time it crossed sessions
Session 17 recorded the lesson: parallel sessions share the git **index**, so a path-scoped
`git add` followed by `git commit` is not isolated. It happened again here, in the direction
that is harder to notice. Session 18's commit `d0045a8` ("SDG&E 8/1/2026") **swept up this
session's in-flight HANDOFF.md edit** — the PG&E vintage-asymmetry block under "tariff facts
that cost real money" is committed under a message about SDG&E rate vintages, and that
commit's "measured in a clean HEAD checkout with only these files applied" does not describe
what it actually contains.

Nothing is lost and no history was rewritten (session 18 may still have been working; rewriting
shared history under a live tree is worse than the misattribution). Recorded so a future
`git log -S` for the PG&E finding does not come up confused.

**The fix remains `git worktree add` per writing lane.** Two sessions have now paid for not
doing it. The mitigation that did work: `git add <explicit paths> && git commit -- <the same
explicit paths>` in a single shell invocation — the pathspec form of `git commit` ignores
whatever else is staged, so this session's own commit came out clean at 13 files.

### Recorded, not acted on
- **Neither utility has a 2027 table**, and 2027 is the last application year that earns a
  lock-in at all — so it is the last vintage the "when to install" question can ever turn on.
  `Vintage(application_year=2027, ...)` raises `MissingAccTableError`, which is correct.
- **PG&E's floating NBT00 has not been refreshed since 2024-12-18** (the zip's member file
  dates). Worth re-checking, since the whole value of a lock-in is what the floating table does
  next.

## 2026-09-09 — Session 18 (the 8/1/2026 SDG&E vintage, all three schedules in one pass)

**860 tests green (was 719), ruff clean, golden bills untouched.** HANDOFF action 2. Six new
spec files, no existing spec edited. Every SDG&E spec previously stopped at 6/1, so August
through December — five months of any calendar-year run — were priced with June rates on
TOU-DR1, TOU-DR2 and EV-TOU-5 alike. All three are done together, per session 16's rule that
a partial fix is worse than a consistent lag.

### DONE — the vintage, from the primary sheets
`curl` reaches sdge.com fine (the 403 field note is specific to sdcommunitypower.org), so all
six Total Rates Tables — three schedules x standard/CARE — came straight from
`sdge.com/sites/default/files/regulatory/`, `pdftotext -layout`, delivery and generation
transcribed as separate layers. **All 32 layer-sum cells reconcile to SDG&E's printed Total
Electric Rate and Total Adjusted CARE Rate**, worst residual 6e-6 and that only from the
sheet's own 5-dp rounding. The CARE split derived on TOU-DR1 back in session 6 — delivery
keeps the 0.00864 exemption, both layers take the 35% — still rebuilds the printed CARE total
on a fifth vintage it was never fitted to.

**8/1 is the LAST 2026 vintage.** 7-1-26, 9-1-26, 10-1-26 and 11-1-26 all 404 in the same
series as of today, and sdge.com's live plan pages quote "prices effective August 1, 2026".
So calendar 2026 is now covered end to end with no stale tail.

### ⭐ FINDING — one filing, and the two layers moved in OPPOSITE directions
The 6/1 filing moved delivery only. The 8/1 filing moved both, and not the same way:

| | 6/1 | 8/1 |
|---|---|---|
| TOU-DR1 UDC Total | 0.32948 | **0.32601** (down) |
| TOU-DR1 summer on-peak EECC | 0.34920 | **0.35943** (up) |
| all-in summer on-peak | 0.68459 | **0.69135** (up) |

So "SDG&E delivery rates went down in August" is true, and for a summer on-peak kWh entirely
misleading — the all-in rate rose. A tool carrying one blended 2026 SDG&E rate gets the
magnitude wrong on both halves and **the sign wrong on delivery**. This is the sharpest
instance yet of the ⭐ fact already in HANDOFF, and it is now pinned by
`test_the_august_filing_moved_both_layers_in_opposite_directions`.

### ⭐ FINDING — the PCIA moved too, and only a CCA customer would ever feel it
Every residential PCIA vintage fell ~0.00216/kWh (2018: 0.03670 → **0.03454**; 2026: 0.04987
→ **0.04771**), identically on all three schedules' sheets. That is ~$13/yr on a 6,000 kWh
CCA household, and it lands on **nothing a bundled test would catch** — the layer-sum gate
never touches the adder. Pinned separately by `test_the_august_filing_moved_the_pcia_too`.
The baseline credit also grew, (0.10663) → **(0.10702)**, likewise pinned.

### ⭐ FINDING — EV-TOU-5's super-off-peak delivery rate did not move at all
Its on/off-peak UDC fell 0.31711 → 0.31218 while super-off-peak UDC held at **0.04114** for a
third consecutive vintage. So the delivery discount in the battery-charging window did not
deepen; only the windows it is measured against got cheaper. The NBC share of that window's
delivery charge therefore holds at ~45% while rising 6.5% → 6.6% elsewhere — the ~2x
overstatement trap for anyone netting exports against a headline rate is unchanged in size.

### CHECKED, NOT ASSUMED — the windows did not move
`sdge.com/super-off-peak-residential`, retrieved today, still prints "Weekdays: 12 a.m. to
6 a.m. / 10 a.m. to 2 p.m. Weekends: 12 a.m. to 2 p.m." and "now ... all year long". So no
5/1-style rate/window split is needed for this vintage (open decision 8) and the 8/1 specs
inherit the 6/1 rules verbatim. TOU-DR2 still has no super-off-peak period at all.

### THE POINT OF THE EXERCISE — did anything reorder?
**No, and one of the two answers is structural rather than empirical.**

- **`scripts/rate_optimizer.py` is unchanged, byte for byte.** Verdict still SWITCH to
  E-TOU-C + PG&E, $933.50/yr vs $1,104.22 current, −$170.72. That is not a coincidence the
  8/1 rates survived: **the optimizer prices the PG&E household on PG&E schedules only**, so
  no SDG&E spec can reach it. There is still no SDG&E household to rank — the binding
  constraint, unchanged.
- **`scripts/nem3_report.py` (real SDG&E rates, synthetic load) moves ~0.1% and reorders
  nothing.** Baseline $3,052 → **$3,056**/yr; solar only $1,867 → **$1,870**; +battery greedy
  $514 → **$512**, LP $436 → **$433**. Savings, paybacks (8.9 / 7.4 / 7.2 yr), the P10/P50/P90
  bands and the NBC floor ($86/yr) are all unchanged. The baseline rose *despite* delivery
  falling, because this load is summer- and peak-weighted and generation rose more — the
  opposite-directions finding showing up in dollars.

**So the fix was worth making for correctness, not for its effect on any current answer.**
Five months of the year were priced wrong; they now are not. Nothing downstream changes,
which is exactly what one wants to be able to *say* rather than assume.

### Test counts
719 → 860. The growth is parametrization, not new assertions of new kinds: a fifth vintage
multiplies through the existing per-cell layer-identity and window tables. Five hand-written
tests are genuinely new (opposite-direction layers, PCIA move, baseline-credit move,
EV-TOU-5 frozen super-off-peak, generation moved on every schedule). Stale `719` counts in
README.md, docs/METHODOLOGY.md and the published docs/methodology.html updated in the same
commit — the drift session 17 had to clean up twice.

### Incidental correction
The TOU-DR1 printed-total table in `test_sdge_vintages.py` gained its 6/1 row, which had
never been there (6/1 was covered only by `test_sdge_layers.py`). Four of its CARE cells were
first written from the layer sums rather than the sheet and were wrong in the 5th decimal;
the 6/1 CARE table was fetched and they now come off the sheet. Worth recording because it
is the exact failure mode the printed-total gate exists to catch, and it caught it.

### ⚠ COORDINATION — another session is writing this same tree, right now
`git status` at commit time showed in-flight work that is not mine: PG&E ACC tables
(`src/nem3/acc_tables/pge_nbt*.{csv.gz,yaml}`, `tests/nem3/test_acc_pge.py`), a TOU-DR-P test,
and a **full rewrite of `docs/methodology.html`** onto the shared chrome. Per session 17's
lesson I committed with an explicit pathspec (`git commit -- <my files>`), so the shared index
could not fold their work into my commit.

Two consequences for whoever reads this next:
- **My 719 → 860 edit inside `docs/methodology.html` is NOT in my commit** — that file belongs
  to the other lane and I only sed'd the one number. If their rewrite lands without it, the
  published page will claim 719 again. README.md and docs/METHODOLOGY.md *are* in my commit.
- **The HANDOFF action list was renumbered by me** (old action 2, the 8/1 vintage, is done and
  gone; 3-5 became 2-4). The other lane is working what is now action 2 and action 3. Expect
  to renumber again, and reconcile rather than re-derive.
- The **860** figure was measured in a clean `git archive HEAD` checkout with only my six
  specs and my test file applied, precisely so it is not inflated by the other lane's tests.

## 2026-09-09 — Session 17 (reconciling four parallel sessions' docs)

Housekeeping, no engine change. **719 tests green, ruff clean, wasm parity and render checks
pass.** Sessions 13-16 ran **in the same working tree at the same time** and all four patched
HANDOFF.md independently, which reproduced exactly the drift session 12 had just cleaned up:

- **Two contradictory test counts inside one file** — the status header said 719, the "How to
  run" block still said 418.
- **A struck-through DONE action still holding its number** (ACC Plus as `**2.**`), the same
  defect the session-12 rewrite existed to remove. Dropped; the live actions renumbered 1-5.
  The resolution itself was already recorded under M3 open items, so nothing was lost.
- **Three stale `331 tests` claims** in README.md, docs/METHODOLOGY.md and the *published*
  docs/methodology.html.
- A status header still reading "end of session 12", and `main pushed` while `main` was six
  commits ahead of `origin`.
- The M5 warning claimed the engine "has never been validated against a single real SDG&E bill
  **or export**". The export half stopped being true in session 13 — narrowed to the bill
  claim, with the weaker parser claim stated separately so it cannot be read as the strong one.

### LESSON — parallel sessions share the git INDEX, not just the tree
A path-scoped `git add` followed by `git commit` is **not** isolated: another session staging
between the two calls puts its files in your commit. It happened here — a parser commit
captured 25 files across four lanes and had to be reset and redone. `git worktree add` per
writing lane is the fix; a read-only lane can share.

### The corollary that actually matters
Four lanes ran and **none of them moved M1**, because M1 is blocked on data, not code. Sessions
14-16 were correct, well-cited work; they were also all polish. Session 16's 8/1/2026 finding
is the exception worth acting on, and it is worth acting on because it makes existing numbers
*wrong*, not because it adds capability. Re-read THE BINDING CONSTRAINT before opening another
parallel fan-out.

## 2026-09-08 — Session 16 (TOU-DR2 and EV-TOU-5: earlier 2026 vintages, and two half-built schedules finished)

**719 tests green, ruff clean, golden bills untouched.** HANDOFF action 3. Twelve new spec
files; no existing spec edited (session 15 was cross-checking them read-only — see the
coordination note at the end). Ran concurrently with session 15, which independently
cross-checked these files mid-flight and found zero errors.

### DONE — the vintages, from the primary sheets
`curl` reaches sdge.com fine (no 403 — the field note's 403 is specific to
sdcommunitypower.org), so all twelve Total Rates Tables came straight from
`sdge.com/sites/default/files/regulatory/`, `pdftotext -layout`, delivery and generation
transcribed as separate layers. **All 40 layer-sum cells reconcile to SDG&E's printed Total
Electric Rate and Total Adjusted CARE Rate, worst error 7.5e-6.** The CARE split derived on
TOU-DR1 (delivery keeps the 0.00864 exemption, both layers take the 35%) rebuilds the printed
CARE total on two schedules it was never fitted to — including EV-TOU-5's collapsed
super-off-peak row, where the exemption is a quarter of the whole delivery charge.

Independently corroborated: every Total Electric Rate matches `corruptbear/my_sdge`'s
hand-transcribed YAMLs at 1/1 and 4/1, on both schedules. Their files were consulted, not
vendored (no LICENSE); sdge.com is cited as the source.

### ⭐ FINDING — TOU-DR2 and EV-TOU-5 were HALF-AUTHORED, and nothing failed
Both shipped in session 6 with a **delivery spec and no generation layer**, so a bundled
customer could not be priced on either — only half their bill existed. The EV-TOU-5 spec even
recorded its six EECC values in a comment "for reference". This was invisible because every
test named its spec files explicitly, so no test ever asked for the missing half. Both pairs
are now complete (including the 6/1 generation layers, which were also missing), and the gap
is closed structurally rather than by memory:

- `test_every_sdge_delivery_vintage_has_a_matching_generation_vintage` globs the specs dir
  and asserts pair completeness. TOU-DR-P is the one documented exclusion.
- `SDGE_DELIVERY` in `test_sdge_layers.py` **was a hand-maintained list of six filenames**
  and is now a glob. A hand-maintained list is a gate that stops gating the moment someone
  adds a spec and forgets a line — it had already silently stopped covering nothing, but it
  would have. The NBT-settleability gate now covers all 11 SDG&E delivery specs
  automatically.

### DECISION — TOU-DR2 gets THREE vintages, not four, and that is a fact about the schedule
TOU-DR1 and EV-TOU-5 each carry a 2026-05-01 vintage because the weekday 10:00-14:00
super-off-peak window went year-round mid-rate-vintage (open decision 8). **TOU-DR2 has no
super-off-peak period at all** — two periods, every day, no weekend table — so that filing
cannot touch it. Confirmed three ways: no 2026 TOU-DR2 rate table prints a Super Off-Peak row;
SDG&E's super-off-peak page lists the affected plans and does not name TOU-DR2; SDG&E's
Time-of-Use Plans page prints TOU-DR2 as "Every Day / 12 a.m. - 4 p.m., 9 p.m. - 12 a.m." with
no carve-out. One secondary source (a solar-installer blog) *does* list TOU-DR2 among the
affected schedules and **is wrong**; the rate tables outrank it. Pinned by
`test_tou_dr2_has_no_may_vintage_because_it_has_no_super_off_peak_window`, because "the 5/1
file is missing" and "the 5/1 file must not exist" look identical in a directory listing.

### ⭐ EV-TOU-5's pre-May window: sourced DIRECTLY, not inherited
The riskiest input in this session was whether EV-TOU-5's 10 a.m.-2 p.m. weekday window was
also March/April-only before 5/1, or simply did not exist. Assuming it mirrored TOU-DR1 would
have been a guess. **SDG&E's own EV Pricing Plans page settles it**: the 2025-11-07 capture
(prices effective 2025-11-01 — the table in force when the 1/1 vintage took effect) prints the
Super Off-Peak column as "Midnight - 6:00 a.m. / **10:00 a.m. - 2:00 p.m. in March and April**
(Weekdays) / Midnight - 2:00 p.m. (Weekends & Holidays)". SDG&E's super-off-peak page names
EV-TOU-5 among the plans the year-round change applies to and says the hours "were previously
only available in March and April". The 5-1-26 EV-TOU-5 URL 404s, verified for this schedule
rather than assumed from TOU-DR1.

**On EV-TOU-5 the 5/1 split is worth ~4x what it is worth on TOU-DR1.** Pricing May weekday
10:00-14:00 as off-peak instead of super-off-peak costs 0.47610 - 0.12115 = **0.35495/kWh**
(≈$30/month at 1 kW in that window), against 0.09076/kWh on TOU-DR1. Note that spread is the
**winter** one: May is a winter month under Schedule EECC (winter is Nov 1 - May 31), and the
summer spread never applies to the days that file covers.

### Also pinned
- **TOU-DR2's delivery layer is NOT period-flat.** TOU-DR1's UDC total is flat, which is why
  100% of its TOU signal lives in generation — a fact this repo leans on. TOU-DR2's UDC *is*
  time-differentiated, but only in summer (0.34550 on-peak vs 0.33903 off-peak at 1/1); winter
  is flat. A tool that learned "SDG&E delivery is flat" from TOU-DR1 misprices TOU-DR2 summer.
- **EV-TOU-5 has no baseline credit on any vintage** — deliberately absent, not UNVERIFIED: no
  EV-TOU-5 table prints an "Up to 130% of Baseline" row where every TOU-DR1/DR2 table does.
- The super-off-peak NBC share is starker on the earlier EV-TOU-5 vintages than on 6/1:
  **49%** of the 1/1 super-off-peak delivery charge is non-bypassable (0.02099 / 0.04267),
  against 45% at 6/1 and ~6.4% in the other windows.

### ⚠ FINDING, OUT OF SCOPE, AND IT MATTERS MORE THAN THIS SESSION'S WORK — an 8/1/2026 vintage exists
Chasing the live EV plans page turned up "Prices effective **August 1, 2026**", which did not
match our 6/1 rates. `8-1-26 Schedule TOU-DR1 Total Rates Table.pdf` **exists and is not in
this repo** (nor is EV-TOU-5's; 7-1, 9-1 and 10-1 all 404). It is a real move, not a reprint:
TOU-DR1 UDC Total 0.32948 → **0.32601**, summer on-peak EECC 0.34920 → **0.35943**, baseline
credit (0.10663) → **(0.10702)**.

**Every SDG&E spec in this repo stops at 6/1, so Aug-Dec 2026 is currently priced with stale
rates — TOU-DR1 included.** Deliberately NOT fixed here: the task was earlier vintages, and
adding 8/1 to only the two schedules I touched would make them more current than TOU-DR1 and
produce an apples-to-oranges ranking, which is worse than a consistent lag. It is now HANDOFF
action 3, and it is cheap — same method, four more sheets per schedule.

### ⚠ Also noticed, NOT edited (coordination)
`sdge_tou_dr1_delivery_2026-05-01.yaml`'s header quotes its dollar impact using the **summer**
EECC spread (0.12853 - 0.04121 = 0.08732/kWh) for a change that only ever governs **May**, a
winter month. The winter spread is 0.19304 - 0.10228 = 0.09076/kWh, so the file slightly
*understates* its own case. Comment-only, no rate affected. Left alone because session 15 was
cross-checking `src/tariffs/specs/` read-only and the handoff said to coordinate before
editing an existing spec.

### Not done, and deliberately
There is **no SDG&E candidate set in the optimizer** — `ALL_PGE_CANDIDATES` is the only one, so
nothing ranks SDG&E schedules today regardless of vintage coverage. The specs were the
prerequisite and are now in place; the candidate tuple is the follow-on, and it is gated on a
real SDG&E household anyway (invariant 1 — no SDG&E dollar figure before reconciliation).

## 2026-09-08 — Session 15 (independent cross-check of the SDG&E specs: zero errors found)

Full writeup in `notes/spec_crosscheck_2026-09.md`. **No spec was changed** — the read-only
constraint held because nothing in `src/tariffs/specs/` turned out to be wrong. 436 tests
still green.

### What was checked, and against what
`github.com/corruptbear/my_sdge` (unaffiliated, active since Dec 2022) hand-transcribes SDG&E
residential rates into YAML across 9 vintages. Their model is *totals* (delivery+generation
fused); ours is *layers*. Reconstructing their totals by summing our two layers is therefore
also a check that our layer split is coherent, not just that the digits match.

**115 value-level comparisons, zero mismatches**: 24 TOU-DR1 total $/kWh cells (6
season×period × all four of our 2026 vintages), 54 PCIA vintage rates, 4 baseline adjustment
credits, 4 Base Services Charges, 8 Basic baseline allowances, 15 TOU-DR2 cells+credits, plus
the 6 SDCP 2021V PowerOn cells and the weekday/weekend/holiday hour-sets. Separately, their
**mirrored source PDFs** gave a second copy of the sheets: full UDC component decomposition
verified line-for-line for TOU-DR1 @1/1 and @6/1, TOU-DR2 @6/1, EV-TOU-5 @6/1.

**⚠ Eight untracked spec files were on disk when this ran** — earlier TOU-DR2 and EV-TOU-5
vintages from another session working HANDOFF action 3, including the first TOU-DR2
*generation* specs. Not written here, not modified here, but in scope, so checked:
**they cross-check clean.** TOU-DR2 delivery+generation reconstructs the published total
exactly at 1/1, 4/1 and 6/1; credits match; the two layers carry byte-identical `tou.rules`
at every vintage; and the four EV-TOU-5 delivery vintages correctly mirror the 4-way window
split. Whoever resumes that work can rely on it.

Not vendored — that repo has no LICENSE. Read in scratch, cited by URL.

### ⭐ The 2026-05-01 window question got a real answer, and it is uncomfortable
Three findings pointing three different ways. **The modeling does not change**; the caveat does.

1. **CORROBORATED on substance, by a fourth non-CCA party.** Their code carried
   `is_march_or_april = 1 if (date.month == 3 or date.month == 4) else 0` — literally our
   `months: [3, 4]` — for years, and commit `be51c303` (2026-06-10, *"apply extended
   super-offpeak hours"*) deletes the condition. An unaffiliated engineer independently held
   our old rule and independently abandoned it.
2. **NOT corroborated on the DATE.** Their windows live in code with no effective date, so the
   change applies retroactively to all nine of their vintages — their 2023–2026-04 files now
   misprice March/April months. They cannot distinguish 5/1 from 6/1. Their handling is
   strictly worse than ours and is exactly the failure open decision 8 exists to prevent.
3. **⚠ NEW and against us: the filed tariff sheet still says March and April.**
   `elec_elec-scheds_tou-dr1.pdf` — SDG&E's *current and effective* tariff-book PDF, retrieved
   2026-09-08 — prints "Excluding 10:00 a.m. – 2:00 p.m. in March and April" on Cal. P.U.C.
   Sheets 29952–29955-E, Advice 3167-E, eff. Jan 1 2018. **This is why sessions 8 and 9 never
   found a superseding advice letter: the tariff book was never updated.** It is not proof the
   window did not change — the same PDF still carries 2018 *rates* (EECC 0.29722), so the book
   demonstrably lags the Total Rates Tables — but no *filed* document supports 5/1.

Best single document for the date is still a CCA's: SDCP's `Res_2021V_042026.pdf` — an
*April*-named file whose body says **"Effective May 1, 2026"** five times, whose PowerOn rates
are cell-for-cell our `sdcp_2021v_..._2026-05-01.yaml`, and whose printed TOU table drops the
March/April exclusion that its own February-2025 predecessor still carries.

HANDOFF open decision 1 rewritten accordingly. The per-vintage split is right *because* it
survives being wrong about the date: one file changes.

### Incidental confirmations off the tariff sheets
- Weekend/holiday windows (SOP midnight–2pm, off-peak 2–4pm & 9pm–midnight, on-peak 4–9pm)
  match ours exactly.
- The March/April carve-out is printed **only in the Winter column** — which makes our
  season-free `months: [3, 4]` rule exactly equivalent, since Mar/Apr are winter under EECC.
- **Baseline allowances re-verified**, all 16 cells, off Schedule DR SC 3 (Sheet 29294-E).
- NBC components (PPP 0.01515 / ND 0 / CTC −0.00007 / WF-NBC 0.00591) confirmed on two sheets,
  as is the **absence of any CEC surcharge column** — the flagged approximation is correctly
  left unasserted.
- HANDOFF's "~45% of EV-TOU-5 super-off-peak delivery is non-bypassable" checks out: 44.6%.
- Minimum bill $0.329 / $0.164 CARE appears on the current-and-effective Schedule DR sheet —
  but that sheet is still the 2018 filing, so the flagged approximation **stands as recorded**.
  Marginally stronger, not resolved.

### Three discrepancies found — all three are theirs
1. **Stale CCA sheet.** Their 1/1/2026 file pairs correct SDG&E rates with SDCP generation from
   a sheet reading "Effective February 1, 2025". Implied summer super-off-peak **0.08111** vs
   the **0.01000** we carry — 8× wrong, precisely on the battery-charging window. A layered
   model makes that drift visible; a fused total hides it.
2. **All-electric baseline allowances wrong** (Basic right). Adjudicated against Schedule DR
   SC 3: **our** numbers are the tariff's, on all sixteen cells. Theirs has winter coastal
   all-electric *below* Basic — backwards for a heating-electrified household.
3. **Holiday calendar too broad** — pandas `USFederalHolidayCalendar` (11 days) vs SDG&E
   Electric Rule 1's 8. They price 06:00–10:00 as super-off-peak on MLK Day, Juneteenth and
   Columbus Day. ~$1–3/yr, systematic.

### DR-SES and EV-TOU-2 (question b — assessed, deliberately NOT added)
- **DR-SES is worth adding, and is the more valuable of the two.** Solar-household schedule:
  UDC Total flat **0.26328** (TRAC 0.00000) → delivery 6.6¢/kWh cheaper than TOU-DR1, but a
  much steeper EECC (summer on-peak 0.47019 vs 0.34920) and **no Baseline Adjustment Credit at
  all** where TOU-DR1 credits −0.10663/kWh to 130%. Which wins is a pure function of import
  shape and baseline allowance — unanswerable from a marketing page, and aimed at exactly the
  population M3 serves. Ranking a solar household without it on the menu is a real gap.
- **EV-TOU-2: no.** Cameron has no EV, EV-TOU-5 is already specced and is the current EV
  offering, and EV-TOU-2's enrolment status is unverified — do not assert it.
- **Carry forward: PPP is not schedule-independent.** 0.01515 on TOU-DR1/DR2/EV-TOU-5/DR-SES
  but **0.01713** on EV-TOU and EV-TOU-2, which also carry LGC 0.01235. `non_bypassable` is
  per-spec so this is not a live bug, but copy-pasting the TOU-DR1 NBC block onto an EV-TOU
  spec would silently misstate the NBT import floor.

### What this does NOT establish — stated so the result is not over-read
**Agreement on rate transcription is not reconciliation.** Invariant 1 is still unmet for
SDG&E and M1's DoD is unchanged. Also genuinely unchecked: **CARE** (they do not model it at
all — our derivation remains checked only against SDG&E's own printed CARE tables, and open
decision 9 is untouched); the **EV-TOU-5 generation layer** we do not hold; and all of
NEM 3.0 / ACC / netting, which is outside their scope.

## 2026-09-08 — Session 14 (RESOLVED: SDG&E has no ACC Plus adder, and it is a decided fact)

Closed HANDOFF next action 2. `acc.acc_plus_table` no longer raises for SDG&E; it returns a
cited all-zero table. 436 tests green, ruff clean on the files touched.

### THE ANSWER — $0.000/kWh, every residential segment, by decision
**CPUC D.22-12-056** (R.20-08-020, issued 2022-12-15) sets the adder per utility, not each
utility's own filing, and adopted **zero for SDG&E**:

- **Table 7, "Adopted Initial ACC Plus Adders by Utility ($/kWh)", at 158** —
  Residential Non-CARE / Residential CARE / Commercial: PG&E $0.022 / $0.090 / $0.000;
  SDG&E **$0.000 / $0.000 / $0.000**; SCE $0.040 / $0.093 / $0.000.
- **Table 11, low-income households, at 177** — PG&E 0.087, SCE 0.093, SDG&E **"-"**.
- **Text at 153:** *"Since SDG&E residential customers already have a simple payback period
  of less than nine years without the ACC Plus, SDG&E residential customers who interconnect
  during the five-year glide path and transition period will not receive an adder."*
- **The reason, Table 6 at 153:** SDG&E residential paybacks *without* any adder were already
  4.70–8.43 years (non-CARE 5.95 stand-alone / 4.70 with storage; CARE 8.43 / 6.98), inside
  the nine-year target the adder exists to hit — **because SDG&E's retail rates are the
  highest of the three**. So the same rate level that makes SDG&E solar attractive is exactly
  what disqualifies it from the incentive.
- Corroborated by **D.23-11-068** (virtual NBT), which carries ACC Plus adders for PG&E and
  SCE only.
- URL: docs.cpuc.ca.gov/PublishedDocs/Published/G000/M500/K043/500043682.PDF (retrieved
  2026-09-08). No eligibility conditions or vintage variation to model: the value is zero for
  every application year 2023–2027 and both tiers.

**Residual, recorded not hidden:** SDG&E's *own* Schedule NBT sheet was never located. Its
tariff portal (`tariffsprd.sdge.com`) is a static Next.js app whose listing is fetched from an
endpoint not discoverable in its bundles, and every `www.sdge.com/sites/default/files/...`
name that works for other schedules (`elec_elec-scheds_<id>.pdf`, the `regulatory/` dir)
404s for NBT. The adopting decision is the instrument that *sets* the number, so citing it is
not a downgrade — but if the sheet turns up, add it as corroboration.

### DECISION — encode the negative as a positive fact, not a raise
`SDGE_ACC_PLUS` is an `AccPlusTable` of explicit zeros, 2023–2027, both tiers, carrying the
full citation. `acc_plus_table` is now a dict lookup that still raises for any utility whose
row has not been read (test pins `"SCE"`), so **"no table" and "a table of zeros" stay
distinguishable** — which was the whole point of the old raise. The class docstring says so.

**Consequence:** on SDG&E `acc_plus_eligible` no longer moves a dollar. `scripts/nem3_report.py`
therefore sets it **True** (the demo household is eligible) instead of False-as-a-hedge, and a
test asserts an eligible and an ineligible SDG&E customer settle to the identical
`amount_due`. The "conservative path" comment is gone; it was hedging against a number we now
have.

### Honest-broker note added
`netting._notes` now emits, whenever an eligible customer's adder resolves to zero: *"ACC Plus
adder is $0.000/kWh for SDG&E applications in 2026. This is an adopted value, not a missing
one … PG&E and SCE customers do receive one, so figures quoted from their tables do not
transfer."* Silence would have read as an omission, and **this is a specific way a San Diego
customer gets misled**: the widely-cited ACC Plus numbers are PG&E's and SCE's, and the
low-income tier — $0.087–0.093/kWh there, the largest adder in the decision — is worth exactly
nothing here. A calculator that generalises PG&E's table overstates a CARE SDG&E household's
export value by ~9¢/kWh.

### Side finding, not acted on
SDCP publishes a **"San Diego Community Power Generation Adder"** for its NBT customers — a
CCA-side export adder, entirely separate from ACC Plus, and *not* covered by the D.22-12-056
zero. It plugs into the existing `cca_export_terms` hole (open item: "CCA export terms —
netting excludes the CCA generation credit by default, so a CCA customer's result is a lower
bound"). Sourcing it would turn that lower bound into a real number for SDCP customers.

## 2026-09-08 — Session 13 (the SDG&E parser meets a real export — and loses, twice)

**435 tests green (was 418), ruff clean, wasm parity and render checks pass.** Answering "where else can free SDG&E data come from" turned up a **real,
author-anonymized SDG&E export committed to a public repo** —
`corruptbear/my_sdge`, `example/Electric_60_Minute_11-1-2022_11-30-2022_20230819.csv`
(39 stars, active as of 2026-06-10, **no LICENSE file** — so the bytes may NOT be vendored;
re-download at test time or hand-author an equivalent fixture and cite the URL).

### FINDING — `src/greenbutton/sdge.py` would have refused dad's file
`scripts/inspect_export.py` on that file: *"not recognized as a PG&E or SDG&E Green Button
interval export."* The parser was written to a **PG&E-shaped** table
(`TYPE,DATE,START TIME,END TIME,...`, 24-hour `H:MM`, `IMPORT`/`EXPORT` columns). The real
file is:

```
Name,SDGE VICTIM / Address,... / Account Number,... / Disclaimer,...
Title,CSV Export Electric Meter(s)
Resource,Electric / Meter Number,... / Interval UOM,Minute(s)
Reading Start,11/1/2022 00:00 / Reading End,11/30/2022 23:00
Total Duration,30 Days / Total Usage,817.415 / UOM,kWh
Meter Number,Date,Start Time,Duration,Consumption,Generation,Net
"00000000","11/1/2022","12:00 AM","60","0.2200","","0.2200"
```

Four concrete differences: a **`Duration` in minutes instead of `END TIME`**; **12-hour
`h:MM AM/PM`** times; **`Consumption`/`Generation`/`Net`** rather than `IMPORT`/`EXPORT`; every
field **quoted**, with a richer metadata preamble (`Total Usage` is a free checksum — parse it
and assert against the summed series).

**Caveat, do not over-correct:** this is ONE file, 60-minute, from the 2022–23 portal, and its
`Title` row says *"CSV Export"* while the repo README calls it the Green Button Download — so
SDG&E may emit more than one CSV shape. **Sniff and accept both**, do not swap one guess for
another. The 15-minute variant is still unseen.

### Also free, also unused
- Same repo carries **9 vintages of independently hand-transcribed SDG&E rate YAMLs**
  (2023 → 2026-06-01, incl. 2026-01-01 and 2026-04-01) plus the 1/1/26 and 6/1/26 Total Rates
  PDFs and `Res_2021V_042026.pdf` (SDCP). An independent second reading of the same tariff
  sheets is the only validation of our specs available without a bill.
- Green Button Alliance samples (green-button.github.io/samples) are **all synthetic and all
  XML** — no use for the CSV parsers.
- **An SDG&E bill PDF alone, with no interval data, validates the dollars-from-bucketed-kWh
  half of the gate**, because TOU bills print kWh *and* $ per period. Much smaller ask than a
  13-month export; also the cheapest route to settling open decision 9 (CARE on a CCA).

### FINDING 2, the expensive one — SDG&E writes a TRUE 25-hour fall-back day
Caught only because the file parsed far enough to reach the duplicate-timestamp guard.
`11/6/2022` carries **25 rows**, with `1:00 AM` written **twice** — the real PDT hour and the
real PST hour, in real-time order. PG&E writes 24 nominal labels and sums both physical hours
into one reading. `_common.localize` hardcoded `ambiguous=True`, which sends *every* ambiguous
label to the PDT fold, so both SDG&E rows collided on one instant and `finalize` rejected the
file.

**This is the second time the shared "both IOUs run the same Opower platform" premise has been
wrong**, and it was wrong in the module docstring as a stated fact. The premise is now
retired: `_common.py` says plainly that the formats are less alike than they look.

### DECISION — resolve the DST fold from FILE ORDER, not from the utility
`_fold_flags` infers the convention from the data instead of branching on utility: no repeated
label means the PG&E summed-reading convention (all-`True`, unchanged behaviour, second hour
surfaces as a gap); a label appearing exactly twice means the SDG&E true-day convention (first
occurrence PDT, second PST, no gap, no energy merged). Three or more occurrences is not a fold
and raises `AmbiguousDSTError`. Chosen over a utility flag because a *third* export shape then
costs nothing, and because the file is the authority on what the file contains.

### DECISION — the `Total Usage` checksum is a NOTE, never a rejection
The preamble's declared total matched the summed `Consumption` column to the digit (817.415
kWh), which is free proof every row was read. It is still reported rather than enforced: the
semantics on a *solar* account are unverified (consumption sum or net sum?), and a file with
legitimately missing rows could undershoot a total computed over the requested range. Turning
one observation into a rejection rule is how a valid export gets refused — the exact failure
mode HANDOFF.md warns against.

### What changed
- `_common.split_header_and_table` now finds the table by **signature** (a row with a date
  column and a start-time column, >=3 fields) rather than a literal `TYPE,`. Required: SDG&E's
  preamble contains `Meter Number,00000000` *above* a header that also starts `Meter Number`,
  so a leading-token test stops on the wrong line. Billing-history headers still match, so
  `check_not_billing_summary` keeps producing its specific message.
- `_common.to_minutes` accepts 12-hour `h:MM AM/PM` alongside 24-hour `H:MM`, with range
  checks and a clear error instead of an `astype(int)` traceback.
- `sdge.py` accepts both shapes: `Duration` is reconstructed into the inclusive-last-minute
  end so the shared span-vs-modal-step cross-check still applies; timestamps are built from
  date + minutes-since-midnight rather than string concatenation, so one time parser serves
  both shapes; `Consumption`/`Generation` join `IMPORT`/`EXPORT` as recognised registers, with
  blank `Generation` cells treated as zero rather than as an error.
- 17 new tests, all hand-authored to the observed shape. **The real file is not vendored** —
  that repo has no LICENSE.

### Still unverified — do not read this as "the SDG&E parser is validated"
One file, one portal vintage, **60-minute**, **November only**. Unseen: the 15-minute
meter-shape variant; **spring-forward on either shape** (both conventions happen to survive
the current `shift_forward` policy, but that is luck, not evidence); whether `Net` is
per-interval netted for a NEM account and therefore whether `Consumption` is gross — which M3
needs before it prices a solar export. **No real SDG&E bill has still ever met the engine**;
the site's reconciliation-gate copy is unchanged and remains accurate.

## 2026-09-08 — Session 12 (the site stops looking generated: the tariff-sheet redesign)

**418 tests green, ruff clean, golden bills untouched.** No engine work. Cameron: the session-11
site "instantly signals ai perfection and no creativeity" — content and structure fine, look
generic. He was right, and the diagnosis is worth keeping because it generalises.

### What actually signalled "generated", and why
Every one of these was a **default nobody decided against**, not a bad choice:
1. A desaturated neutral + one muted accent from a single hue family — what "safe good taste"
   optimises to. Nothing in it anyone could disagree with.
2. `border-radius` on every card, panel, button and bar. Uniform softness is a tell.
3. **Cards** — bordered rounded rectangles as the universal container.
4. One centre axis, near-identical vertical padding per section. Nothing hung into a margin,
   bled off an edge, or broke the line.
5. The mono-uppercase-letterspaced eyebrow, used six times.
6. No density contrast and nothing hand-made — no passage a person had to decide.
The deepest failure: **the design expressed nothing about what the product is.**

### DECISION — the site becomes the document it is about
Cameron picked, from four options: **utility document**, pushed **hard**, **unexpected colour
pairing**, **characterful type**. So: a tariff sheet. Two-colour offset print on manila —
**oxblood + sulphur** on `#EAE3D3`. **Zero border-radius anywhere on the site.** A left rail of
mono margin-annotations (`00`–`05`) carries every block, which is what kills the centred-stack
tell. Ledger rows with right-aligned mono figures replace the stat cards; findings became
numbered notes with the numeral hanging in the margin; charts sit on bordered "plates" with
`FIG. 1` headers.
**The signature device is a rotated stamp: `NOT A BILL / NO AMOUNT DUE`.** The tool
deliberately prices nothing, and a document says that the way a document would. It is the one
element that could not appear on any other site.

### DECISION — colour carries meaning, and one hard rule
`--sul` (sulphur) is a **FILL ONLY** — 1.89:1 on paper, so it must never carry text; accent
text is always `--ox`. And **`--ox` means exactly one thing: the expensive hours.** Fig. 2's
month bars were oxblood in the first draft and were changed to `--mark`: reusing the accent
for "just data" would have drained it of meaning. Every token was solved for contrast, not
picked — full matrix in the design-system skill.

### DONE — type with a point of view
**Archivo** is variable on weight *and width* (62–125%), so one file gives both voices:
`font-stretch:125%` + uppercase for the display, normal width for body. **Space Mono** carries
every number, label, stamp and axis. Two families, each with a job. Replaces the
Newsreader/Public Sans/IBM Plex trio, which is *the* default tasteful trio.

### ⭐ THE BROWSER PAID FOR ITSELF AGAIN — three defects in one pass
All three passed jsdom, ruff and pytest:
1. **A JS syntax error** — a missing `)` on `svg.appendChild(svgEl(...)` in `monthChart`. The
   render test caught it as `__renderInspection is not a function`. Same class of bug session
   8d hit. `node --check` on the extracted inline script located it in seconds.
2. **The label collision came back.** New chart geometry put the band caption and the
   "BUSIEST" direct label 9px apart again. `T = 64` now exists specifically to prevent it —
   **it is not spare whitespace**, and this has now been broken and re-fixed twice.
3. **The `§` glyph renders as a speck** in Space Mono at label sizes. All section marks (tool
   rails and methodology's six `§n` headings) became zero-padded numerals — one convention
   across the site.

### DELIBERATE TEST CHANGE — assert the guarantee, not the phrasing
`test_tool_render.mjs` asserted the demo banner matched `/demonstration file/i`. The new copy
says "Specimen … invented data, not a real household's". Rather than bend the copy to the
test, the assertion now requires the banner to **name the data as fabricated AND say it is not
real** — the guarantee it existed to enforce, now phrasing-independent. Changed in the same
commit as the markup, per the design-system skill's own rule.

### Scope
`index.html` rebuilt; `privacy.html` / `terms.html` rewired to the new chrome (their old nav
markup referenced classes that no longer exist); `methodology.html` migrated by **token and
font swap only** — it keeps its calmer long-form layout, which suits a reading document, and
still holds its own copy of the palette. Migrating its layout is the remaining tidy-up.

### Next
Unchanged and still ahead of all of this: dad's SDG&E export + bills.


## 2026-09-08 — Session 11 (the site: UI overhaul, legal pages, self-hosted fonts, a browser)

**418 tests green, ruff clean, 11/11 PG&E golden bills unchanged.** No engine work: this
session is entirely `docs/`, plus two project skills and a screenshot tool. Cameron's brief
was that the site "not look to just be AI slop" and be followable by a non-technical person.

### DONE — project skills, committed so they travel (`.claude/skills/`)
Cameron installed Anthropic's **Design** skill pack on **claude.ai**, which does NOT reach
Claude Code — the CLI loads skills only from `~/.claude/skills/`, `<project>/.claude/skills/`
and plugin marketplaces, and the official CC marketplace carries no such pack (checked; its
`frontend-design` plugin has one skill). Rather than chase it, two **project** skills were
written and committed: `design-system` and `accessibility-audit`. Project scope was chosen
deliberately — committed skills load in every environment the repo reaches, including a fresh
clone and a cloud sandbox, and they can encode THIS repo's invariants, which a generic pack
cannot: the DOM contract `test_tool_render.mjs` pins, the no-dollars rule, the generated
`engine.js`.

### DONE — the tool page overhauled
The page had eight identically-shaped sections of heading + prose + card, so nothing led and
the tool argued for its own virtue before showing anyone their data. Now two states that look
different: a **landing** (asymmetric hero, drop zone, three numbered steps) and a **report**
(masthead with utility + date range, one dominant figure, then evidence). Technical material
moved into disclosure panels. Jargon cut at first use ("Green Button file" -> "usage file");
chart labels read "7 p.m." not "19:00". **Findings prose was NOT touched** — it is generated
in `src/report/inspect.py` precisely so it stays tested, and it was already plain English.
The DOM contract was **preserved exactly rather than relaxed**; no test was weakened.

### DONE — privacy.html and terms.html, and `docs/site.css` / `docs/fonts.css`
Written from what the site actually does, verified not assumed. No cookies, storage,
analytics or backend. But the page did make third-party requests, and a privacy page omitting
them would be the exact failure this project exists to avoid. Also stated: the *timing* of the
jsDelivr fetch could reveal that someone at an IP used a tool of this kind, though not what
was in their data. Contact is the public issue tracker — Cameron's email is not mine to
publish. ⚠ These are plain-language documents, **not lawyer-drafted**; get them reviewed
before M5 puts them in front of recruited strangers.

### ⭐ THE LESSON OF THE SESSION — headless tests do not see the page
Everything below passed jsdom, ruff and pytest, and was still wrong. jsdom does no layout.
Installing Chromium (playwright) and *looking* found, in one run:
1. **A label collision.** The hour chart's "4-9 P.M." band caption sat on top of the
   "busiest: 6 p.m." direct label whenever the busiest hour fell inside the band — the common
   case, and the only case that matters.
2. **Bars at 1.5:1.** Non-peak bars were drawn in `--rule-2`, a *hairline* colour: 1.58 light
   / 1.54 dark against the panel, where WCAG 1.4.11 wants 3:1 for meaningful graphics. Those
   bars are the data. New `--mark-muted` token (3.31 / 3.37). **A border colour is not a data
   colour.**
3. **A regression I had introduced myself** — the rewrite dropped the Google Fonts `<link>`,
   so the entire editorial look was silently falling back to Georgia. Found only by looking.
`scripts/screenshot_site.py` is committed; playwright is an **optional local extra**, kept out
of `environment.yml` so CI is not made to download a browser.

### DONE — fonts self-hosted; the site now requests nothing from Google
A font on someone else's server reports every visitor's IP to that company on every page
view, on a site whose headline promise is the opposite. `docs/fonts/` now holds the woff2
files (368 KB on disk; ~204 KB fetched on a typical English page view, since `unicode-range`
means `latin-ext` downloads only when needed). **Newsreader and Public Sans are variable
fonts** — Google serves one byte-identical file whatever weight is requested, so six files
collapsed to two over a 400-600 range. All three families are SIL OFL 1.1; licence and
attribution travel in `docs/fonts/`.
⚠ `@font-face` lives in its own `fonts.css`, NOT in `site.css`, because `methodology.html`
needs the fonts but must not inherit the shared chrome — `site.css` sets `th{width:44%}`,
which would wreck that page's tables. That collision was caught before shipping, not after.

### Accessibility, measured rather than asserted
`--ink-3` failed AA body text on every light surface (3.22-3.71) across eight usages including
the `font-size:10` chart axis labels; solved for, not guessed (`#676C61` / `#888E7F`,
`--accent` -> `#0B784F`). `role="img"` hides per-bar `<title>` from screen readers, so
`#hourTable` / `#monthTable` now carry the same numbers. Headings skipped `h1 -> h3` at the
steps. `methodology.html` picked up the retuned tokens but is otherwise **unaudited** — its
heading order, `<th scope>` and reflow are the open work.

### Still open
- `methodology.html` still keeps its own copy of the palette instead of linking `site.css`;
  migrating it needs its nav/footer rules reconciled with the shared ones first.
- Legal pages want a lawyer's eye before M5.
- Arrows (U+2190/2192) are outside Google's latin subsets, so they render from a fallback
  font. True before this session too; cosmetic.

### Next
Unchanged: dad's SDG&E export + bills outrank everything. Then SDG&E ACC Plus, then the
earlier TOU-DR2 / EV-TOU-5 vintages.


## 2026-09-08 — Session 10 (San Diego Community Power overlay; the SDCP 403 was solvable)

**418 tests green (was 384, +34), ruff clean, 11/11 PG&E golden bills reconcile with
byte-identical residuals** (worst +$0.22). Dad's SDG&E data had NOT arrived (checked first:
`data/` unchanged since July 19, nothing SDG&E-shaped), so next-action #0 stayed blocked and
this took next-action #1.

### DONE — the SDCP overlay, and it did NOT need the manual download HANDOFF asked for
Four specs, two jurisdiction cohorts x two 2026 vintages:
`sdcp_2021v_tou_dr1_generation_{2026-01-01,2026-05-01}.yaml` and the `2022v` pair.
Both San Diego CCAs are now authored, so whichever one dad turns out to be on, his bill goes
straight to reconciliation.

### ⭐ THE 403 WAS ONLY ON `curl` — RECORD THIS, IT COST SESSION 9 THE WHOLE ITEM
sdcommunitypower.org still returns HTTP 403 to `curl` (re-verified this session, with a
browser UA). But **the agent's own fetcher gets through**, and although it cannot parse a
PDF it **saves the binary to disk anyway** and prints the path. So the working method for
any 403-guarded PDF is:
    WebFetch the PDF URL (any prompt)  ->  read the saved path out of the result
    ->  `pdftotext -layout` it locally  ->  transcribe from the extracted text
which is exactly the session-8 method, just with a different way of getting the bytes.
Session 9 concluded the sheet was unreachable and deferred the whole overlay to a human
download; it was reachable. **Generalise: "curl got 403" is not "the document is
unavailable".**
Also found what session 9 missed — the rates are on the site as HTML, on two cohort gateway
pages the landing page links but does not name: `/residential-rates/2021v/` and `/2022v/`.

### DECISION — the cohort is a PROVIDER, not a product or a territory
⭐ **SDCP publishes two different rate sheets by enrollment cohort, and they differ.**
2021V (San Diego, Chula Vista, Encinitas, Imperial Beach, La Mesa) vs 2022V (National City,
unincorporated county). The 2022 cohort pays a flat **+$0.00559/kWh** on the 5/1/2026
vintage (+$0.00558 on 1/1/2026) in every period except summer super-off-peak, which is
floored at $0.01000 for both. ~$33/yr on 6,000 kWh — small, but **not electable**, and
invisible on SDCP's marketing pages, which quote one set of figures.
Modeled as two providers (`SDCP-2021V`, `SDCP-2022V`) rather than a territory table, so the
loader **refuses to pick one** exactly as it refuses to pick between SDG&E and a CCA. Four
providers now supply TOU-DR1 generation; `AmbiguousProviderError` names all four.
⚠ **Both cohort sheets carry a footer saying the rates apply "to all customers in all
jurisdictions served by Community Power"** — which cannot be true of both, since they print
different numbers. Treated as stale boilerplate; the cohort must be confirmed from the bill.

### DECISION — PowerOn only, following the CEA precedent
PowerOn is SDCP's default/standard product (auto-enrolment). PowerBase (cheaper opt-down)
and Power100 (opt-up) are transcribed into the spec headers and deliberately **not** modeled
— a customer must actively elect them. Power100 = PowerOn + $0.01000/kWh is not derived: the
sheet prints it as its own one-line table, and the arithmetic holds in all 12 published cells
of both cohorts.

### CARE — read off the sheet, and better evidenced than CEA's
`care == standard` on the SDCP layer. SDCP's Rate Key states the mapping "will not impact
service, billing, or **CARE/FERA status**"; its SDG&E-to-SDCP table maps base schedule codes
only (TOUDR1 -> TOU-DR-1) with no CARE or FERA variants anywhere, and no rate table on the
sheet has a CARE column. SDCP prices by SCHEDULE; CARE is a STATUS SDG&E administers.
Corroboration it is a real distinction rather than an omission: where SDG&E has a separate
low-income *schedule*, SDCP does publish a separate rate (DR-LI; DR-LI-MB at a flat
$0.13780 PowerOn).

### ⭐ NEW EVIDENCE ON OPEN DECISION 9 — and it points AGAINST what the CEA spec asserted
Open decision 9 recorded, as an unverified consequence, that a CARE customer on a CCA gets a
*smaller* total discount than a bundled one. **SDG&E's own SDCP Joint Rate Comparison
(1/1/2026) implies the opposite.** In that document `(CCA total $/kWh - SDG&E bundled total
$/kWh)` is **invariant to CARE/FERA status** — across DR, TOU-DR, TOU-DR1, TOU-DR2 and all
three SDCP products, agreeing to <=2e-5 in 11 of 12 rows (the outlier, TOUDR2-FERA, is
1.7e-3). If the 35% were applied only to SDG&E's own charges, the CCA customer's absolute
discount would be smaller by 0.35 x EECC and that delta could not be class-invariant.
**The engine was NOT changed.** Reasons, recorded so this is not reopened casually:
  * The JRC's per-line allocation is presentational, not tariff structure — its SDG&E
    *generation* line is identical in the CARE and non-CARE tables, which the tariff says is
    false (our specs reconstruct SDG&E's printed Total Adjusted CARE Rate as
    `0.65 x (UDC - 0.00864) + 0.65 x EECC`, exactly, on all four vintages). Only the TOTALS
    carry information — and the class-invariance is a totals-level fact, so it survives.
  * Against it stands **direct bill evidence on the other utility**: 11 real PG&E bills for a
    CCA (3CE) + CARE household reconcile within +$0.22 with the discount applied to the
    delivery layer only. A reconciled bill outranks a comparison document.
  * The two need not conflict — PG&E and SDG&E may compose it differently.
Dollar impact of being wrong: 0.35 x EECC, ~4-5 c/kWh, **~$170-210/yr**. The CEA spec header
overstated its case and has been corrected in place to carry both sides, per session 9's
lesson that an overclaim does its damage inside a citation-bearing file.

### ⭐ FINDING — the exit fee, not the CCA's rates, decides; and it bites in the charging window
On the matched 1/1/2026 vintage SDCP undercuts bundled EECC in **every** period (the opposite
shape to CEA, which is seasonally opposite). Add the PCIA a CCA customer pays and a bundled
one does not, and at a **2018 vintage exactly ONE period flips: summer super-off-peak**
(0.01000 + 0.03662 = 0.04662 vs SDG&E 0.04126) — the window a battery charges in and the one
load-shifting advice targets. At a **2024 vintage, 5 of 6 periods flip**. So "SDCP is
cheaper" is true in general and false in precisely the hours a storage or EV recommendation
turns on, and no single verdict can be published for "SDCP customers". Both pinned by test.

### Verification of the transcription (the numbers came off a 403-guarded PDF)
Four structural identities hold exactly across the 24 cells, none of which would survive a
faulty extraction: Power100 - PowerOn = $0.01000 in all 12 cells of both cohorts; the cohort
differential is a constant $0.00559 (May) / $0.00558 (Jan) in all 10 non-floored cells and 0
in the 2 floored ones; summer super-off-peak is exactly $0.01000 on all four sheets; and
SDCP's published average bills imply a $0.01000 Power100 premium and $0.13000/kWh blended
PowerOn against the JRC's $0.13021. Independently, the **1/1/2026 2021V figures extracted
this session match session 9's transcription of the same PDF digit for digit**, and the HTML
cohort pages match the PDFs cell for cell.

### Also corroborated in passing — open decision 1, now with a THIRD witness
SDCP's January sheet prints weekday super-off-peak as "Midnight - 6:00 a.m." plus "10:00
a.m. - 2:00 p.m. **in March and April**"; its May sheet prints "Midnight - 6:00 a.m.; 10:00
a.m. - 2:00 p.m." year-round with no month restriction. The **same publisher's two dated
sheets differing in exactly the disputed way** is the cleanest corroboration yet that the
underlying tariff changed on 2026-05-01. SDG&E's own publications were the first witness,
CEA the second. The caveat stands (still not a P.U.C. sheet), but it is now well supported.

### Next
Dad's SDG&E export + bills (next-action #0) still outranks everything. SDCP is done, so the
next unblocked units are SDG&E ACC Plus and the earlier TOU-DR2 / EV-TOU-5 vintages.


## 2026-09-08 — Session 9 (CCA overlay: vintaged PCIA + Clean Energy Alliance)

Commit `dd96f12`. **384 tests green (was 357), ruff clean, 11/11 PG&E golden bills reconcile
with identical residuals, M2 verdict unchanged.** Dad's SDG&E data had NOT arrived (checked:
`data/` unchanged since July, nothing SDG&E-shaped on disk), so next-action #0 stayed blocked
and this took next-action #2.

### DECISION — author the CCAs rather than wait to learn which one dad is on
HANDOFF had the overlay blocked on "which CCA". That is only a blocker if you author one.
Both San Diego CCAs publish their residential rates, so doing both dissolves the dependency
and means whichever one he is on, his bill goes straight to reconciliation instead of
waiting a further session. CLAUDE.md invariant 4 names this work explicitly.

### DONE — the PCIA is now VINTAGED, and the vintage is never guessed
`PerKwhAdder` gained `per_kwh_by_vintage` + `vintage_pin`, selected by a `vintage` argument
threaded through `compute_layer` / `compute_bill` / `NbtSettings` — deliberately the same
shape as `Baseline.allowances` + `territory`, and raising the same way rather than
defaulting. All four SDG&E TOU-DR1 delivery vintages now carry the CCA column of their own
sheet's PCIA table (the 1/1/2026 sheet prints a different table from 4/1 onward, so each
carries its own; the 2001 Legacy vintage is absent because it is Direct-Access-only).
**Why it earns the complexity:** the CCA column spans 0.01538..0.05055 $/kWh. That 0.035
spread is ~$211/yr on a 6,000 kWh household — more than the entire annual saving the PG&E
case study found from switching supplier. Pinning one vintage would have been the largest
single error a CCA bill could carry.

### DONE — Clean Energy Alliance generation layer (`cea_tou_dr1_generation_2026-06-01.yaml`)
From CEA's adopted schedule effective 6/1/2026 — the same vintage as our SDG&E delivery
spec. Carries the **Clean Impact Residential Rate Relief Credit, -$0.03871/kWh**, a standing
line that MORE THAN OFFSETS the 0.03670 PCIA a 2018-vintage customer pays; omitting it would
overstate a CEA customer's cost by more than the exit fee that gets all the attention. No
expiry is printed, so it is modeled as current-vintage-only and must be re-read next time.
CARE: CEA's own mapping table sends TOU-DR-1 / -CARE / -MB to one CEA rate, so `care` ==
`standard` here, read off the sheet. ⚠ That implies a CARE CCA customer gets a smaller total
discount than a CARE bundled one — follows from the two published documents, NOT confirmed
against a real bill, flagged in-spec.

### ⭐ FINDING — CEA is not uniformly cheaper than SDG&E, it is seasonally OPPOSITE
Against bundled EECC on the same 6/1/2026 vintage, CEA is dearer in every summer period
(summer on-peak 0.55397 vs 0.34920, +59%) and cheaper in every winter one (winter off-peak
0.08433 vs 0.19304, -56%). So whether a CCA wins depends on the household's seasonal shape
and its PCIA vintage — not on the CCA. That is exactly what a board's "rates competitive
with SDG&E's" cannot tell any individual, and exactly the question this engine settles.
Pinned by test.

### ⭐ BUG THE NEW SPEC EXPOSED — the loader had no notion of *provider*
Bundled EECC and CEA are both legitimately `TOU-DR1` / `generation`. `_matching_specs`
filtered on schedule_id + layer only, so adding CEA made `load_specs` pick by effective date
across two different suppliers — a wrong answer that looks entirely right, off by up to
20 c/kWh in a single period. `load_specs` / `load_spec_versions` now take `provider` and
raise `AmbiguousProviderError` when several match and none was named. **Caught by two
pre-existing tests, not by inspection** (test_sdge_vintages' version count, and the nem3
netting test) — the argument for asserting counts rather than just properties.

### CORRECTED — two claims of mine that the new tests falsified
Both had already been written into citation-bearing spec headers, which is exactly where an
overstatement does damage:
1. "the vintage spread is wider than the schedule's entire super-off-peak generation rate" —
   FALSE (0.03517 vs 0.04121). Replaced with the $211/yr framing, which is true and checkable.
2. "the rate relief credit is larger than CEA's whole winter super-off-peak rate" — FALSE
   (0.03871 vs 0.05138). Replaced with "more than offsets a 2018-vintage PCIA", which is true.

### RESEARCH CAPTURED — San Diego Community Power, NOT yet authored (and why)
SDCP's **current** schedule is effective **2026-05-01** and could not be retrieved: the site
returns HTTP 403 to scripted requests, the page's PDF links do not survive markdown
conversion, and the URL is not indexed. Only the **1/1/2026** sheet is reachable
(`sdcommunitypower.org/wp-content/uploads/2026/01/Res_2021V_2026.pdf`).
**Deliberately NOT authored from the January sheet alone:** `load_specs` picks the newest
version effective on or before the bill date, so a January-only SDCP spec would silently
price a September 2026 bill at January rates. Shipping a stale-only spec for a utility whose
reconciliation gate is unmet is a worse failure than shipping none.
Transcribed here so it is not re-researched — SDCP **TOU-DR-1, effective 1/1/2026**,
PowerOn / PowerBase $/kWh:
    summer on 0.29626 / 0.27528   off 0.08656 / 0.07884   super-off 0.01000 / 0.01000
    winter on 0.22551 / 0.20901   off 0.14787 / 0.13627   super-off 0.06163 / 0.05548
Products: **PowerOn is the standard plan** (53% renewable); PowerBase 45% (cheapest);
Power100 = PowerOn + $0.01/kWh (100% renewable). Two enrollment cohorts with separate rate
documents: **2021V** (San Diego, Chula Vista, Encinitas, Imperial Beach, La Mesa) and
**2022V** (National City, unincorporated county) — a jurisdiction fact, like climate zone.
**Structural contrast worth keeping:** on the matched 1/1/2026 vintage SDCP is cheaper than
bundled EECC in *every* period (summer super-off 0.01000 vs 0.04126, -76%) — the opposite
shape to CEA. But adding a 2018-vintage PCIA (0.03662) flips the cheapest periods: summer
super-off becomes 0.04662 vs SDG&E's 0.04126, i.e. **the exit fee can invert the comparison
in exactly the low-price hours a battery or EV charges in**. Worth a test once authored.

### Next
Dad's SDG&E export + bills (next-action #0) still outranks everything. After that, SDCP —
which needs one manual PDF download, see HANDOFF.


## 2026-09-08 — Session 8d (the site became a tool; Green Button inspector)

Cameron: "I don't want the site to just be a glorified readme — I want anyone including a
non-technical person to be able to use it. Also do that Green Button export inspector."
Those turned out to be one task: the inspector is the engine, the page is its front door.

Live: **https://camerongordonn.github.io/energy-advisor/** (the tool)
      **/methodology.html** (the M4 writeup, moved from index.html)
357 tests green (was 331), ruff clean, both CI jobs green including the new browser job.

### DECISION — run the REAL Python engine in the browser (Pyodide/WebAssembly)
The alternative architectures and why they lost:
  * **Backend API** — would mean the customer's meter data leaves their machine and lands
    on a server. This project's privacy posture is that real exports never even enter git;
    accepting uploads would contradict it, and would cost money.
  * **Reimplement the parsers in JavaScript** — two implementations drift, and the one
    visitors use would be the untested one. That is precisely the "what is tested" vs "what
    users get" split the whole project exists to avoid.
  * **CHOSEN: Pyodide.** The page runs the actual `greenbutton` + `report.inspect` modules
    the pytest suite covers. Nothing is uploaded — there is no server — so "your file never
    leaves your computer" is architecture, not a promise.
`docs/engine.js` is GENERATED from `src/` by `scripts/build_web_engine.py`;
`tests/report/test_web_engine.py` fails if it goes stale. Editing a parser and forgetting to
rebuild is a red test, not a silently outdated website.

### DECISION — the tool prices NOTHING, and says why
Usage arithmetic on a customer's own meter carries no reconciliation gate, so it is safe to
run for any utility. Dollars need a tariff spec, and invariant 1 permits that only where the
engine reproduces real bills — true for PG&E, **not** true for SDG&E. So the tool shows load
shape and refuses to show money, with the gate quoted on the page. Enforced by test, not
just intent: `Inspection` may carry no money-shaped field, findings may not contain `$`,
`¢` or `/kWh`, and the jsdom test asserts no dollar amount appears in any computed region
of the rendered page.

### ⭐ BUG THE WASM RUN FOUND — `report/__init__` was dragging in the whole bill engine
`report/__init__.py` eagerly imported `.reconcile`, which imports `yaml`, so
`import report.inspect` pulled the entire reconciliation and tariff stack. Native Python
never noticed. Pyodide failed loudly with `ModuleNotFoundError: yaml`. Fixed by making the
package lazy (PEP 562 `__getattr__`), which keeps the public API and drops the browser
payload to what the inspector actually needs. Good argument for running code in a
constrained environment: it surfaces accidental coupling that a fat environment hides.

### DONE — the inspector itself (`src/report/inspect.py`, `scripts/inspect_export.py`)
Auto-detects the utility by trying each real parser rather than sniffing formats. Reports
provenance (interval, span, coverage, gaps, estimated readings, DST days, export register)
and usage shape (monthly, hour-of-day, weekday/weekend, and the shares in the windows CA TOU
rates actually price). The 4-9 p.m. window is not a choice made here — it is the on-peak
window of *both* PG&E E-TOU-C and SDG&E TOU-DR1.
**Findings are generated in Python so the prose a visitor reads is tested.** Peak-share
bands are set around the 20.8% a perfectly flat load produces, not round numbers: the real
PG&E household at 26.9% now reads as "above average" instead of being reported as typical.

### DONE — sample data, fabricated on purpose
`docs/sample-usage.csv` is generated by the committed `scripts/make_sample_export.py` —
13 months, evening-peaked, DST-correct. Most visitors (recruiters included) will not have a
Green Button file, and publishing a real household's hour-by-hour occupancy pattern is not a
line worth crossing. Labelled as a demonstration everywhere it appears; the page shows a
banner. Invariant 6 governs *analysis*, and nothing draws a conclusion from it.

### Verification — three layers, all in CI
1. `pytest` — 357 tests, including inspector behaviour and bundle-drift.
2. `tools/test_engine_wasm.mjs` — loads the SHIPPED `docs/engine.js` under Pyodide in Node
   and compares against native CPython on the committed sample: **all 29 fields identical**.
   (Also verified against the real 8,423-interval PG&E export: 28/29 identical, the only
   difference being the filename.)
3. `tools/test_tool_render.mjs` — jsdom renders a real inspection through the page's own
   code: chart shapes, peak-window highlighting, demo banner, and the no-dollars rule.
A second CI job runs 2 and 3. Both were caught being useful immediately: the render test
found two unbalanced-paren bugs in the chart code and a `scrollIntoView` call that would
throw wherever it is unimplemented.

### Next
Dad's SDG&E export, expected today. `scripts/inspect_export.py` is now the first command to
run on it — see next-action #0.


## 2026-09-08 — Session 8c (the site is live)

Cameron pushed to **https://github.com/CameronGordonn/energy-advisor** (public, AGPL-3.0).
Site: **https://camerongordonn.github.io/energy-advisor/** — HTTP 200, CI green on `main`.

### Went live, with two GitHub quirks worth not re-debugging
The push landed on `session-4-nperiod-tou-m2`, which GitHub then made the default branch —
so `pages.yml` (triggered on `main`) never fired and the site 404'd. Fixes applied:
- Stale local `main` (session 3, 621c1c1) was a clean **ancestor**, so it fast-forwarded 10
  commits with no conflict. Pushed, and set as the default branch — which also gets the repo
  off a default branch named after a working session, a bad look on a portfolio repo.
- **Path filters do not reliably match on branch *creation*.** The first push to `main` did
  not trigger the deploy despite touching `docs/`. `workflow_dispatch` covered it.
- **Enabling Pages auto-creates a `github-pages` environment whose deployment branch policy
  is pinned to the then-default branch.** Ours was pinned to the session branch, so `main`
  deploys were rejected with "Branch main is not allowed to deploy to github-pages due to
  environment protection rules" — not a workflow bug, an environment policy. Fixed by POSTing
  `main` to `.../environments/github-pages/deployment-branch-policies`.

### Also done
README `OWNER/REPO` placeholders resolved to the real path (badges and the site link now
work). Repo description, homepage and eleven topics set for discoverability.

### Next
Dad's SDG&E export + bills, expected today (2026-09-08). Unchanged as next-action #0.


## 2026-09-07 — Session 8b (portfolio/publishing scaffolding; AGPL chosen)

Cameron reframed the goal: this becomes a **portfolio piece with a served website on
GitHub, regardless of whether it ever becomes a paying product.** That is a different
target from the roadmap's M5-gated "web UI", and it is much closer to M4's own DoD
("writeup live") than to product delivery infrastructure — so it is not a roadmap
override. What stays gated behind M5 is the interactive upload-and-report app.

### DONE — pre-publication PII audit of the whole git history (the blocking step)
Scrubbing a file does not scrub the commits that still contain it, so the history was
audited before anything goes public. **Result: clean, safe to publish.**
- `.gitignore` was correct in the **very first commit** (`data/`, `tests/golden_bills/raw/`,
  `*.pdf`, `.env`, `secrets.yaml`).
- **No bill PDF, Green Button export, or `data/` file has ever been committed** — the
  history contains zero `.pdf`/`.csv`/`.zip`/`.xml` paths.
- Two commits (`29b522d`, `b0df750`) match the unit-number string session 7 scrubbed. Both
  are benign: the M0 one is inside a **synthetic** parser fixture
  (`tests/greenbutton/conftest.py`: "1 TEST ST APT A, SANTA CRUZ CA", "TEST CUSTOMER",
  a fake account number), and the current-tree one is session 7's own scrub note quoting
  the string it removed. Session 7 had treated that synthetic fixture as PII; it never was.
- No occurrence of the email address, or of lease/tenancy/renewal terms, anywhere in history.
The only personal content in the repo is what session 7 **deliberately** decided to publish
(city, schedule, CARE status, exact bill dates and amounts). Settled; not reopened.

### DECISION — AGPL-3.0, asked and answered
Cameron chose AGPL-3.0 over MIT / source-available / no-license. Rationale recorded because
it is hard to walk back once public: the tariff engine is the substance of the project, and
the network clause stops a competitor or installer-tool vendor from running a modified copy
as a hosted service without publishing source, while leaving reading, running, learning and
contributing unrestricted — and Cameron can relicense his own code later. `LICENSE` is the
canonical FSF text **downloaded from gnu.org**, not hand-typed (661 lines). README gained a
License section stating that the tariff sheets and ACC tables it cites are public regulatory
filings not covered by the license, plus a not-financial-advice line.
⚠ The copyright line reads "Cameron Gordon" — inferred, correct it if wrong.

### DONE — CI, Pages, and a standalone `docs/index.html`
- `.github/workflows/ci.yml` — ruff + pytest on every push/PR, in the documented conda env
  via `setup-micromamba` with caching. **Its header states the honest scope limit**: the
  golden-bill reconciliation tests SKIP in CI because they need the gitignored real interval
  export, so a green badge proves the engine/schema/loader/tariff identities, **not** the
  ±$2 reconciliation. Said out loud so the badge cannot overclaim.
- `.github/workflows/pages.yml` — deploys `docs/` to GitHub Pages on pushes to `main`
  (free on public repos). Needs Settings -> Pages -> Source -> "GitHub Actions" once.
- **`docs/index.html` is now a valid standalone document.** It was authored body-only for
  the Artifact publisher (which supplies the wrapper), which meant a browser served it in
  quirks mode. It now carries `<!doctype html>`, `<html lang>`, charset/viewport/color-scheme
  meta, an OG card, and a `body{margin:0}` reset matching what the Artifact wrapper provided.
  ⚠ CONSEQUENCE: republishing this file **as an Artifact** now needs the wrapper stripped
  first — the Artifact tool wants page content without doctype/html/head/body. Pages is the
  canonical home from here; the artifact URL is a preview.
- README gained CI/license/python badges and a "Read the writeup" link, all carrying
  literal `OWNER`/`REPO` placeholders — **one sed away from correct** once the repo exists.

331 tests green, ruff clean throughout.

### Still open
- **Nothing is pushed.** The repo has no remote; creating and pushing it is Cameron's call
  and needs his GitHub account. Commands are in HANDOFF.
- The published Artifact is still private (share menu) — moot once Pages is live.
- Dad's SDG&E Green Button export + bills expected **2026-09-08**; that is the M1 unblock
  and outranks all of the above.


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
