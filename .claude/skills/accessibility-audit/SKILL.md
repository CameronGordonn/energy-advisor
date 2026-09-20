---
name: accessibility-audit
description: Accessibility review for this repo's four published pages (docs/index.html, methodology.html, privacy.html, terms.html) — what already holds and must not regress, the known open defects, and how to check. Load when auditing, redesigning, or adding UI to docs/, or when changing the SVG charts, the ranking table or the file-drop control.
---

# Accessibility audit — energy-advisor site

The audience is homeowners checking their own utility bills, not developers. A visitor who
cannot read the chart cannot use the tool at all, because the chart **is** the output.

Audit all four published pages: `docs/index.html` (the tool), `docs/methodology.html` (the
writeup) and the two legal pages, which since session 30 use the same `.row`/`.rail` grid as
the rest of the site. Target WCAG 2.1 AA.

⚠ **The tool page has four states, not one**, and three of them are invisible to a plain
page load: the report (`__renderInspection`), the priced ranking (`__renderRecommendation`)
and the refusal (`__renderGate`). An audit that only loads the page has audited the smallest
of the four. Both scripts below drive all of them.

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

**Heading order is unbroken** on `index.html` — but only since session 30, and the previous
note here was wrong in a way worth remembering. It claimed the finding cards sat "under the
'What stands out' `h3`"; **that `h3` was not in the page**, so the report actually skipped
`h2 → h4`, and the tool page as a visitor first meets it skipped `h1 → h3`, because section
02 ("Procedure") had no heading of its own and `#results`' `h2` is out of the accessibility
tree while it is `hidden`. Both are fixed — the `h3` now exists and section 02 has an `h2` —
and **both are now checked rather than asserted**, by `scripts/audit_layout.py`, which walks
the tree in a real browser in both states. Nothing in the jsdom test or the screenshot pass
could see either one. And on `methodology.html` since session 20: 27 headings, one `h1`,
zero skips. Its `.plate-head` titles are `<p>`, **not headings** — a plate is a figure, not a
section, and making them `h4` under an `h2` is what broke the order in the first place. Each
table carries a visually-hidden `<caption>` instead.

**Every `th` on every page has a `scope`**, including row headers. `methodology.html` has
had them since session 20; `index.html`'s three generated tables (`#hourTable`, `#monthTable`,
`#fileTable`, plus `#stats` and the two pricing tables) did **not** until session 30, because
nothing walked them. `audit_layout.py` now does. The pass column is `✓<span class="vh"> within tolerance</span>` — a
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

**Status and arrival are announced, and the announcer is not `#status`.** Session 29 closed
both remaining index defects. `#status` is toggled with `hidden`, and a live region that is
out of the accessibility tree when its text is written announces nothing — so the
announcements go through `#announcer`, a `.vh` `role="status" aria-live="polite"` paragraph
that is **always present, never hidden, and empty on load**. `status()` writes HTML
(entities, a spinner `<span>`), so it announces `plainText(msg)`, never the markup. Revealing
`#results` also announces ("Analysis ready…") **and** moves focus into it (`tabindex="-1"`,
`focus({preventScroll:true})` before the smooth scroll) — a keyboard user needs both the
message and the caret, not either. All four facts are pinned by `tools/test_tool_render.mjs`
and mutation-checked: deleting the announce or the focus call fails it.

**`#results` is focused but does not paint a ring.** It is revealed, announced and focused
(`tabindex="-1"`), and Chromium then applied the global `:focus-visible` outline to the whole
region — at full report length a 4,700px oxblood box that reads as an error state.
`#results:focus{outline:none}` is scoped to that one element and to nothing else: it is a
scroll-and-focus target, not a keyboard-reachable control, so the rule that **every
interactive control shows a focus ring is untouched**. Do not generalise it.

## Open defects

None known on any of the four pages. `index.html`'s live-region and focus items were closed
in session 28; `methodology.html`'s list in session 20; the heading skip, the missing `th`
scopes and the focus ring in session 30.

⚠ **"None known" has meant "nobody looked with the right instrument" twice now.** Session 30
found three live defects on a page this file described as clean, because reflow, heading
order and `scope` need a browser and a tree walk and nothing in CI does either. The next
audit's job is to find new ones with the method below — and if it adds an instrument, to say
so here.

## Method

Prefer checks that can be re-run over one-off inspection.

```bash
conda activate energy-advisor
node tools/test_tool_render.mjs        # jsdom render; pins the DOM contract
pytest -q tests/report/                # findings prose, no-dollars, bundle staleness
```

**Reflow, heading order and `scope` need a real browser and a tree walk — so they are a
script now, not a procedure.**

```bash
PYTHONPATH=src python scripts/audit_layout.py
```

It drives Playwright at 1280 / 640 / 320 CSS px (640 and 320 being 200% and 400% zoom of a
1280 viewport, where a sideways scroll fails WCAG 1.4.10), on all four pages and on the tool
page in both its closed and its open state, and reports level skips and bare `th`s. Session
20 found three failures this way by hand; session 30 found two more the first time the script
ran. If you extend the audit, extend the script.

**Contrast is arithmetic — so it is a script too**, reading the tokens out of `site.css`
rather than a table somebody retypes:

```bash
PYTHONPATH=src python scripts/contrast_matrix.py --markdown
```

⚠ **Check a fill's edge as well as the text on it.** `--band` against the plate is 1.09 light
/ 1.25 dark. The sulphur highlight reads instantly in light mode on *hue*, but luminance is
what survives dark mode, greyscale and most CVD — which is why the current-plan marker in
`#planTable` carries a 2px `--ink-2` edge. The state it marks is also written in words in the
"vs. yours" column, so it was never carried by colour alone.

## Constraints that override generic advice

- **Do not introduce a `$`, `¢` or `/kWh` into the LOAD-SHAPE half** (`#stats`, `#findings`,
  the two charts, `#fileTable`, `#warnBox`) **or into a refusal** (`#priceGateText`,
  `#priceGateList`). That half runs for every visitor, including the ones the engine may not
  price. **Section R2 (`#priceOut`) is denominated in dollars on purpose** — the tool has
  priced since session 28, and the old blanket "the tool prices nothing" rule is retired.
  See the `design-system` skill, contract 2, for exactly which test covers which half.
- **Do not move generated copy into the HTML.** Findings prose comes from
  `src/report/inspect.py` so it can be tested; rewording belongs there.
- **Do not hand-edit `docs/engine.js`** — it is generated from `src/`.
- Changes to the pinned DOM must land with the matching test change in the same commit.
- **The refusal is a designed state, not an error state.** A household the engine may not
  price sees `#priceGate` with named blocker codes and no dollar figure. Audit it with the
  same care as the answer — `screenshot_site.py` and `audit_layout.py` both render it.
