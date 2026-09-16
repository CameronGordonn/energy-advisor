# Stream B — PCIA disambiguation + corpus growth (2026-09-15)

> **STATUS 2026-09-16 (session 26): this file's recommendations have been absorbed.** Both
> softenings it asked for are done, in HANDOFF.md, the April fixture and the tests. One of its
> own claims was corrected in the process — "all six other territories remain far off, >$2, in
> every quarter" is not right; June CARE puts `inland_basic` $1.41 off. And the territory
> finding went further than this file states: **no single territory fits every cell**, not just
> "the contest flips". All three quarters are now under test
> (`tests/published_impacts/test_sdge_tou_dr1_quarters.py`). The measurement method below is
> superseded by that test, which does the same work in CI instead of in a scratch script.

Written for: the next Claude Code session (and stream A / Cameron reconciling parallel work).
Scope per `notes/session25_handoff_prompts.md`: settle the PCIA inference across quarters,
grow the fixture corpus. Per that brief, this file — not SESSION_NOTES.md or HANDOFF.md —
is where stream B's findings live; stream A owns those two.

**Do not edit `tests/published_impacts/sdge_2026-04_tou_dr1.yaml`'s existing fields.**
Stream A's `test_sdge_2026_04_tou_dr1.py` reads `measured_2026_09_15.pcia_treatment` and
several other keys in that file directly. This session added a pointer comment only
(none of the file's tested values), to avoid a collision with a test that was mid-edit in
the same working tree when this session started — see "coordination note" at the bottom.

## Job 1 — settle the PCIA inference. SETTLED.

**Claim:** SDG&E's published "unbundled" (delivery-only) residential bill-impact figures
exclude the vintaged PCIA, even though a real unbundled (CCA) customer pays it.

**Method.** Fetched two more SDG&E rate-change alerts — January 2026 and June 2026 — to
put alongside the already-fixtured April 2026 one. Three independently filed documents,
three different rate vintages (`sdge_tou_dr1_delivery_2026-{01,04,06}-01.yaml`), covering
both CARE and non-CARE, six cells total. For each, computed the delivery-only bill at
`coastal_basic` three ways: PCIA excluded, PCIA at its cheapest vintage on that sheet, PCIA
at its most expensive (2026) vintage. All engine-verified through `compute_bill` (see the
scratch script note below), not hand arithmetic alone.

**Result — residual (|computed - published|), best case each side:**

| quarter | class    | PCIA excluded | PCIA included, best vintage |
|---|---|---|---|
| Jan 2026 | non-CARE | $0.60 | $6.14 (2009 vintage) |
| Jan 2026 | CARE     | $0.14 | ~$5+ |
| Apr 2026 | non-CARE | $0.48 | $6.63 (2009 vintage, per stream A's test) |
| Apr 2026 | CARE     | $0.21 | ~$5+ |
| Jun 2026 | non-CARE | $0.86 | $14.68 (2018 vintage) |
| Jun 2026 | CARE     | $0.43 | ~$10+ |

**Verdict.** The PCIA-excluded residual never exceeds $0.86 on a $119-124 bill (well inside
the ±$0.50-ish rounding/territory noise this corpus already carries). The best possible
PCIA-included residual — picking whichever vintage happens to land closest, which a real
customer cannot do, since their vintage is fixed by when they left bundled service — never
gets under $5. That gap is an order of magnitude too large to be rounding, territory choice,
or coincidence. **Confirmed across three independently filed documents spanning three rate
vintages: SDG&E's published "unbundled" bill-impact figure excludes the PCIA.**

It remains, honestly, an *inference* rather than a documented rule — no SDG&E rate alert
states this outright; footnote 3 of each one only says actual bills vary by "PCIA rate which
will vary based on when you became a CCA customer," which is consistent with excluding an
indeterminate component but doesn't say so. What changed is the evidence class: one document
could have been a coincidence of arithmetic; three independently filed documents, in three
different quarters, agreeing on the same exclusion by the same order-of-magnitude margin, is
a pattern. Recommend stream A (or whoever finalizes the fixture) treat `pcia_treatment:
EXCLUDED_BY_INFERENCE` as settled going forward, updating only the comment/prose that calls
it single-quarter evidence.

## Job 2 — grow the corpus

Three new fixtures added to `tests/published_impacts/`:

- `sdge_2026-01_tou_dr1.yaml` — January 2026 rate alert (Advice Letter 4757-E). Testable,
  same shape as the existing April fixture.
- `sdge_2026-06_tou_dr1.yaml` — June 2026 rate alert (Advice Letter 4843-E, a FERC-driven
  interim decrease, not a routine annual filing). Testable.
- `pge_2026-03_class_average.yaml` — PG&E's March 2026 Electric Rate Advisory (Advice Letter
  7846-E). **Not testable, and marked so explicitly** — see the fixture's own header. PG&E
  states no schedule and no territory, averaging its entire residential class at a flat
  500 kWh; there is no spec to check it against without inventing a load mix, which invariant
  6 forbids. Kept for provenance and because it independently corroborates the direction and
  rough size of PG&E's Base Services Charge rollout (a ~2.5% bundled decrease, an ~8%
  CARE-specific decrease — consistent with the source's own framing that the BSC structure
  gives CARE customers a larger discount).

