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
for `.vh` (visually hidden), `.gate`, `.row`, `.plate`, `details.fine`, buttons and the
`.doc` prose chrome. **All four pages link it** and keep only page-specific rules inline. No
page defines a palette token of its own; if you find one, that is the bug.

Pages is the canonical home. `docs/index.html` carries its own `<!doctype html>`, `<html
lang>`, and `<head>`, so it is **not** an Artifact — do not route it through the Artifact
publisher without stripping the wrapper first, and prefer not to at all.

## The idea (session 32 — replaces the session-12 "tariff sheet")

**Get out of the way of the numbers.** White page, system fonts, one centred column (52rem),
sentence-case headings, a little border-radius on boxes and buttons. The content — when you
use power, what each plan costs, what would overturn the answer — is the design.

**Why it changed.** Sessions 12–31 built the site as "the document it is about": manila
paper, oxblood/sulphur two-colour print, 125%-width uppercase Archivo headlines, Space Mono
on every label, a left rail of numbered margin notes, zero radius, and two rotated rubber
stamps. Cameron (2026-10-23): it "way overdoes it, isn't simple, and takes away from the
meaningful and insightful content by trying to look super bespoke." All of it was removed.
**Do not reintroduce bespoke ornament** — stamps, margin rails, display/mono "voices",
uppercase tracked labels, "Fig. 1 / Schedule A / Form A" numbering. If something needs
emphasis, use size, weight and position.

