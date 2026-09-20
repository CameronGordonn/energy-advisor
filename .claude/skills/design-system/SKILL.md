---
name: design-system
description: The visual system for this repo's four published pages (docs/index.html, methodology.html, privacy.html, terms.html) — design tokens, the theme contract, typography, the chart and ranking conventions, and the DOM/test contracts a redesign must not break. Load before changing any CSS, markup, or chart rendering in docs/, and before adding a page.
---

# Design system — energy-advisor site

Four published pages, served from `docs/` on GitHub Pages:

- **`docs/index.html`** — the tool. Drop a usage CSV, get load-shape analysis **and, for a
  household the engine can prove it prices correctly, a ranking of every rate plan in
  dollars**. Runs the real Python under Pyodide.
- **`docs/methodology.html`** — the M4 writeup.
- **`docs/privacy.html`**, **`docs/terms.html`** — the legal pages, prose only.

**`docs/site.css` is the shared stylesheet** and the single source of truth for the palette,
for `.vh` (visually hidden), for `.stamp`, `.gate`, `.row`/`.rail` and the `.doc` prose
chrome. **All four pages link it** and keep only page-specific rules inline. No page defines
a palette token of its own; if you find one, that is the bug. `methodology.html` was migrated
in session 20 — it had carried a fourth hue (`--warn`) for caveats, which was deleted rather
than aliased, because the system is two-colour.

Pages is the canonical home. `docs/index.html` carries its own `<!doctype html>`, `<html
lang>`, and `<head>`, so it is **not** an Artifact — do not route it through the Artifact
publisher without stripping the wrapper first, and prefer not to at all.

## The idea

The product exists to reproduce a utility bill to within $2, so the site is built as **the
document it is about**: a tariff sheet. Two-colour offset print on manila. Rules and ledger
columns do the structural work; **there is no border-radius anywhere on the site**, and
adding one is a regression, not a refinement.

**Every page is the same grid.** A `.row` is `8.5rem 1fr`: a left rail of mono
margin-annotations (`.rail`, a number plus a two-or-three-word tag) and the content beside
it. This is what stops the page being a stack of centred cards, and **all four pages now use
it** — the legal pages were a single 42rem column adrift in a 76rem sheet until session 30,
which made them read as though they came from a different site. Each `h2` there is its own
`.row`, so its number sits in the margin the way a numbered clause sits on paper.

**Reflow is part of the system, not an afterthought.** `.row>*{min-width:0}` in `site.css` is
load-bearing: a grid item's `min-width` is `auto` = min-content, so without it one `<pre>` or
wide table drags its column past the viewport and the *page* scrolls sideways instead of the
block. Anything that must scroll horizontally does so inside its own `overflow-x:auto` box,
and that box needs `position:relative` if it contains a visually-hidden (`position:absolute`)
caption. All four pages are checked at 1280 / 640 / 320 CSS px by `scripts/audit_layout.py`.

## The two stamps

`.stamp` is the signature device, and **there are two of them, saying different things.**
They were one until session 30, and the single stamp had gone quietly wrong.

- **The hero stamps the claim**: `RECONCILED ±$2 / 11 OF 11 REAL BILLS`. That is what earns
  the right to the dollar figures further down the page.
- **The pricing section stamps the disclaimer**: `NOT A BILL / NO AMOUNT DUE`, in
  `#priceOut`, beside the verdict. `.stamp.due` leans the other way so the two read as a
  pair of impressions rather than a repeated motif.

**Why it moved.** The stamp was authored in session 12 to say the thing the tool then did:
it priced nothing. Session 28 made it price, and the stamp was left sitting directly under
hero copy that promises to re-bill a year under every rate plan — still literally true, but
reading as a retraction of the sentence above it, and 2,000px from the only figures it
qualifies. A disclaimer belongs where the money is. **Cameron chose this split explicitly**;
do not re-merge them without asking.

No test pins `.stamp`. That is not permission to treat it as decoration.

## The tokens

Defined once in `docs/site.css`, and only there.

```
--paper --paper-2                   the manila grounds
--band                              the sulphur block behind the 4-9 p.m. hours
--ink --ink-2 --ink-3               text, strongest to faintest
--rule --rule-2                     hairlines
--ox  (= --accent)                  oxblood: accent TEXT, peak bars, rules, the stamps
--sul                               sulphur: a FILL ONLY, never text (1.89:1 on paper)
--mark                              non-highlighted chart bars — a data colour
--display --sans --mono             Archivo (wdth axis), Archivo, Space Mono
```

