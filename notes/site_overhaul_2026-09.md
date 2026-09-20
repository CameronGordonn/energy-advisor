# The visual half of the site overhaul — 2026-09-20

HANDOFF's session-28 update, item 9, named this as not started: "the visual half of the site
overhaul (all four pages, the design-system skill rewrite, a recomputed contrast matrix)".
This is that work. No `src/` file was touched — another session owns it in parallel, and it
was editing the same working tree while this ran (see **The bundle test** below).

Branch: `site-overhaul`.

---

## 1. The stamp: split, at Cameron's decision

`docs/index.html:202` stamped **NOT A BILL / NO AMOUNT DUE** directly under hero copy that
now promises to re-bill a year under every rate plan. Still literally true — it is not a
bill, nothing is due — but the device was authored in session 12 to say the thing the tool
then did, which was *price nothing*, and session 28 made it price. Left alone it reads as a
retraction of the sentence above it, and it sits about 2,000px from the only dollar figures
it qualifies.

Three options were put to Cameron with their consequences. **He chose the split:**

- **Hero** now stamps the *claim*: `RECONCILED ±$2 / 11 OF 11 REAL BILLS`. That is what earns
  the right to the figures further down.
- **`#priceOut`** stamps the *disclaimer*: `NOT A BILL / NO AMOUNT DUE`, beside the verdict,
  where the money actually is. `.stamp.due` leans `+2.5°` against the hero's `−3°` so the two
  read as a pair of impressions rather than a repeated motif.

No test pins `.stamp`, so this was free of CI risk. It is recorded in the design-system skill
as a decision, not a preference: do not re-merge them without asking.

The hero stamp also now sits at `margin-left:auto`, anchored under the end of the headline
instead of trailing the lede into an empty half-row.

---

## 2. The design-system skill was wrong in four places, and one of them mattered

The brief flagged three; a fourth turned up while checking the first.

