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

## The idea

The product exists to reproduce a utility bill to within $2, so the site is built as **the
document it is about**: a tariff sheet. Two-colour offset print on manila. Rules and ledger
columns do the structural work; **there is no border-radius anywhere on the site**, and
adding one is a regression, not a refinement. A left rail of mono margin-annotations
(`.rail`, section numbers `00`-`05`) carries each block, which is what stops the page being
a stack of centred cards.

The signature device is the **stamp** (`.stamp`): `NOT A BILL / NO AMOUNT DUE`. The tool
deliberately prices nothing, and a document says that the way a document would. Keep it.

## The tokens

Defined once in `docs/site.css`. `methodology.html` still holds its own copy of the values
(in sync; migrating it needs its nav/footer rules reconciled with the shared chrome first).

```
--paper --paper-2                   the manila grounds
--band                              the sulphur block behind the 4-9 p.m. hours
--ink --ink-2 --ink-3               text, strongest to faintest
--rule --rule-2                     hairlines
--ox  (= --accent)                  oxblood: accent TEXT, peak bars, rules, the stamp
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

## Contrast — all tokens pass; keep it that way

Solved for, not eyeballed. Text needs 4.5; chart bars are graphics and need 3.0.

| token | light: paper / paper-2 | dark: paper / paper-2 |
|---|---|---|
| `--ink` | 14.21 / 12.66 | 15.18 / 14.06 |
| `--ink-2` | 7.16 / 6.38 | 8.91 / 8.25 |
| `--ink-3` | 5.07 / 4.52 | 4.94 / 4.58 |
| `--ox` | 5.60 / 4.99 | 4.88 / 4.52 |
| `--mark` (bars) | 3.39 / 3.02 | 3.25 / 3.01 |
| `--sul` | **1.89 — FILL ONLY** | 11.29 |

Peak bars sit on the sulphur band, so that pair is checked too: `--ox` on `--band` is
**4.58** light and **3.62** dark, both clear of the 3.0 graphics threshold.

**Recompute after any palette change** — relative luminance is arithmetic, not judgement.

## Contracts a redesign must not break

These are enforced by CI, not by intent. Breaking them turns a job red.

1. **`tools/test_tool_render.mjs` pins the DOM.** It renders the page under jsdom and asserts
   on: `#results` and `#status` hidden on load; `#demoBanner` hidden for a real file and
   shown in demo mode, its text naming the data as fabricated AND saying it is not real
   (the assertion matches the guarantee, not one phrasing); `#stats`; `#findings
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
touching either, **load the `dataviz` skill**.

Conventions to preserve:
- **Square bar ends.** No `rx`. Printed, not drawn.
- **`--ox` means one thing: the expensive hours.** Peak bars are `--accent` (= `--ox`) on a
  `--band` block; every other bar in both charts is `--mark`. Month bars are deliberately
  `--mark`, not oxblood — reusing the accent for "just data" would drain it of meaning.
- One series, so no legend; the plate header names it.
- Axis and label text in `--ink-3` or `--ink`, never `--sul`.
- Exactly one direct label (the busiest hour); never a number on every bar.
- Per-bar `<title>` for pointer tooltips, plus `#hourTable` / `#monthTable` in text, because
  `role="img"` hides those titles from screen readers.
- **Leave the top margin alone.** `T = 64` on the hour chart exists so the band caption and
  the direct label cannot collide when the busiest hour falls inside the band — which is the
  common case. This has now been broken and re-fixed twice; it is not spare whitespace.

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