**The hard colour rule: `--sul` is a fill, `--ox` is the ink.** Sulphur sits at 1.89:1 on
paper and must never carry text. Accent text is always `--ox`.

**Type.** `Archivo` is variable on weight *and width* (62–125%), so one file gives both
voices: `font-stretch:125%` + uppercase is the display voice (`.display`), normal width is
body. `Space Mono` carries every number, label, stamp and axis — the ledger voice. Two
families, both doing a specific job; do not add a third.

## The theme contract

Three states, and all three must be written:

```css
:root { /* complete light palette — every token defined here */ }
@media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){ /* dark overrides */ } }
:root[data-theme="dark"]{ /* the same dark overrides again */ }
```

A token defined **only** inside a media query or `[data-theme]` block is a bug: the toggle
breaks in one direction. `body` must always paint an explicit `background:var(--ground)`.

## Contrast — compute it, do not retype it

```bash
PYTHONPATH=src python scripts/contrast_matrix.py --markdown
```

That script reads the tokens **out of `site.css`'s own `:root` blocks**, so the numbers
cannot drift from the palette the way a hand-maintained table does. Text needs 4.5; chart
bars are graphics and need 3.0. Run it after any palette change and paste the result here.

Current output (2026-09-20, palette unchanged since session 12):

| pair | light | dark | needs | what it is |
|---|---|---|---|---|
| `--ink` on `--paper` | 14.21 | 15.18 | 4.5 | body text |
| `--ink` on `--paper-2` | 12.66 | 14.06 | 4.5 | body text on a plate |
| `--ink-2` on `--paper` | 7.16 | 8.91 | 4.5 | secondary text |
| `--ink-2` on `--paper-2` | 6.38 | 8.25 | 4.5 | secondary text on a plate |
| `--ink-3` on `--paper` | 5.07 | 4.94 | 4.5 | rail, tags, axis labels |
| `--ink-3` on `--paper-2` | 4.52 | 4.58 | 4.5 | rail, tags, axis labels on a plate |
| `--ox` on `--paper` | 5.60 | 4.88 | 4.5 | accent text, links, the stamps |
| `--ox` on `--paper-2` | 4.99 | 4.52 | 4.5 | accent text on a plate |
| `--mark` on `--paper` | 3.39 | 3.25 | 3.0 | chart bars (graphic) |
| `--mark` on `--paper-2` | 3.02 | 3.01 | 3.0 | chart bars on a plate, ranking bars (graphic) |
| `--ox` on `--band` | 4.58 | 3.62 | 3.0 | peak bars on the sulphur band (graphic) |
| `--ink` on `--band` | 11.62 | 11.26 | 4.5 | the current plan's name, highlighted |
| `--ink-2` on `--band` | 5.86 | 6.61 | 4.5 | the conditional-plan note on that row |
| `--sul` on `--paper` | **1.89 — FILL ONLY** | 11.29 | 4.5 | never text |

⚠ **A fill's own edge is a separate number from the text on it.** `--band` against the plate
is **1.09 light / 1.25 dark**: the sulphur highlight reads instantly in light mode because
the *hue* shift is large, but luminance is what survives dark mode and greyscale, and in dark
the fill all but disappears. That is why the current-plan highlight in `#planTable` carries a
2px `--ink-2` edge (6.38 / 8.25) — the edge is the part of the marker that is actually
visible. Check the fill *and* its boundary whenever a fill means something.

## Contracts a redesign must not break

These are enforced by CI, not by intent. Breaking one turns a job red.

