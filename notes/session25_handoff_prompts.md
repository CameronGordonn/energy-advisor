# Session 25 handoff — status, parallel streams, and paste-ready prompts

Written for: the next Claude Code sessions, not for Cameron. Written 2026-09-15.

## Status across all three tracks

### ROADMAP (the product)

| Milestone | State | Blocker |
|---|---|---|
| M0 PG&E reconciliation | **Done** | — |
| M1 SDG&E + CCA | Engine complete, **DoD blocked** | dad's export + 3 bills, or a recruited SDG&E user |
| M2 Rate optimizer | **Done for PG&E** | the SDG&E household |
| M3 NEM 3.0 | Engine complete, **DoD blocked** | one real household with export data |
| M4 Methodology | **Done, live** | — |
| M5 External users | Drafted, nothing sent | gated on M1 |

Unchanged by session 25. Nothing here moved; M1 and M3 are blocked on data that does not
exist in this repo and cannot be substituted.

### CLI-PLAN (the spec-extraction pipeline)

| Phase | State |
|---|---|
| A — CLI surface | **Done** except `--bare` (needs a Console API key) |
| B — schema + prompt as a skill | **Frontmatter done** (`.claude/skills/author-rate-spec/`). Schema and body are **Cameron's to write** and are the critical path |
| C — driver + calibration | Not started. Sources now on disk (D5), so it is unblocked apart from B |
| D — scoring loop | Not started |
| E — hooks, MCP, subagents | Not started |

Decisions D1-D5 are settled and recorded in CLI-PLAN.md. **D2-D4 are hypotheses about what a
generator gets wrong; nobody has measured them.** Expect phase C calibration to revise them.

### tests/published_impacts (new, session 25)

Tier 2. Fixture + README written, **no test written**. First outside evidence to touch
TOU-DR1. Carries one load-bearing inference (`pcia_treatment: EXCLUDED_BY_INFERENCE`) that
should be disambiguated before the assertion is written.

---

## What is actually available to work on

Ordered by value. Note that #0 is not a session.

0. **Dad's SDG&E data, or a recruited SDG&E user.** Outranks everything. Human action.
1. **Disambiguate the PCIA inference** (stream B below) — de-risks #2's main assumption.
2. **Write the tier-2 delivery point test** (stream A) — converts session 25's measurement
   into a permanent gate, and partially closes HANDOFF next-action #2.
3. **Cameron writes the JSON schema + skill body** — CLI-PLAN phase B critical path. No
   session can do this; rule 1 reserves it.
4. **Phase C scaffolding** (stream C) — the parts that do not depend on the schema.

---

## Parallel streams

⚠ **File ownership, to avoid merge conflicts.** Parallel sessions must not all edit
`SESSION_NOTES.md` and `HANDOFF.md`. Assign: stream A owns SESSION_NOTES.md and HANDOFF.md.
Streams B and C write to their own notes file under `notes/` and hand their findings to A.

---

### STREAM A — tier-2 test (sequential, do first or alone)
**Model: Opus 5 (`claude-opus-5`). Effort: high.**
Touches the pricing path and a live invariant boundary. Not a place to economise.

```
Read CLAUDE.md, then HANDOFF.md, then the session 25 entry in SESSION_NOTES.md, then
tests/published_impacts/README.md and tests/published_impacts/sdge_2026-04_tou_dr1.yaml.
Do not re-derive anything recorded there.

Write the tier-2 test for tests/published_impacts/. Two assertions, and they are NOT the
same kind of test:

1. DELIVERY (point test). SDG&E TOU-DR1 delivery energy is flat across all six
   season x period keys, so the unbundled figure needs no load-shape assumption. Assert
   that the committed sdge_tou_dr1_delivery_2026-04-01.yaml, priced at 400 kWh/month for
   an annual-average month, reproduces the published $123 non-CARE and $67 CARE at
   baseline territory coastal_basic, and that NO OTHER territory does. Session 25
   measured $123.48 / $66.79 by hand arithmetic off the spec YAML. YOUR TEST MUST GO
   THROUGH compute_bill(), not repeat the hand arithmetic — that is the whole point, and
   it means constructing a degenerate interval series. Expect the engine figure to differ
   from $123.48; investigate any gap rather than widening the tolerance.

2. GENERATION (feasibility test). Assert that the implied $71 lies inside the achievable
   envelope [$30.73, $122.31]. This is deliberately weak. Do not dress it up as
   reproduction, and do not assume a load shape to tighten it.

Honour the tier boundary in tests/published_impacts/README.md: nothing there may be
imported by src/, nothing counts toward the +/-$2 golden-bill pass rate, and no figure may
reach a user-facing output. If a test you write would blur that line, stop and say so.

The published figures are whole dollars; derived quantities inherit +/-$1 per operand. Get
the error bands right or the test fails on correct specs.

Then append to SESSION_NOTES.md and update HANDOFF.md's next-action list.
```