**Contract 2 ("No dollar figures anywhere the page computes / The tool prices nothing by
design") — reversed.** It was rewritten around what the tests actually cover, which is not
what the old text implied:

- `tests/report/test_inspect.py::test_the_inspection_carries_no_dollar_figures` guards the
  **inspection layer only** — the `Inspection` pydantic model's *field names* against a
  money-shaped word list, plus `"$" not in i.model_dump_json()`. It is a statement about one
  Python object. It says nothing whatever about the page.
- `test_findings_never_quote_a_price` likewise covers only a `Finding`'s `title` and `detail`.
- The **page** half is `tools/test_tool_render.mjs`, which scans `#stats`, `#findings`,
  `#hourChart`, `#monthChart`, `#fileTable`, `#warnBox` for `$<digit>` — and separately
  asserts that `#planTable` **is** dollar-denominated, and that a refusal is not.

So the real boundary is three-part (load-shape half never prices / R2 prices on purpose /
a refusal stays clean), and the real *limit* on pricing is not a blanket refusal at all — it
is that the committed PG&E specs describe **one household** (territory T, all-electric, 3CE,
PCIA 2018), a scope derived by `authored_scope()` with four named blocker codes.

**`docs/site.css:93`'s comment ("A tool that deliberately prices nothing")** — rewritten to
describe the two stamps and why there are two.

**The skill's description said "two published pages" while its body said four** — both now
say four, and the body now describes the legal pages as part of the system rather than as an
afterthought.

**The fourth, found while checking: the accessibility skill's heading-order claim was false.**
It stated that the finding cards sit "under the 'What stands out' `h3`". That `h3` did not
exist in the page. See §4.

`.claude/skills/accessibility-audit/SKILL.md` was updated in the same pass — its "audit the
two published pages", its "Open defects: none known", and its blanket no-dollars constraint
were all stale in the same direction.

---

## 3. Contrast: recomputed, and now derived rather than retyped

`scripts/contrast_matrix.py` (new) parses the tokens out of `docs/site.css`'s own `:root` and
`[data-theme="dark"]` blocks and computes the matrix from the relative-luminance formula.
`--markdown` prints the table that is pasted into the skill; a non-zero exit means a pair
failed its threshold.

**The palette did not change, and every previously recorded number reproduced exactly** —
14.21 / 12.66 / 7.16 / 6.38 / 5.07 / 4.52 / 5.60 / 4.99 / 3.39 / 3.02 / 4.58 / 3.62 / 1.89.
The hand-maintained table had been right. It is now a derivation, so it cannot go stale.

**One recorded figure was misleading and is corrected.** `index.html`'s comment on the
sulphur row said the conditional-plan note "steps to `--ink-2` (6.61)". 6.61 is the **dark**
figure; light is **5.86**, and light is the tighter of the two. Both pass; the comment now
carries both and says which one binds.

**⭐ The finding that changed a design decision: a fill's edge is a different number from the
text on it.** `--band` against `--paper-2` is **1.09 light / 1.25 dark**. The sulphur
highlight reads instantly in light mode because the *hue* shift is large, but luminance is
what survives dark mode — and in the dark ranking the current-plan marker was all but
invisible. `--ink-2` was chosen as a 2px edge (6.38 / 8.25 against the plate, clear of 3.0 in
both themes) because it is ink and therefore carries no chart meaning. The state is also
written in words in the "vs. yours" column, so it was never colour-alone; this is legibility,
not a 1.4.1 failure.

---

## 4. Two live accessibility defects, on pages recorded as clean

`scripts/audit_layout.py` (new) drives Playwright over all four pages at 1280 / 640 / 320 CSS
px, and over the tool page in **both** its closed and open states, checking three things CI
cannot see: sideways scroll (WCAG 1.4.10), heading-level skips walked over the
**accessibility tree**, and `scope` on every `th`.

It found two faults the first time it ran, on pages the accessibility skill described as
having no known defects:

1. **`h2 → h4` in the report.** The findings' `h4` cards hung straight off the report's `h2`.
   The skill said they sat under a "What stands out" `h3`; that `h3` was not in the page.
   Fixed by adding it — which the list wanted anyway, since it had no label at all.
2. **`h1 → h3` on the tool page as a visitor first meets it.** Section 02 ("Procedure") had no
   heading of its own, and `#results`' `h2` is out of the accessibility tree while it is
   `hidden`, so the first heading after the `h1` was a step's `h3`. Fixed with an `h2.sec`
   ("What happens, start to finish"), which the section was missing visually too — it was the
   only `.row` on the page without one.

And a third class it enumerated: **`index.html`'s generated tables had no `scope` at all** —
`#hourTable`, `#monthTable`, `#fileTable`, `#stats` and `#whyTable`, ~45 bare `th`s.
`methodology.html` has had them since session 20; nobody had ever walked the tool page.
All now carry `scope="col"` / `scope="row"`, including `#planTable`, whose plan-name cell was
promoted from `<td>` to `<th scope="row">`.

**Reflow was clean everywhere**, including after the legal-page restructure — 12 page/width
combinations, no sideways scroll.

A fourth defect came from the screenshots rather than the audit: **focusing `#results` painted
a 4,700px oxblood `:focus-visible` box** around the whole report. `#results:focus{outline:none}`
is scoped to that one element — a scroll-and-focus target with `tabindex="-1"`, not a
keyboard-reachable control — and the global focus-ring rule is untouched. The arrival is
still announced through `#announcer` and focus still moves, both still pinned by the render
test.

---

## 5. The legal pages joined the site

`privacy.html` and `terms.html` were a single 42rem `.doc` column sitting in a 76rem sheet
with an empty left gutter — the one place on the site that stopped looking like the document
it is about. Both now use the same `.row`/`.rail` grid as the tool and the methodology page:
**one row per `h2`**, numbered `00`–`11` (privacy) and `00`–`14` (terms), each with a short
mono tag in the margin. A numbered clause with its number in the margin is what a legal
document does on paper anyway.

The measure is unchanged (`.doc` is still `max-width:42rem`); only the scaffolding around it
moved. `.doc h2` grew from `1.1rem` to `1.25rem` and lost its top margin, since it is now the
first child of its row.

Two small shared fixes fell out of looking at them:
- **`.gate` had no `max-width`**, so a refusal's quoted rule ran to the full content column
  while the reasons beneath it stopped at 70ch. Capped at 78ch.
- **`.doc .callout p{margin:0}`** butted the terms callout's two paragraphs together. Added
  `p+p{margin-top:.8rem}`.

---

## 6. Both charts had collisions jsdom cannot see

**`#hourChart`: the direct label sat on the band's edge.** `T = 64` is the headroom that keeps
the band caption and the "BUSIEST · 6 P.M." label apart, and it was still doing that job. What
nothing covered was the band's *own* 10px overhang above the plot: with the busiest hour
inside the band — the common case — the label's baseline landed at y=54 and the band's top
edge was also 54, so the words sat half on sulphur and half on paper. The overhang is now
`BAND_LIFT = 6` and the label `LABEL_LIFT = 16`, which puts 10px of paper between type and
fill and still leaves 14px under the caption. **They are a pair and are commented as one** —
this is the third distinct way that corner has broken.

**`#monthChart`: the rotated ticks ran into the axis caption.** Ticks were at `−42°` with
`B = 52`, and their descending ends overlapped `KWH PER CALENDAR MONTH`. The fix is not more
room: thirteen months across 698px leaves ~54px per tick and `"Jul 25"` needs ~33px, so **the
rotation is gone** and the ticks sit level. `B` went to 62, the caption to `H−4`. A rotated
axis label is a workaround for a width problem this chart does not have.

`monthLabel()` compresses the engine's `"2025-07"` for the **axis only**. The per-bar
`<title>` and `#monthTable` keep the engine's own string, because the table is the chart's
text equivalent and should carry the value verbatim.

Neither change touches a `<rect>`, so the pinned counts (25 / 5 / 24 / one per month) are
untouched.

---

## 7. The ranking is the product's answer and was six numbers in a column

`#planTable` in `#priceOut` is where the whole site lands. Two things were wrong with it:

**The hierarchy was inverted.** The loudest row was the reader's **current** plan — a
full-width sulphur fill — while the **recommended** plan was merely bold. A table whose job
is to rank against the status quo was shouting the status quo. The winner now carries
**oxblood rules top and bottom**; the current plan keeps sulphur as a **highlighter on its
name** rather than a fill across the row, plus the `--ink-2` edge from §3.

**There was no magnitude encoding at all.** `.mbar` is a thin bar in the cost cell encoding
**the gap to the cheapest plan** — zero-based, so the winner's bar is correctly empty —
growing right-to-left under the right-aligned figure, the way a ledger sets a column. It
carries a `.vh` text equivalent because that number is printed nowhere else on the page.

⚠ **The tradeoff worth flagging, since the generic answer and the differentiating one
disagree.** The obvious move is to paint the winner's bar in the accent. The repo's rule is
that **`--ox` means "the expensive hours" and nothing else** as a data colour, so painting
the *cheapest* plan oxblood would invert it. All bars are `--mark`; the winner is marked with
`--ox` **as a rule**, which is how `site.css` already uses it for links, rail numbers and the
stamps. The `dataviz` skill's "colour follows the entity, never its rank" points the same way.

---

## 8. The bundle test, and why it is not this work's

`PYTHONPATH=src python -m pytest -q` ends **1 failed, 1771 passed**, on
`tests/report/test_web_engine.py::test_the_committed_bundle_matches_src`.

**That failure belongs to the parallel `src/` session, which is working in this same working
tree.** Uncommitted at the time of writing: `src/tariffs/bill.py`, `src/report/reconcile.py`,
a new `src/tariffs/bucketed.py`, `tests/golden_bills/test_reconciliation.py` and a new SDG&E
bill-only fixture template. Demonstrated rather than assumed:

```
git stash push -- src tests && pytest -q tests/report/test_web_engine.py   # 5 passed
git stash pop
```

`docs/engine.js` is byte-identical to `origin/main` and was not touched here.

⚠ **Whoever lands that `src/` work must regenerate `docs/engine.js` AND
`docs/case-study.json`** — the case study records the bundle's digest and is built from
gitignored `data/`, so only someone with `data/` can do it. That is the repo's standing
stale-cache hazard, and this is it firing.

Baseline before any of this work: **1,711 passed**, both node checks green.

---

## Verification

```
node tools/test_tool_render.mjs                    # 42 checks, all pass
node tools/test_engine_wasm.mjs                    # WASM ENGINE MATCHES NATIVE
PYTHONPATH=src python -m pytest -q                 # 1 failed (see §8), 1771 passed
ruff check . && ruff format --check .              # clean, 78 files
PYTHONPATH=src python scripts/contrast_matrix.py   # every pair clears its threshold
PYTHONPATH=src python scripts/audit_layout.py      # reflow, heading order, th/scope all clean
PYTHONPATH=src python scripts/screenshot_site.py   # 18 images, looked at in both themes
```

## What was NOT done

- **No palette change.** Every token is session-12's. The matrix was recomputed to confirm
  that, not to accommodate a change.
- **`src/` untouched**, per the brief.
- **`docs/engine.js` and `docs/case-study.json` untouched**, per the brief — no UI change
  here can move either.
- **`HANDOFF.md` not rewritten and `SESSION_NOTES.md` not prepended to**, per the brief. The
  session-notes entry is in `notes/_pending_session_notes_site.md` for merging.
