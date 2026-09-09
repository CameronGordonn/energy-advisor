---
name: accessibility-audit
description: Accessibility review for this repo's published pages (docs/index.html, docs/methodology.html) — what already holds and must not regress, the known open defects, and how to check. Load when auditing, redesigning, or adding UI to docs/, or when changing the SVG charts or the file-drop control.
---

# Accessibility audit — energy-advisor site

The audience is homeowners checking their own utility bills, not developers. A visitor who
cannot read the chart cannot use the tool at all, because the chart **is** the output.

Audit the two published pages: `docs/index.html` (the tool) and `docs/methodology.html`
(the writeup). Target WCAG 2.1 AA.

## Already true — verify these still hold, do not "fix" them

Checked against the current source. Regressions here are the likeliest damage from a
redesign, so re-check each after any markup or CSS change.

- **`:focus-visible{outline:2px solid var(--accent);outline-offset:2px}`** is defined
  globally. Every interactive control gets a visible focus ring. Do not remove it, and do
  not replace it with `outline:none` plus a colour change.
- **The drop zone is keyboard operable.** `#drop` is `tabindex="0" role="button"` with an
  `aria-label`, and it has a real `keydown` handler — it is not a mouse-only div.
- **Reduced motion is respected**: `@media (prefers-reduced-motion:reduce){.spin{animation:none}}`.
  Any new animation needs the same guard.
- **The peak window is not conveyed by colour alone.** The shaded 4–9 p.m. band is also
  stated in the caption text. Keep that sentence if you restyle the band.
- **Decorative glyphs are hidden**: the padlock carries `aria-hidden="true"`.
- **Both pages are theme-aware** in light, dark and system, so a forced-dark reader does not
  get an unstyled page.

## Open defects

### 1. Chart data is unreachable by screen reader — the significant one

`#hourChart` and `#monthChart` are `<svg role="img" aria-label="...">`. `role="img"` makes
the SVG an **atomic image**: its children are removed from the accessibility tree, so the 24
per-bar `<title>` elements are pointer tooltips only and are **never announced**. A screen
reader user hears one sentence and gets none of the 24 hourly values.

The `<title>` elements are load-bearing for tests (`tools/test_tool_render.mjs` asserts
exactly 24 of them), so **keep them** and add a text alternative alongside:

- preferred: render a visually-hidden `<table>` of the same 24 values next to each chart, or
  a `<details>` disclosure holding it — it reuses data the page already has; or
- extend the `aria-label` into a short summary naming the peak hour, the trough hour and the
  peak share, which `src/report/inspect.py` already computes.

Do not switch the SVG to `role="table"` or drop `role="img"` without re-running the render
test — the assertions are counted, not fuzzy.

### 2. `--ink-3` fails AA for body text

Measured contrast against the current tokens:

- light: **3.45** on `--ground`, **3.71** on `--surface`, **3.22** on `--surface-2`
- dark: 4.51 on `--ground`, **4.15** on `--surface`, **3.78** on `--surface-2`

AA body text needs **4.5**. `--ink-3` is not an incidental token — it is used in eight places
in `docs/index.html` for genuine copy: `#drop .small` (.88rem), the privacy line (.84rem),
`.cap` chart captions (.8rem), table header cells, and — worst — **the SVG axis labels on
both charts, at `font-size:10`** (`fill:var(--ink-3)`). The smallest text on the page is
drawn in the one token that fails contrast, which compounds the chart problem in defect 1.

Fix by darkening the token in both pages' `:root` blocks — one line each, and it lifts every
one of those eight usages at once. See the `design-system` skill for the full matrix.
`--accent` on `--surface-2` in light (4.32) is large-text/UI only.

### 3. Unverified, check when auditing

- Heading order on both pages (no skipped levels; one `h1` each).
- `#status` updates during parsing — confirm they reach a live region rather than only
  changing text silently.
- The results region is revealed by toggling `hidden`; confirm focus or an announcement
  moves there, so a keyboard user knows the analysis arrived.
- `docs/methodology.html` tables: confirm `<th scope>` and captions.
- Zoom to 200% and 400% reflow; the charts have `viewBox` so they scale, but check captions
  and the stats grid do not clip.

## Method

Prefer checks that can be re-run over one-off inspection.

```bash
conda activate energy-advisor
node tools/test_tool_render.mjs        # jsdom render; pins the DOM contract
pytest -q tests/report/                # findings prose, no-dollars, bundle staleness
```

Contrast is arithmetic — compute it rather than eyeballing, using the relative-luminance
formula against the token values in `:root`. Report ratios to two decimals with the pass
threshold stated, as the table above does.

## Constraints that override generic advice

- **Do not introduce a `$`, `¢` or `/kWh` into any computed region.** The tool prices nothing
  by design and tests enforce it. This outranks any presentational argument.
- **Do not move generated copy into the HTML.** Findings prose comes from
  `src/report/inspect.py` so it can be tested; rewording belongs there.
- **Do not hand-edit `docs/engine.js`** — it is generated from `src/`.
- Changes to the pinned DOM must land with the matching test change in the same commit.
