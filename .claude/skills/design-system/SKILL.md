---
name: design-system
description: The visual system for this repo's two published pages (docs/index.html, docs/methodology.html) — design tokens, theme contract, typography, and the DOM/test contracts a redesign must not break. Load before changing any CSS, markup, or chart rendering in docs/, and before adding a page.
---

# Design system — energy-advisor site

Two published pages, served from `docs/` on GitHub Pages:

- **`docs/index.html`** — the tool. Drop a Green Button CSV, get load-shape analysis. Runs
  the real Python parsers under Pyodide.
- **`docs/methodology.html`** — the M4 writeup.

Pages is the canonical home. `docs/index.html` carries its own `<!doctype html>`, `<html
lang>`, and `<head>`, so it is **not** an Artifact — do not route it through the Artifact
publisher without stripping the wrapper first, and prefer not to at all.

## The tokens

Both pages open with a **byte-identical** `:root` token block. Treat it as one system that
happens to be stored twice.

```
--ground --surface --surface-2      surfaces, lightest to most recessed
--ink --ink-2 --ink-3               text, strongest to faintest
--rule --rule-2                     hairlines and borders
--accent --accent-soft              the green; soft is its tinted background
--warn --warn-soft                  the orange, for caveats and gates
--serif --sans --mono               Newsreader / Public Sans / IBM Plex Mono
--col                               methodology.html only: 40rem measure
```

**Rules**

1. **Never hardcode a colour.** Every colour in either page resolves to a token. A raw hex
   outside the `:root` blocks is a bug.
2. **A token added to one page must be added to the other**, or extracted to a shared
   stylesheet first. They are duplicated verbatim today; that is the single biggest
   maintenance hazard on the site and the most defensible thing to fix in a redesign.
3. **Serif for display and prose, sans for UI, mono for eyebrows and labels.** `h1`, `.sub`,
   `#drop .big` and section headings are `--serif`; nav brand and small caps labels are
   `--mono` with `letter-spacing:.11em` and `text-transform:uppercase`.
4. `.wrap` is `max-width:60rem`. Long-form prose on methodology.html uses `--col` (40rem)
   for measure. Do not widen prose past ~75 characters.
5. Keep the existing font fallback stacks. Any webfont must degrade to them.

## The theme contract

Three states, and all three must be written:

```css
:root { /* complete light palette — every token defined here */ }
@media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){ /* dark overrides */ } }
:root[data-theme="dark"]{ /* the same dark overrides again */ }
```

A token defined **only** inside a media query or `[data-theme]` block is a bug: the toggle
breaks in one direction. `body` must always paint an explicit `background:var(--ground)`.

## Contrast — a known defect, do not propagate it

Measured against the current tokens (AA needs 4.5 for body text, 3.0 for large text and UI):

| token | light on ground / surface / surface-2 | dark on ground / surface / surface-2 |
|---|---|---|
| `--ink` | 15.75 / 16.97 / 14.72 | 15.05 / 13.85 / 12.63 |
| `--ink-2` | 6.38 / 6.88 / 5.97 | 7.61 / 7.00 / 6.38 |
| `--ink-3` | **3.45 / 3.71 / 3.22** | 4.51 / **4.15 / 3.78** |
| `--accent` | 4.62 / 4.98 / **4.32** | 5.70 / 5.24 / 4.78 |
| `--warn` | 4.85 / 5.22 / 4.53 | 5.68 / 5.23 / 4.77 |

**`--ink-3` fails AA for body text on every light background**, and it is used in eight
places for real copy — `#drop .small`, the privacy line, `.cap` captions, table headers, and
the **SVG axis labels at `font-size:10`** on both charts. Darken the token rather than
restricting it; one line in each page's `:root` lifts all eight usages. `--accent` on `--surface-2` in light is large-text-only. Fixing `--ink-3` is a
one-line change to two files and is worth doing in any redesign.

## Contracts a redesign must not break

These are enforced by CI, not by intent. Breaking them turns a job red.

1. **`tools/test_tool_render.mjs` pins the DOM.** It renders the page under jsdom and asserts
   on: `#results` and `#status` hidden on load; `#demoBanner` hidden for a real file and
   shown in demo mode with text matching `/demonstration file/i`; `#stats`; `#findings
   .finding` with the first one's `h4` containing "peak hours"; **24 `#hourChart rect` and 24
   `#hourChart title`**; `#monthChart rect`; `#fileTable`. Restructure the markup and you
   must update this test in the **same commit**, deliberately.
2. **No dollar figures anywhere the page computes.** The tool prices nothing by design — the
   reconciliation gate is met for PG&E but not SDG&E, so shipping dollars would violate
   invariant 1. Enforced on both sides: `tests/report/test_inspect.py` forbids money-shaped
   field names and any `$`, `¢` or `/kWh` in findings text, and the render test scans
   computed regions. Do not add a currency glyph to a computed region, even decoratively.
3. **`docs/engine.js` is GENERATED** from `src/` by `scripts/build_web_engine.py`, and
   `tests/report/test_web_engine.py` fails if it goes stale. Never hand-edit it. Pure UI work
   does not touch it; if you change `src/greenbutton/` or `src/report/inspect.py`, rebuild.
4. **Findings prose is generated in Python** (`src/report/inspect.py`), not in the page, so
   that the words a visitor reads are tested. Do not move copy into the HTML to reword it.

## Charts

Two hand-rolled inline SVGs, no chart library: `#hourChart` (`viewBox="0 0 760 300"`) and
`#monthChart` (`viewBox="0 0 760 240"`), built with a small `createElementNS` helper. Before
touching either, **load the `dataviz` skill** for palette, axis and mark guidance. The 4–9
p.m. peak band is highlighted; it is the on-peak window of both PG&E E-TOU-C and SDG&E
TOU-DR1, so it is a tariff fact, not a styling choice, and the caption must keep saying so.

## Verify

```bash
conda activate energy-advisor
npm install --prefix tools && node tools/test_tool_render.mjs && node tools/test_engine_wasm.mjs
pytest -q                       # includes the no-dollars and bundle-staleness gates
```

Both browser checks run as a separate CI job on every push.