---

### STREAM B — PCIA disambiguation + corpus growth (parallel-safe)
**Model: Sonnet 5 (`claude-sonnet-5`). Effort: high.**
Mechanical fetch-and-measure with a real analytical question at the end. Bounded.

```
Read tests/published_impacts/README.md and sdge_2026-04_tou_dr1.yaml, and the session 25
entry in SESSION_NOTES.md. Do not re-derive them.

Two jobs.

(1) SETTLE AN OPEN INFERENCE. The fixture records pcia_treatment: EXCLUDED_BY_INFERENCE.
SDG&E's "unbundled" customer is a CCA customer and pays the vintaged PCIA, but the
published $123 only matches with PCIA excluded ($143.43 with vintage 2026, $129.63 with
vintage 2009). Settle it with evidence, not argument: fetch SDG&E rate-change alerts for
several quarters, recompute against the spec effective on each date, and see whether
PCIA-excluded holds consistently. A single quarter cannot distinguish "they exclude PCIA"
from "coincidence". If you cannot settle it, say so plainly and record what would.

(2) GROW THE CORPUS. Fetch the other SDG&E rate-change alerts and PG&E electric rate
advisories you can find, one fixture per publication, same shape as the existing one.
Each rate change is an independent regression point.

Rules. Sources go in data/sources/ (gitignored). Extract with `pdftotext -layout` ONLY —
raw pdftotext destroys the column labels and makes the text useless as evidence; see
CLI-PLAN.md D5. PG&E's figures are a residential CLASS AVERAGE across every schedule and
territory, NOT reproducible from any single spec — fixture them for provenance, mark them
non-testable, and do not write an assertion against them.

Write findings to notes/published_impacts_corpus.md. Do NOT edit SESSION_NOTES.md or
HANDOFF.md; stream A owns those.
```

---

### STREAM C — CLI-PLAN phase C scaffolding (parallel-safe)
**Model: Sonnet 5 (`claude-sonnet-5`). Effort: high.**
Bash and config, no pricing path. Do not use Haiku — this stream's whole job is getting
permission-rule details exactly right, which is a precision task.

```
Read CLI-PLAN.md in full, especially the Rules, the Permissions findings, and decisions
D1-D5. The rules there are binding: do not write the project's algorithmic code, never run
`claude` yourself, and verify every flag and config key against
https://code.claude.com/docs/llms.txt before stating it — never from memory.

Build the parts of phase C that do NOT depend on the JSON schema (Cameron is writing that):

1. A validation wrapper script that takes a candidate YAML path and runs it through the
   repo's loader, exiting non-zero on failure. Phase A measured that `PYTHONPATH=src
   python ...` is NOT covered by `Bash(python *)` and that granting a general interpreter
   to an unattended run is the wrong shape — the whole point of the wrapper is that ONE
   command gets allowlisted instead.
2. The matching permission rule, verified against the docs.
3. A driver skeleton: bash loop over inputs, `claude -p` invocation, and the gate. The
   gate is exit code AND empty .permission_denials AND schema-valid .structured_output —
   phase A measured that is_error: false does NOT mean the task succeeded. Log session IDs
   so failures can be reopened with `claude --resume <id>`.
4. Leave the schema-shaped holes clearly marked TODO. Do not invent a schema.

Note: a `Write(path)` permission rule is accepted but NEVER consulted and warns at
startup; `Edit(path)` is the rule that governs the Write tool. Verify this yourself.

Write findings to notes/phase_c_scaffolding.md. Do NOT edit SESSION_NOTES.md or
HANDOFF.md; stream A owns those.
```

---

## Model and effort rationale

Verified against https://code.claude.com/docs/en/cli-reference.md this session:
`--model` takes `opus|sonnet|haiku|fable` or a full id; `--effort` takes
`low|medium|high|xhigh|max|ultracode`.

| Stream | Model | Effort | Why |
|---|---|---|---|
| A | Opus 5 | high | Pricing path + an invariant boundary a weaker model will blur. The failure mode is a test that passes for the wrong reason |
| B | Sonnet 5 | high | Fetch, extract, recompute. Bounded, verifiable, high volume. The analytical step at the end is narrow |
| C | Sonnet 5 | high | Bash and config. Precision task — not a Haiku job despite looking like one |

**Do not drop any of these to `low` or `medium`.** Every stream's failure mode is a
plausible-looking wrong answer rather than an obvious error, which is exactly what low
effort produces more of.

**Check whether fast mode is on before you start.** CLI-PLAN records that it doubles Opus 5
to $10/$50 per MTok, and that model and effort were silently coming from
`~/.claude/settings.json` rather than the command.

`xhigh` or `max` on stream A is defensible if the compute_bill integration turns out
fiddlier than expected — but start at high and escalate on evidence, not in advance.
