# PENDING — merge this into SESSION_NOTES.md (newest first, at the top)

Written on branch `site-overhaul`, 2026-09-20. Not prepended directly because a parallel
`src/` session is working in the same tree and both entries need to land in one order.
Full working: `notes/site_overhaul_2026-09.md`.

---

## 2026-09-20 — Session 30 (the visual half of the site overhaul: four pages, two stamps, and three defects on "clean" pages)

HANDOFF's session-28 item 9. `src/` untouched; `docs/engine.js` and `docs/case-study.json`
untouched.

### ⭐ The stamp is now two stamps, and the split was Cameron's call

`NOT A BILL / NO AMOUNT DUE` sat under hero copy promising to re-bill a year under every rate
plan. Defensible but no longer obviously right: the device was authored in session 12 to say
the thing the tool then did — price nothing — and session 28 made it price. Three options
were put up with consequences; Cameron chose the split. **The hero stamps the claim**
(`RECONCILED ±$2 / 11 OF 11 REAL BILLS`), **`#priceOut` stamps the disclaimer**, beside the
verdict, where the money actually is. `.stamp.due` leans the other way. No test pins `.stamp`.
**Recorded in the design-system skill as a decision: do not re-merge without asking.**

### The design-system skill was wrong in four places

Three were flagged in the brief; the fourth surfaced while checking the first.

⭐ **Contract 2 was reversed, and the replacement is not "it prices now" either.** The tests
cover less than the old text implied: `test_the_inspection_carries_no_dollar_figures` guards
the **`Inspection` model's field names** and its JSON — one Python object, nothing about the
page. The page half is the jsdom test, which scans the six load-shape regions for `$<digit>`
*and separately asserts `#planTable` IS dollar-denominated*. So the boundary is three-part
(load-shape half never prices / R2 prices on purpose / a refusal stays clean), and the real
limit is the **derived one-household scope** with its four blocker codes, not a refusal.

Also fixed: `site.css:93`'s "a tool that deliberately prices nothing"; the skill's description
saying "two published pages" against a body saying four. The **accessibility skill** was stale
in the same direction and was updated too.

### ⭐ Three live accessibility defects on pages the skills recorded as clean

New `scripts/audit_layout.py` — Playwright over all four pages at 1280/640/320, and over the
tool page in **both** its closed and open states, checking reflow, heading skips over the
**accessibility tree**, and `th`/`scope`. It found faults on its first run:

1. **`h2 → h4` in the report.** The a11y skill said the finding cards sat under a "What
   stands out" `h3`. **That `h3` was not in the page.** Added.
2. **`h1 → h3` on first load.** Section 02 had no heading, and `#results`' `h2` is out of the
   tree while `hidden`. Added an `h2.sec` — the section was the only `.row` without one.
3. **~45 bare `th`s** across `index.html`'s generated tables. `methodology.html` has had
   `scope` since session 20; nobody had ever walked the tool page.

A fourth came from the screenshots: focusing `#results` painted a **4,700px oxblood focus
ring** around the report. Suppressed on that element only — it is a scroll-and-focus target,
not a control; the global rule is untouched.

**Reflow was clean everywhere**, including after the legal-page restructure.

### Contrast is now derived from the stylesheet, not retyped

New `scripts/contrast_matrix.py` reads the tokens out of `site.css`'s own `:root` blocks.
**The palette did not change and every recorded number reproduced exactly** — the hand table
had been right, and is now a derivation. One correction: `index.html` quoted `--ink-2` on
`--band` as 6.61; that is the **dark** figure, light is **5.86** and light is the binding one.

⭐ **The finding that changed a design decision: a fill's EDGE is a different number from the
text on it.** `--band` against the plate is **1.09 light / 1.25 dark** — the sulphur reads
instantly in light on *hue*, but luminance is what survives dark mode, and the current-plan
marker was invisible there. It now carries a 2px `--ink-2` edge (6.38 / 8.25).

### The legal pages joined the site; both charts had collisions

`privacy.html` and `terms.html` were a 42rem column adrift in a 76rem sheet. Both now use the
`.row`/`.rail` grid, **one row per `h2`**, numbered clauses with their numbers in the margin.
Measure unchanged. Fell out of it: `.gate` had no `max-width` (a refusal's rule ran wider than
its own reasons) and `.doc .callout` butted two paragraphs together.

**`#hourChart`**: the direct label's baseline landed exactly on the band's top edge whenever
the busiest hour was inside the band — the common case. `T = 64` was doing its job; the band's
own 10px overhang was the uncovered part. Now `BAND_LIFT = 6` / `LABEL_LIFT = 16`, commented
as a pair. **Third distinct way that corner has broken.**

**`#monthChart`**: rotated `−42°` ticks ran into the axis caption. The rotation is **gone** —
13 months across 698px leaves ~54px a tick and `"Jul 25"` needs ~33px. `monthLabel()`
compresses for the **axis only**; the `<title>` and `#monthTable` keep the engine's string.

No `<rect>` added or removed, so the pinned counts are untouched.

### The ranking now reads as a ranking

⭐ **The hierarchy was inverted**: the loudest row was the reader's *current* plan (full-width
sulphur) and the *recommended* plan was merely bold. Winner now carries oxblood rules top and
bottom; the current plan keeps sulphur as a highlighter on its **name**. New `.mbar` encodes
**the gap to the cheapest plan**, zero-based, with a `.vh` text equivalent.

⚠ **Tradeoff flagged rather than chosen silently:** the obvious move is an accent-coloured
winner bar. `--ox` means "the expensive hours" as a data colour, so painting the *cheapest*
plan oxblood inverts the site's one chart rule. All bars are `--mark`; the winner is marked
with `--ox` **as a rule**, which is how `site.css` already uses it.

### ⚠ The bundle test fails, and it is the parallel session's

`pytest -q` → **1 failed, 1771 passed**, on `test_the_committed_bundle_matches_src`. The
parallel `src/` session is working in **this same working tree** (`src/tariffs/bill.py`,
`src/report/reconcile.py`, new `src/tariffs/bucketed.py`, uncommitted). Demonstrated, not
assumed: `git stash push -- src tests` → that test passes → `git stash pop`. `docs/engine.js`
is byte-identical to `origin/main`.

**Whoever lands that `src/` work must regenerate `docs/engine.js` AND `docs/case-study.json`**
— the case study carries the bundle digest and is built from gitignored `data/`, so only
someone with `data/` can. The repo's standing stale-cache hazard, firing.

Baseline before this session: 1,711 passed, both node checks green. Node checks still green
(42 render assertions, dollar parity to the cent); ruff clean.
