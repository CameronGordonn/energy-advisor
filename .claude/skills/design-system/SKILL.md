---
name: design-system
description: The visual system for this repo's two published pages (docs/index.html, docs/methodology.html) — design tokens, theme contract, typography, and the DOM/test contracts a redesign must not break. Load before changing any CSS, markup, or chart rendering in docs/, and before adding a page.
---

# Design system — energy-advisor site

Four published pages, served from `docs/` on GitHub Pages:

- **`docs/index.html`** — the tool. Drop a usage CSV, get load-shape analysis. Runs the real
  Python parsers under Pyodide.
- **`docs/methodology.html`** — the M4 writeup.
- **`docs/privacy.html`**, **`docs/terms.html`** — the legal pages, prose only.

**`docs/site.css` is the shared stylesheet** and the single source of truth for the palette.
`index.html`, `privacy.html` and `terms.html` link it and keep only page-specific rules
inline. ⚠ `methodology.html` does NOT yet link it — it still carries its own copy of the
token block (values are now in sync, but it will drift again). Migrating it is the next
tidy-up, and the only reason it was not done alongside the others is that its inline nav and
footer rules would need reconciling with the shared ones first.

Pages is the canonical home. `docs/index.html` carries its own `<!doctype html>`, `<html
lang>`, and `<head>`, so it is **not** an Artifact — do not route it through the Artifact
publisher without stripping the wrapper first, and prefer not to at all.

## The tokens

The palette lives in **`docs/site.css`**. `methodology.html` still repeats it inline; those
values are in sync today and must be kept so until it is migrated.

```
--ground --surface --surface-2      surfaces, lightest to most recessed
--ink --ink-2 --ink-3               text, strongest to faintest
--rule --rule-2                     hairlines and borders
--mark-muted                        non-highlighted CHART BARS — a data colour, not a
                                    hairline; 3:1 against --surface in both themes
--accent --accent-soft              the green; soft is its tinted background
--warn --warn-soft                  the orange, for caveats and gates
--serif --sans --mono               Newsreader / Public Sans / IBM Plex Mono
--col                               methodology.html only: 40rem measure
```

**Rules**

1. **Never hardcode a colour.** Every colour in either page resolves to a token. A raw hex
   outside the `:root` blocks is a bug.
2. **Add tokens to `site.css`, never to a page.** The one exception is
   `methodology.html`, which still has its own copy — change both until it is migrated.
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

## Contrast — all tokens pass; keep it that way

Measured against the current tokens (AA needs 4.5 for body text, 3.0 for large text and UI):

| token | light on ground / surface / surface-2 | dark on ground / surface / surface-2 |
|---|---|---|
| `--ink` | 15.75 / 16.97 / 14.72 | 15.05 / 13.85 / 12.63 |
| `--ink-2` | 6.38 / 6.88 / 5.97 | 7.61 / 7.00 / 6.38 |
| `--ink-3` | 4.83 / 5.20 / 4.51 | 5.37 / 4.94 / 4.50 |
| `--accent` | 4.93 / 5.31 / 4.61 | 5.70 / 5.24 / 4.78 |
| `--warn` | 4.85 / 5.22 / 4.53 | 5.68 / 5.23 / 4.77 |

Every token clears AA for body text on every surface in both themes. **Recompute after any
palette change** — relative luminance is arithmetic, not judgement.

**History, so the fix is not quietly undone:** `--ink-3` was `#7E8477` light / `#7B8172` dark
and failed on every light surface (3.22-3.71) while carrying eight real usages, including the
**SVG axis labels at `font-size:10`**. It is now `#676C61` / `#888E7F`. `--accent` was
`#0B7D52` (4.32 on `--surface-2`) and is now `#0B784F`. Both were solved for, not guessed.

`docs/methodology.html` has since been brought into line with these values, though it still
holds its own copy of them rather than linking `site.css`.

## Contracts a redesign must not break

These are enforced by CI, not by intent. Breaking them turns a job red.

1. **`tools/test_tool_render.mjs` pins the DOM.** It renders the page under jsdom and asserts
   on: `#results` and `#status` hidden on load; `#demoBanner` hidden for a real file and
   shown in demo mode with text matching `/demonstration file/i`; `#stats`; `#findings
   .finding` with the first one's `h4` containing "peak hours"; **exactly 25 `#hourChart
   rect`** (24 bars + 1 peak-window shading), of which **exactly 5 carry
   `fill="var(--accent)"`**; 24 `#hourChart title`; one `#monthChart rect` per month;
   `#fileTable` containing the utility, an interval, a date and "Yes"; and the string
   **"$2 per month" must appear inside `#results`**. Adding any decorative `<rect>` to either
   chart breaks the count — use `<path>`, `<line>` or CSS instead. Restructure the markup and
   you must update this test in the **same commit**, deliberately.
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
touching either, **load the `dataviz` skill** for palette, axis and mark guidance.

Conventions already applied, worth preserving: one series so no legend (the heading names
it); recessive gridlines; axis text in `--ink-2`, never `--ink-3`; `rx:3` bar ends; exactly
one direct label (the busiest hour) rather than a number on every bar; per-bar `<title>` for
pointer tooltips; and text tables (`#hourTable`, `#monthTable`) carrying the same numbers,
because `role="img"` hides those `<title>`s from screen readers.

The 4–9 p.m. peak band is highlighted; it is the on-peak window of both PG&E E-TOU-C and
SDG&E TOU-DR1, so it is a tariff fact, not a styling choice. The caption must keep naming it,
so the highlight is never colour-alone.

## Verify

```bash
conda activate energy-advisor
npm install --prefix tools && node tools/test_tool_render.mjs && node tools/test_engine_wasm.mjs
pytest -q                       # includes the no-dollars and bundle-staleness gates
```

Both browser checks run as a separate CI job on every push.

**Then look at it.** jsdom does no layout, so those tests cannot see a label collision, a
clipped caption or an unreadable bar:

```bash
pip install playwright && python -m playwright install chromium   # optional local extra,
PYTHONPATH=src python scripts/screenshot_site.py                  # deliberately not in CI
```

It shoots all four pages in both themes plus the report state and each chart, driving the
page's own `__renderInspection` hook so no Pyodide boot is needed. It earned its place
immediately: it caught the hour chart's band caption colliding with its direct label, and
non-peak bars sitting at 1.5:1 against the panel in both themes. Contrast is arithmetic and
belongs in a script; **collisions and clipping need eyes on a real render.**