What became of the old devices:
- **The two stamps are now plain sentences in the same places.** The hero's claim is
  `.proof` under the lede ("The bill engine reproduces 11 of 11 real PG&E bills to within
  ±$2"). The pricing disclaimer is `.notabill` under the verdict ("A modelled estimate … not
  a bill, and no amount is due"). Still two, still where session 30 put them.
- **Rails are gone from the markup** on all four pages; `.row` is a plain section with a
  hairline between sections.
- **Self-hosted fonts are gone** (`docs/fonts/`, `fonts.css` deleted). The privacy page was
  updated to say no web fonts are loaded at all.

**Reflow is still part of the system.** `.row>*{min-width:0}` stays; anything that must
scroll horizontally does so inside its own `overflow-x:auto` box (which needs
`position:relative` if it holds a `.vh` caption). `body` sets `overflow-wrap:break-word` so a
long URL in prose cannot widen the page. All four pages are checked at 1280 / 640 / 320 CSS px
by `scripts/audit_layout.py`. `#planTable` keeps figures on one line but lets its header wrap
below 560px, and tightens padding below 480px — at 320px the page otherwise scrolls sideways.

## The tokens

Defined once in `docs/site.css`, and only there. **The names are legacy** (`--paper`, `--ox`,
`--band`) and are kept because the chart code, the render test (`var(--accent)`) and
`scripts/contrast_matrix.py` address them by name.

```
--paper --paper-2        page background; the panel/tint background
--band                   the light tint behind the 4-9 p.m. hours in the hour chart
--ink --ink-2 --ink-3    text, strongest to faintest
--rule --rule-2          hairlines; input/button borders
--ox (= --accent)        the warm accent: the expensive hours, and nothing else
--mark                   every other chart bar, and the ranking bars
--link                   links and focus rings
--sans                   system-ui stack (--display aliases it)
--mono                   ui-monospace — code only
```

**The colour rule: `--accent` means the expensive hours.** It paints the five peak bars, the
peak-window caption and the "Worth knowing" finding tag. Links are `--link`, the saving
figure is `--ink`, the winner row is a neutral tint. Everything else is greyscale.

**Type.** One family, the platform's own. Numbers use `font-variant-numeric:tabular-nums`
(set on `body`) rather than a monospace face. Chart text is `var(--sans)`.

## The theme contract

Three states, and all three must be written:

```css
:root { /* complete light palette — every token defined here */ }
@media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){ /* dark overrides */ } }
:root[data-theme="dark"]{ /* the same dark overrides again */ }
```

A token defined **only** inside a media query or `[data-theme]` block is a bug: the toggle
breaks in one direction. `body` must always paint an explicit `background:var(--paper)`.

## Contrast — compute it, do not retype it

```bash
PYTHONPATH=src python scripts/contrast_matrix.py --markdown
```

That script reads the tokens **out of `site.css`'s own `:root` blocks**. Text needs 4.5;
chart bars are graphics and need 3.0. Run it after any palette change and paste the result.

Current output (2026-10-23, session 32 palette):

| pair | light | dark | needs | what it is |
|---|---|---|---|---|
| `--ink` on `--paper` | 17.22 | 15.45 | 4.5 | body text |
| `--ink` on `--paper-2` | 15.78 | 13.96 | 4.5 | body text on a panel |
| `--ink-2` on `--paper` | 8.86 | 9.70 | 4.5 | secondary text |
| `--ink-2` on `--paper-2` | 8.12 | 8.77 | 4.5 | secondary text on a panel |
| `--ink-3` on `--paper` | 5.57 | 6.21 | 4.5 | tags, hints, axis labels |
| `--ink-3` on `--paper-2` | 5.10 | 5.62 | 4.5 | tags, hints, axis labels on a panel |
| `--link` on `--paper` | 6.52 | 8.11 | 4.5 | links |
| `--link` on `--paper-2` | 5.97 | 7.34 | 4.5 | links on a panel |
| `--ox` on `--paper` | 5.56 | 7.25 | 4.5 | peak-window caption, "worth knowing" tags |
| `--ox` on `--paper-2` | 5.09 | 6.56 | 4.5 | accent text on a panel |
| `--mark` on `--paper` | 3.91 | 3.95 | 3.0 | chart bars (graphic) |
| `--mark` on `--paper-2` | 3.59 | 3.57 | 3.0 | ranking bars on a panel (graphic) |
| `--ox` on `--band` | 4.78 | 5.77 | 3.0 | peak bars on the peak-window band (graphic) |

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
disagree, this file wins: the absent legend is the house style, not an oversight.

Conventions to preserve:
- **`--accent` means one thing: the expensive hours.** Peak bars are `--accent` (= `--ox`)
  on a `--band` block; every other bar in every chart is `--mark`, including the month bars
  and the methodology page's reconciliation-error bars.
- Chart text is `var(--sans)`, sentence case, no letter-spacing ("4–9 p.m. · priciest
  hours", "Busiest: 6 p.m.", "Hour of day (local time)").
- One series, so no legend; the plate header names it.
- Axis and label text in `--ink-3` or `--ink`.
- Exactly one direct label (the busiest hour); never a number on every bar.
- Per-bar `<title>` for pointer tooltips, plus `#hourTable` / `#monthTable` in text, because
  `role="img"` hides those titles from screen readers.
- **Leave the top margin alone.** `T = 64` on the hour chart exists so the band caption and
  the direct label cannot collide when the busiest hour falls inside the band — which is the
  common case. This has now been broken and re-fixed twice; it is not spare whitespace.
- ⚠ **`BAND_LIFT` and `LABEL_LIFT` in `hourChart()` are a pair.** `T` kept the caption and
  the direct label apart but said nothing about the band's own overhang above the plot: with
  the band lifted 10px and the label at −10, the label's baseline landed exactly on the
  band's top edge and the words sat half on the band, half off it. 6 and 16 put 10px of
  paper between type and fill. Change one, recompute the other, and look at the screenshot.
- **`monthChart` sets its ticks level, and that is deliberate.** They were rotated −42° and
  ran into the axis caption. Thirteen months across 698px leaves ~54px a tick and `"Jul 25"`
  needs ~33px, so `monthLabel()` compresses the engine's `"2025-07"` for the **axis only** —
  the `<title>` and `#monthTable` keep the engine's own string, because the table is the
  text equivalent and should carry the value verbatim. A rotated axis label is a workaround
  for a width problem this chart does not have.

## Usability pass (session 31) — what was added, and why it is shaped this way

- **The intake is on the first screen** at 1280x800. Since session 32 the h1 itself asks
  what the tool is for ("Which electricity plan is cheapest for the way you actually use
  power?").
- **The facts form names the line on the bill for every answer** (`.fields .hint`, tied to
  its select by `aria-describedby`), quoting the PG&E statement's own words — *Details of
  PG&E Electric Delivery Charges*, *Baseline Territory*, *Heat Source*, *Enrolled
  Programs*, *Rate Schedule* — checked against a real statement, not recalled. Option
  values are unchanged; only their labels became plain.
- **Every plan says what it is** (`.pdesc` under the code, and in the plan dropdown), from
  `PLAN_DESC` in the page: the windows are the specs' own. A code is not a description.
- **The saving is a figure** (`.verdict .save`), in `--ink` — never `--ox`, which means the
  expensive hours. It is the winner's own `delta_vs_current` over the days modelled, never
  annualised.
- **No dead ends.** `#toPrice` links from the report head to the prices; `#again` returns to
  the drop zone; `#redoGate` / `#redoOut` reopen the form. A refusal used to end the page
  until reload. Redo is hidden for the utility-level gate (no answers were asked) and in
  the worked example (no Pyodide, no form).
- **A refusal leads with a plain sentence.** `Blocker.summary` is written in Python
  (`src/report/recommend.py`) and tested for no `$<digit>` and no engine vocabulary
  ("spec", "layer", "authored"…); the technical `detail` folds under it in `details.why`.
  The page never invents refusal copy — contract 5's rule, extended to refusals.
- **The masthead is no longer sticky** (session 32), so `html{scroll-padding-top}` is a
  token 1rem. If it is ever made sticky again, scroll padding must cover its height.

## The ranking is a chart too

`#planTable` in `#priceOut` is the product's actual answer, and it was six mono figures in a
column until session 30. Two rules now hold there:

- **The winner outranks the status quo.** The winner row is a bold, tinted (`--paper-2`)
  band; the current plan's name is semibold and the last column says "your plan" in words.
  Never make the current plan the loudest row — the page's job is to rank against it.
- **`.mbar` encodes the gap to the cheapest plan**, zero-based, so the winner's bar is
  correctly empty, growing right-to-left under the right-aligned figure. It carries a `.vh`
  text equivalent because that number is printed nowhere else. ⚠ It is `--mark` and **never**
  `--accent`: painting the *cheapest* plan in the expensive-hours colour inverts the rule.

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