No August 2026 SDG&E alert exists — checked `sdge.com/rate-alerts` directly (full listing
2024-2026); SDG&E does not appear to have issued a customer-facing rate alert for the 8/1
delivery/generation vintage change. Not pursued further; the three 2026 alerts that exist
(Jan/Apr/Jun) are now all fixtured.

Sources fetched via `WebFetch` (which saves PDF bytes to disk even when it cannot parse
them inline — same trick as the session-9 field note) and extracted with `pdftotext -layout`
per CLI-PLAN's D5 finding (raw `pdftotext` destroys column labels). All four PDFs plus their
`.layout.txt` extractions are in `data/sources/` (gitignored):
`sdge_rate_change_alert_2026-{01,04,06}.{pdf,layout.txt}`,
`pge_electric_rate_advisory_2026-03.{pdf,layout.txt}` (the PG&E one was already on disk from
earlier CLI-PLAN work).

## An unplanned finding — the territory identification is weaker than session 25 stated

Verifying the two new quarters through `compute_bill` (script below) surfaced something
worth flagging under CLAUDE.md's "surface the decision, don't pick silently" rule, because
it revises a claim already written into HANDOFF.md and the April fixture.

Session 25's original claim: "coastal_basic is the only [of eight] territory that rounds to
the published $123" for April. True of April's numbers. **Not true of the other two
quarters**, checked the same way (engine, `by_hour_count` allocation, all eight territories):

| quarter | coastal_basic (|residual|) | coastal_all_electric (|residual|) | which is closer |
|---|---|---|---|
| Jan 2026 | 123.60 (0.60) | 122.46 (0.54) | **all_electric**, by $0.06 |
| Apr 2026 | 123.48 (0.48) | 122.35 (0.65) | **basic**, by $0.17 |
| Jun 2026 | 119.86 (0.86) | 118.75 (0.25) | **all_electric**, by $0.61 |

(CARE figures, same territories: April and January both favor `coastal_basic` clearly —
0.21 vs 0.96, and 0.14 vs 0.88 — while June mildly favors `coastal_all_electric`, 0.29 vs
0.43. All six other territories remain far off, >$2, in every quarter — verified by full
sweep — so `coastal_basic` vs `coastal_all_electric` is the only real contest in any quarter.)

**Why this happens, mechanically:** the two territories' computed bills sit about $1.05-1.13
apart from each other in every quarter (a stable structural gap — coastal's all-electric
allowance is large enough in winter, 13.5 vs 9.2 kWh/day, that most of its baseline credit
saturates at the 400 kWh cap while basic's does not). SDG&E's published figure is a whole
dollar, itself an average that "may not sum due to rounding." Whichever side of the midpoint
between the two candidates that quarter's specific published number happens to fall on
determines which territory "wins" a nearest-value test — and nothing pins that side reliably,
because a ~$1 structural gap and a ~$0.5-0.9 rounding/estimation band overlap by construction.

**What this does NOT undo:** it does not touch the PCIA settlement above (that gap is
$5-15, an order of magnitude larger than this $1 territory gap, and survives it easily). It
also does not mean the territory is unknowable — `coastal_basic` remains the better-supported
choice on a **domain prior**: SDG&E's own Sheet 29294-E frames All-Electric as an
application-only special case ("available upon application to those customers who have
permanently installed space heating or who have electric water heating and receive no energy
from another source"), so most households, including SDG&E's own "typical residential
customer" framing, are Basic by default. CARE evidence leans the same way in 2 of 3 quarters.
**What it does undo** is the stronger claim that the published figure *uniquely identifies*
the territory by arithmetic alone — that was true of one quarter's numbers and not
reproducible. Recommend HANDOFF's session-25 entry and the April fixture's own comment be
softened from "identifies" to "is consistent with, on a domain prior" the next time either
is touched by whoever owns them (stream A / a future session) — not touched here to avoid
the concurrent-edit collision noted below.

## Verification method

All engine numbers above came from a scratch script
(`scripts_scratch` not committed — ad hoc, run against the installed environment), using the
same `compute_bill` / `by_hour_count`-style allocation as `test_sdge_2026_04_tou_dr1.py`,
over the twelve calendar months from each vintage's own effective date
(2026-01-01..2026-12-31, 2026-04-01..2027-03-31, 2026-06-01..2027-05-31). Not committed as a
test per the stream split (stream A owns `tests/published_impacts/*.py`); the exact figures
are recorded in each new fixture's `measured_by_engine_2026_09_15` block so they are
reproducible without rerunning anything ad hoc.

## Coordination note

`tests/published_impacts/sdge_2026-04_tou_dr1.yaml` and
`tests/published_impacts/test_sdge_2026_04_tou_dr1.py` were being actively written by
(apparently) stream A in this same working tree while this session ran — the April fixture
changed under this session mid-task (a `measured_by_engine_2026_09_15` block and an updated
PCIA note appeared between two reads). Per the session-17/19/21/22 lesson in SESSION_NOTES.md
(parallel sessions share one working tree and one git index), this session made no edits to
that fixture or to HANDOFF.md/SESSION_NOTES.md, to avoid clobbering in-flight work. The two
new SDG&E fixtures and the PG&E provenance fixture are new files and carry no such risk.
Whoever commits should use `git add` with explicit paths per file, not a bare `git add -A`,
so each stream's work lands as its own commit.