1. **`tools/test_tool_render.mjs` pins the DOM.** It renders the page under jsdom and asserts
   on: `#results` and `#status` hidden on load; `#demoBanner` hidden for a real file and
   shown in demo mode, its text naming whose data it is AND that it is not the reader's (the
   assertion matches the guarantee, not one phrasing); `#stats`; `#findings .finding` with
   the first one's `h4` containing "peak hours"; **exactly 25 `#hourChart rect`** (24 bars +
   1 peak-window shading), of which **exactly 5 carry `fill="var(--accent)"`**; 24
   `#hourChart title`; one `#monthChart rect` per month; `#fileTable` containing the utility,
   an interval, a date and "Yes"; the string **"$2 per month" must appear inside `#results`**;
   the accessibility contract — `#announcer` present, un-hidden and empty on load with
   `role="status"`/`aria-live="polite"`, the arrival of results announced there, and focus
   moved into `#results` (`tabindex="-1"`); **and the whole pricing section** — an available
   recommendation shows only `#priceOut`, one `tr.win`, a dollar-denominated `#planTable`
   with a caption and `th[scope]`, `#flipNote`, `#assumeList`; a refusal shows only
   `#priceGate`, names its blocker code, and carries **no `$<digit>` anywhere the engine
   wrote**. Adding any decorative `<rect>` to either chart breaks the count — use `<path>`,
   `<line>` or CSS instead. Restructure the markup and you must update this test in the
   **same commit**, deliberately.

2. **Where dollars may and may not appear.** The old rule here — "no dollar figures anywhere
   the page computes; the tool prices nothing by design" — **is wrong and was wrong from
   session 28.** Replace it with the actual boundary, which has three parts:
   - **The load-shape half never prices.** `tests/report/test_inspect.py` guards the
     *inspection layer only*: `test_the_inspection_carries_no_dollar_figures` asserts that
     the `Inspection` pydantic model has no money-shaped **field name** and that its JSON
     contains no `$`; `test_findings_never_quote_a_price` asserts no `$`, `¢` or `/kWh` in
     findings **title or detail**. Neither says anything about the page. The render test
     covers the page half, scanning `#stats`, `#findings`, `#hourChart`, `#monthChart`,
     `#fileTable` and `#warnBox` for `$<digit>`. That half runs for **every** visitor,
     including the ones the engine may not price, so a dollar reaching it escapes the gate.
   - **Section R2 is where money lives**, and only when `src/report/recommend.py` has said
     so. `#priceOut` is dollar-denominated on purpose.
   - **A refusal stays clean.** `#priceGateText` + `#priceGateList` must contain no `$<digit>`
     — the surrounding prose may still quote `±$2`, because that is the rule being read to
     the reader, not a price computed for them.

   The real limit on pricing is **not** a blanket refusal: it is that the committed PG&E
   specs describe **one household** (territory T, all-electric, 3CE, PCIA 2018). That scope
   is *derived* from the spec files by `authored_scope()`, and everyone outside it is refused
   by one of four named codes — `UTILITY_NOT_RECONCILED`, `TERRITORY_NOT_AUTHORED`,
   `HEAT_SOURCE_NOT_AUTHORED`, `SUPPLIER_NOT_AUTHORED`. **The refusal is a designed state,
   not an error state.** Give it the same care as the answer.

3. **`docs/engine.js` is GENERATED** from `src/` by `scripts/build_web_engine.py`, and
   `tests/report/test_web_engine.py` fails if it goes stale. Never hand-edit it. **Pure UI
   work does not touch it** — if a UI-only change makes that test fail, someone else has
   edited `src/`, and the failure is theirs. ⚠ `docs/case-study.json` is generated from
   gitignored `data/` and records the bundle's digest, so **whoever moves the bundle must
   regenerate both**, and only someone with `data/` can.

4. **`tools/test_engine_wasm.mjs` checks dollar parity with CPython to the cent.** UI work
   should never move it; if it does, stop.

5. **Findings prose is generated in Python** (`src/report/inspect.py`), not in the page, so
   that the words a visitor reads are tested. Do not move copy into the HTML to reword it.

## Charts

Two hand-rolled inline SVGs, no chart library: `#hourChart` (`viewBox="0 0 760 300"`) and
`#monthChart` (`viewBox="0 0 760 240"`), built with a small `createElementNS` helper. Before
touching either, **load the `dataviz` skill** — and note that where it and this file
disagree, this file wins: the square bar ends and the absent legend are the house style, not
oversights.

Conventions to preserve:
- **Square bar ends.** No `rx`. Printed, not drawn.
- **`--ox` means one thing: the expensive hours.** Peak bars are `--accent` (= `--ox`) on a
  `--band` block; every other bar in every chart is `--mark`. Month bars are deliberately
  `--mark`, not oxblood — reusing the accent for "just data" would drain it of meaning. This
  is a rule about **chart data colours**: `--ox` stays the document accent for links, rail
  numbers, `h3`, the stamps and pass marks, which is how `site.css` itself uses it. The
  methodology page's eleven reconciliation-error bars were oxblood until session 20 and are
  now `--mark` (3.02 light / 3.01 dark on the plate).
