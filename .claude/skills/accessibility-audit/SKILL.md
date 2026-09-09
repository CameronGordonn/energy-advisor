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

## Fixed — keep them fixed

Each of these is easy to reintroduce, and two of them have been reintroduced once already.

**Charts have a text equivalent.** `role="img"` makes an SVG atomic: its children leave the
accessibility tree, so per-bar `<title>` elements are pointer tooltips and are **never
announced**. The 24 `<title>`s stay (the render test counts them) and `#hourTable` /
`#monthTable` carry the same numbers as real tables. Both charts use `aria-labelledby`
pointing at their visible caption, so the description cannot drift from the text beside it.

**Every token clears AA.** Full matrix in the `design-system` skill. `--sul` is the exception
and is a **fill only** — 1.89:1 on paper. Accent text is always `--ox`.

**Chart bars meet non-text contrast.** Bars are data, so they need 3:1 against the plate, not
the 1.5:1 a hairline colour gives. `--mark` is 3.39 / 3.25; `--ox` on the sulphur band is
4.58 / 3.62. **A border colour is not a data colour.**

**Heading order is unbroken** on `index.html`: `h1 → h2 → h3`, finding cards `h4` under the
"What stands out" `h3`. And on `methodology.html` since session 20: 27 headings, one `h1`,
zero skips. Its `.plate-head` titles are `<p>`, **not headings** — a plate is a figure, not a
section, and making them `h4` under an `h2` is what broke the order in the first place. Each
table carries a visually-hidden `<caption>` instead.

**Every `th` on `methodology.html` has a `scope`**, including row headers (billing period,
plan name, component). The pass column is `✓<span class="vh"> within tolerance</span>` — a
bare glyph is not a status.

**The reconciliation chart's tooltip is not a live region.** It was `role="status"` and set
its text on `mouseenter`, which announced eleven statements on mouse-over. It is `aria-hidden`;
the table below is the text equivalent. Same rule as the index charts: `aria-labelledby`
points at the visible caption so the description cannot drift from the words beside it.

**Reflow at 200% and 400% holds on both pages**, and two of the three defects found were
structural rather than cosmetic — see the design-system skill for `.row>*{min-width:0}` and
why an `overflow-x:auto` box containing a `.vh` caption needs `position:relative`. Re-check
with the audit below after any layout change; jsdom cannot see any of it.

**Label collisions.** Fixed twice now on the hour chart. jsdom does no layout and will never
catch this — run `scripts/screenshot_site.py` and look.

## Open defects

### 3. Unverified, check when auditing

Both remaining items are on `index.html`; `methodology.html`'s list was closed in session 20.

- `#status` updates during parsing — confirm they reach a live region rather than only
  changing text silently.
- The results region is revealed by toggling `hidden`; confirm focus or an announcement
  moves there, so a keyboard user knows the analysis arrived.

## Method

Prefer checks that can be re-run over one-off inspection.

```bash
conda activate energy-advisor
node tools/test_tool_render.mjs        # jsdom render; pins the DOM contract
pytest -q tests/report/                # findings prose, no-dollars, bundle staleness
```

**Reflow and heading order need a real browser.** Drive Playwright at 1280 / 640 / 320 CSS px
and assert `document.documentElement.scrollWidth <= clientWidth` on every page — 640 and 320
are 200% and 400% zoom of a 1280 viewport, and a page that scrolls sideways there fails WCAG
1.4.10. In the same pass, walk `h1..h6` for level skips and every `th` for a missing `scope`.
This found three failures in session 20 that both the jsdom test and the screenshot pass had
missed, one of them on `index.html`.

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