- One series, so no legend; the plate header names it.
- Axis and label text in `--ink-3` or `--ink`, never `--sul`.
- Exactly one direct label (the busiest hour); never a number on every bar.
- Per-bar `<title>` for pointer tooltips, plus `#hourTable` / `#monthTable` in text, because
  `role="img"` hides those titles from screen readers.
- **Leave the top margin alone.** `T = 64` on the hour chart exists so the band caption and
  the direct label cannot collide when the busiest hour falls inside the band — which is the
  common case. This has now been broken and re-fixed twice; it is not spare whitespace.
- ⚠ **`BAND_LIFT` and `LABEL_LIFT` in `hourChart()` are a pair.** `T` kept the caption and
  the direct label apart but said nothing about the band's own overhang above the plot: with
  the band lifted 10px and the label at −10, the label's baseline landed exactly on the
  band's top edge and the words sat half on sulphur, half on paper. 6 and 16 put 10px of
  paper between type and fill. Change one, recompute the other, and look at the screenshot.
- **`monthChart` sets its ticks level, and that is deliberate.** They were rotated −42° and
  ran into the axis caption. Thirteen months across 698px leaves ~54px a tick and `"Jul 25"`
  needs ~33px, so `monthLabel()` compresses the engine's `"2025-07"` for the **axis only** —
  the `<title>` and `#monthTable` keep the engine's own string, because the table is the
  text equivalent and should carry the value verbatim. A rotated axis label is a workaround
  for a width problem this chart does not have.

## The ranking is a chart too

`#planTable` in `#priceOut` is the product's actual answer, and it was six mono figures in a
column until session 30. Two rules now hold there:

- **The winner outranks the status quo.** The loudest row used to be the reader's *current*
  plan (a full-width sulphur fill) while the *recommended* plan was merely bold — a table
  that shouted the status quo on a page whose whole job is to rank against it. The winner
  carries **oxblood rules top and bottom** (the document accent used as a *rule*, which is
  how `site.css` already uses `--ox` for links, rail numbers and the stamps); the current
  plan keeps sulphur as a **highlighter on its name**, not a fill across the row.
- **`.mbar` encodes the gap to the cheapest plan**, zero-based, so the winner's bar is
  correctly empty, growing right-to-left under the right-aligned figure. It carries a `.vh`
  text equivalent because that number is printed nowhere else. ⚠ It is `--mark` and **never**
  `--ox`: painting the *cheapest* plan oxblood would invert the one chart rule the site has.

## Verify

```bash
conda activate energy-advisor
npm install --prefix tools && node tools/test_tool_render.mjs && node tools/test_engine_wasm.mjs
PYTHONPATH=src python -m pytest -q     # includes the inspection no-dollars and bundle gates
PYTHONPATH=src python scripts/contrast_matrix.py --markdown
```

Both browser checks run as a separate CI job on every push.

**Then look at it.** jsdom does no layout, so those tests cannot see a label collision, a
clipped caption or an unreadable bar:

```bash
pip install playwright && python -m playwright install chromium   # optional local extras,
PYTHONPATH=src python scripts/screenshot_site.py                  # deliberately not in CI
PYTHONPATH=src python scripts/audit_layout.py
```

`screenshot_site.py` shoots all four pages in both themes plus the report, priced and
refused states and each chart, driving the page's own `__renderInspection` /
`__renderRecommendation` / `__renderGate` hooks so no Pyodide boot is needed. It earned its
place immediately — it caught the hour chart's band caption colliding with its direct label,
and non-peak bars sitting at 1.5:1 in both themes — and it has now caught three more: the
direct label sitting on the band's edge, the month ticks running into the axis caption, and a
4,700px focus ring around `#results`.

`audit_layout.py` is the part eyes are bad at: reflow at 1280 / 640 / 320 on every page,
heading-level skips over the **accessibility tree** (so the tool page is walked twice, once
with `#results` hidden as a visitor first meets it), and a missing `scope` on any `th`. It
found two live defects the moment it existed. **Contrast is arithmetic and belongs in a
script; collisions and clipping need eyes on a real render; reflow and heading order need a
real browser and a walk.**
