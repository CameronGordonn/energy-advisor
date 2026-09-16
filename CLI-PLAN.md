# CLI-PLAN — learning the Claude Code CLI against this repo

Cameron is learning the Claude Code CLI by wiring it into energy-advisor.
**This file is the resume point for a cold session.** Read with HANDOFF.md.

## Rules for the assistant

1. Don't write the project's algorithmic code. Scaffolding, config, fixtures OK.
   Prompts, schemas and scoring logic are Cameron's.
   > **⚠ OVERRIDDEN ONCE, 2026-09-16 (session 27), at Cameron's explicit request:** he asked
   > the assistant to write phase B's JSON schema and the `author-rate-spec` skill body.
   > Both are now committed. **The rule still stands for everything else** — scoring logic
   > (phase D) and the D2 span gate are still his. A future session should not read phase B
   > as licence to write phase D. The override was for two named artifacts, not the rule.
2. Don't run `claude` — Cameron runs every CLI exercise and pastes output back.
3. Verify every flag/config key against current docs before stating it. Index:
   `https://code.claude.com/docs/llms.txt`. Never answer from memory.
4. One step at a time. Give a step, say what to expect, stop.
5. No basic shell/git/Python explanation.

**Hard scope:** no model output goes near bill arithmetic. Generated YAML is a
candidate until a human diffs it against the source.

---

## The goal

Generate tariff spec YAML from published rate sheets, headlessly, with a scoring
loop that says whether it worked.

## Phases

- [x] **A — finish the CLI surface.** Done except `--bare`, DEFERRED: it needs a Console
      `ANTHROPIC_API_KEY` (bare never reads OAuth). Findings under "Permissions" below.
- [x] **B — write the schema + prompt, as a skill.** `.claude/skills/author-rate-spec/`:
      `SKILL.md` (body) + `extraction-schema.json`. Committed beside the skill, **not** in
      `build/` — that is gitignored, and a contract that vanishes on a fresh clone is not
      one. `tests/tariffs/test_extraction_schema.py` (14 tests) pins that the schema accepts
      a committed spec re-expressed as an extraction and rejects each of D2-D4's gaps.
      **Never run against a model** — rule 2 — so every claim about it is structural.
      A skill is the one artifact that works interactively *and* in `-p`, and survives
      `--bare` via `--add-dir` (custom commands do not).
- [ ] **C — driver script + calibration.** Bash loop over inputs. **Calibrate against
      an already-authored spec** (CEA or 3CE) re-derived from its cited source and
      diffed against the committed file — the only corpus with ground truth. Diff the
      parsed pydantic object, not file bytes (those specs are mostly human commentary).
      **Done when:** one spec generated end to end and passes schema validation.
- [ ] **D — scoring loop.** Gate tests + reconciliation harness, pass rate per spec and
      per field, compare models and prompt variants.
- [ ] **E — later.** Hooks (PostToolUse ruff + pytest subset), local MCP server over
      interval data, subagents + the prose explanation layer.

**Targets, once calibrated:** MCE, Ava, SVCE, Peninsula, SJCE; PG&E baseline table.
**Not in scope, any phase:** the optimizer customer-facts fix, or anything else in the
deterministic pricing path.

---

## Settled decisions

### D1 — `schedule_id` convention for new CCA generation specs: BARE (2026-09-15)

New specs use the **utility's own schedule id** in `schedule_id` (`E-TOU-C`), with the
supplier in `provider` (`MCE`, `SVCE`, ...). Not the namespaced form (`MCE-E-TOU-C`).

**Why.** Under the namespaced form `schedule_id` is a string the model must *invent* —
and the existing "convention" is not one: `MBRETCH1` is 3CE's real product name off its
rate sheet, `3CE-E-TOU-D` is synthetic, `PGE-BUNDLED-E-TOU-C` is a third pattern, so
there is no rule a generator could follow. Under the bare form it is *transcribed* from
the source document and can be checked against it. For a pipeline whose whole risk
surface is hallucinated content that passes validation, a generated identifier is the
one field with nothing to check it against.
Secondary: it makes `schedule_id` mean exactly one thing (the utility schedule this
layer prices) and lets the loader's `AmbiguousProviderError` do its job — the same
raise-don't-default philosophy as `territory`, `vintage`, `event_days` and `service`.

**Existing specs are NOT migrated.** Migration would mean editing all 11 golden-bill
fixtures (each names `generation: MBRETCH1`) and the 8 `Candidate` tuples in
`src/scenarios/rate_optimizer.py`, for zero functional gain today, on the reconciled
path. Take the split deliberately.

**Consequences, accepted.**
- The repo carries two conventions. **Pin it with a test** asserting which files use
  which, so it is a recorded decision and not drift.
- `load_specs("E-TOU-C", GENERATION)` finds nothing today. Under D1 the first bare CCA
  spec makes it resolve, and the second makes it raise correctly — but PG&E-bundled and
  3CE stay invisible to that lookup. So there is no single lookup enumerating every
  supplier of a PG&E schedule's generation, which is what the optimizer's candidate set
  will want beyond Santa Cruz. Argues for migrating eventually, by hand, deliberately —
  never as part of this pipeline.
- `reconcile.py` already threads an optional `generation_provider` into
  `load_spec_versions` (lines 344, 348), so the harness supports this today.

### D2 — provenance in the extraction schema: prose + a checkable span (2026-09-15)

The extraction object emits **two** provenance fields per component:
`citation` (prose, repo's existing style, goes into the YAML) and `evidence`
(a verbatim span from the source plus its locator, consumed by the driver's gate
and then **dropped**). The driver asserts two things mechanically: the span occurs
in the source text, and the emitted numeric rate occurs inside that span.

**Why.** A wrong rate fails reconciliation eventually; a wrong citation fails nothing,
ever — it is the only one of the three schema gaps with no downstream detector, and
CLAUDE.md makes citation the validity condition for a spec existing at all. A regex on
a free-form citation string constrains form, not content: a model that invents a rate
invents a conforming citation just as cheaply. A verbatim span is the first check in
this pipeline that does not route through the model's own judgment.

**`evidence` stays OUT of the committed spec.** Adding it to `schema.py` would make
provenance machine-checkable forever, but it is an edit to reconciled specs that 11
golden bills flow through. Rejected for now on the same grounds as D1's no-migration.

**Consequences, accepted.**
- Requires source text on disk. There is none today — getting it is a Phase C
  prerequisite, not an afterthought.
- Self-reported span != API-enforced span. The model chooses the text it will be graded
  on. This is weaker than the Citations API's `cited_text`, and it is one pass instead
  of two. Take the weaker check for now; the open citations-vs-structured-output
  question stays open.
- Granularity is per-component (`PerKwhAdder`, `Surcharge`, ... each carry their own),
  so token cost scales with the number of line items.

**Also found, correcting this file's earlier note.** `PerKwhAdder.citation` (schema.py:422)
and `Surcharge.citation` (schema.py:545) are bare `str` with **no `min_length`** — the
empty string loads clean on both. Every other citation field has `min_length=1`. Those two
are the long-tail line items the generator transcribes most.

### D3 — seasons are emitted as a 12-key map, not two arrays (2026-09-15)

The extraction object emits `month_to_season`: an object whose `required` list is all
twelve month keys, each value `enum: [summer, winter]`. The driver converts it to
`summer_months` / `winter_months` for the YAML.

**Why.** `SeasonDef` (schema.py:93-94) validates only that each array is non-empty and
in 1..12. It does not check the two for disjointness or completeness, and the two
failure modes are not equally visible:
- **A month in neither: loud but late.** `season_for` raises at *bill* time, and only if
  a billing period touches that month. Calibrating on a September bill with a hole in
  March passes clean.
- **A month in both: silent forever.** `season_for` tests summer first and returns, so
  the month prices at summer — the expensive season. No exception, ever, just a wrong bill.

JSON Schema has no cross-field arithmetic, so "these two arrays partition 1..12" is not
expressible. Under the 12-key map both failures become unrepresentable: `required`
enforces completeness, a single scalar value enforces disjointness.

Rejected: emitting `summer_months` only and deriving winter as the complement. Also makes
both failures impossible and costs fewer tokens, but it hides which boundary the model
actually read — a misread summer start silently moves winter's end with it. The 12-key
form forces twelve independent decisions that diff against the sheet line by line.

**Generalized:** prefer an output shape in which the bad value cannot be expressed over a
valid-looking value checked afterwards. A driver check costs a retry; a shape costs nothing.

**Caveat.** Shape constraints bind the structured pass only. Per the phase-A finding that
`.result` and `.structured_output` are two separate generations, they do not stop a value
from drifting during that transcription. Calibration still diffs the two.


### D4 — rate magnitude: generous per-site bounds, with the real check in D2 (2026-09-15)

`Rate` (schema.py:255) is `standard: float | None` / `care: float | None`, unbounded, and
the **same class is reused at every site**. The extraction schema does not mirror that: it
bounds each use site separately, because a shared `$ref` cannot be bounded correctly.

**Measured across the 30 committed specs** (476 energy values, zero negative, zero zero):

| field | n | min | max |
|---|---|---|---|
| `energy` (delivery) | 212 | 0.01828 | 0.62569 |
| `energy` (generation) | 260 | 0.01 | 0.55397 |
| `fixed_per_day` | 38 | 0.19713 | 0.79343 |
| adder `per_kwh_by_vintage` | 90 | 0.014 | 0.05055 |
| `surcharge.per_kwh` | 4 | 0.00059 | 0.00059 |

**A blanket `exclusiveMinimum: 0` would reject real cited data.** `sdge_tou_dr1_delivery`
carries `Nuclear Decommissioning: 0.0` and `Competition Transition Charge: -7e-05` under
`non_bypassable.components`. Zero and negative are legitimate there and only there.

**Bounds are generous — 10x observed headroom, not tight.** Energy `[0.005, 2.0]`,
`fixed_per_day` `[0.01, 5.0]`, vintage adders `[0, 1]`, NBC components `[-1, 1]`. Tight
bounds inferred from 2026 data are a trap: CA rates climb, and a spec failing validation
because a real tariff outgrew an inferred bound is worse than the error it prevents. These
catch order-of-magnitude errors and nothing else, which is the whole job.

**The failure mode is decimal shift, not sign.** `0.55397` -> `5.5397` or `0.055397` both
pass pydantic; one is a 10x bill. The check with teeth is **D2's span check**, not the
bounds: `5.5397` does not occur in a source span containing `0.55397`, so comparing literal
digit strings catches it outright. Bounds are the cheap structural guard that costs no
retry. Gap 3 is mostly closed by D2.

**Same family, also closed here.** A `Rate` with both `standard` and `care` null is
representable and loads clean, raising at *bill* time — the same late-failure signature as
D3's season hole. Closed with an `anyOf` requiring at least one of the two.


### D5 — the extraction contract: `-layout`, text not PDF, floats not strings (2026-09-15)

Sources live in `data/sources/` (gitignored twice over: `data/` and `*.pdf`). Each is
extracted with **`pdftotext -layout`**, and **the model reads the `.layout.txt`, never
the PDF**. The driver greps that same file. Measured, not assumed:

**1. `-layout` is mandatory. Raw `pdftotext` destroys the evidence.** Same CEA row:

    layout:  TOU-DR-1    On-Peak    $0.55397    $0.19791
    raw:     $0.55397

Raw preserves the value and drops every label, serializing the summer and winter columns
into separate runs of bare numbers (4241 bytes vs 8851 — it deletes labels, not whitespace).
A raw span passes a containment check while proving nothing.

**2. D2's span check therefore has a second requirement: the span must carry the label.**
Containment of the number alone is not evidence. On a `-layout` row the natural span is the
whole line, which binds schedule + period + season-column + value at once. The 3CE sheet is
better still — its row block carries the season months and the TOU hours inline:

    E-TOU-D                          Summer - June through September; Winter - October through May
      ENERGY CHARGE ($/KWH)   SUMMER PEAK      0.19419  0.20219   5pm to 8pm, Monday - Friday
                             SUMMER OFF-PEAK   0.09028  0.09828   All other times including holidays

So one span can ground the rate, its season, its period and its hours together.

**3. Compare parsed floats, NOT literal digit strings.** The committed 3CE spec holds
`winter_offpeak: 0.119`; the sheet prints `0.11900`. A strict string equality check fails
on a correct value. A naive substring check passes here by luck and would also accept a
model emitting `0.1190`. The gate must tokenize numbers out of the span and compare
numerically.

**4. The model must read the same bytes the driver greps.** If the model reads the PDF and
the driver greps the text extraction, they disagree on whitespace, hyphenation and column
order, and the gate fails ~100% of the time — teaching nothing. Extraction is a pipeline
step and a calibration variable, not setup.

**Provenance finding, unprompted by any of this.** The committed 3CE citation names
`PGE-Residential-Website-Rate-Sheet-2026.02.15_with3Cflex.pdf`. **That URL 404s.** The live
sheet for that effective date is `...-v29-2026.02.15.pdf`, and all four committed E-TOU-D
rates reproduce from it exactly. So the numbers are right and the citation points at a
document that is not retrievable — which is precisely the failure mode D2 exists to catch,
found in a hand-authored spec before the generator wrote a line.

**SCE: no source obtainable, target dropped for now.** `library.sce.com`, which hosts the
tariff books, does not resolve from this environment. The one reachable SCE PDF
(`Summary_of_Available_Residential_and_Nonresidential_Rate_Options.pdf`) contains **zero**
per-kWh figures — prose rate descriptions only, nothing to extract. Separately, SCE is out
of scope per CLAUDE.md (SDG&E first, PG&E second) and has no committed spec, so it offers
no calibration signal even if fetched. Revisit only as a post-calibration generalization
test. **Real SCE bills are customer data and are not obtainable by fetching.**


---

## What we learned (don't re-derive)

### The repo's spec contract

- Contract is `src/tariffs/schema.py` (pydantic, frozen, `extra="forbid"`) +
  `loader.py` (UNVERIFIED gate, provider disambiguation).
- **The schema enforces structure thoroughly and content not at all.** Caught loudly:
  unknown field names, unknown `holiday_calendar`, literal `UNVERIFIED`, and
  `_energy_keys_cover_seasons_and_periods` (energy keys must exactly cover
  season × `tou.periods`). Confirmed NOT caught, by probe:
  1. `citation: "x"` loads clean — any non-empty string passes.
  2. Seasons need not be disjoint or complete; a month in neither raises at *bill* time.
  3. Rates have no bounds — `5.5397`, `0.0`, `-9.9` all load as energy rates.
  That gap is what the JSON schema must close; shape is already covered by pydantic.
- **Unit of work is (CCA × utility schedule), not per CCA.** A CCA generation spec must
  classify every hour identically to the delivery layer it rides on. 3CE is 4 files.
- **Two `schedule_id` conventions exist — pick one before writing the schema.**
  PG&E-territory generation namespaces it (`3CE-E-TOU-D`); SDG&E-territory keeps the
  bare id (`TOU-DR1`) and disambiguates on `provider`. Adding a bare-id spec makes every
  unqualified lookup for that schedule raise.
- **PG&E's baseline table is an edit to reconciled specs**, not a new file — the 11
  golden bills flow through `pge_etou_c_delivery_*.yaml`. Emit to a standalone file for
  human diffing. Free regression check: the generated Territory T row must reproduce
  7.1 / 12.9.
- **3CE's Santa Cruz UUT is a location fact in a generation spec.** Don't let it be
  copied to five other CCAs.
- No source documents on disk. `data/*.pdf` are the 11 real PG&E bills.

### The CLI

- **Two failure channels, one exit code.** Flags rejected before the run → stderr,
  non-zero. Failures inside the run → printed as the result on stdout, exit 0. Check
  `$?` *and* `.is_error`.
- **`--json-schema` is a forced `StructuredOutput` tool call appended after the prose
  answer.** So `.result` and `.structured_output` are two separate generations and the
  second transcribes the first — diff them while calibrating, because that's where a
  six-decimal rate can get rounded.
- **Prompt specificity is the cost control.** Same input, same model: specific prompt =
  1 turn / $0.07; vague prompt + schema = 4 turns / $0.39; vague prompt, no schema =
  6 turns. A schema partially compensates for a vague prompt rather than taxing it.
- **Pin what you depend on.** Model and effort came from `~/.claude/settings.json`
  (`opus`, `high`), not from the command. Fast mode may also be on — doubles Opus 5 to
  $10/$50 per MTok. Same class of bug as CLAUDE.md loading silently.
- **Prompt caching confounds benchmarking.** Step 2 read a 28.8k cache created by
  step 1 (`input_tokens: 2`), so it ran 7s vs 19s. Warm every variant before measuring.
- `CLAUDE.md` is loaded unconditionally; the HANDOFF/SESSION_NOTES reads it instructs
  are an action the model may or may not take (it did not). Measured: `num_turns: 1`.
- **Hybrid bridge:** `-p` sessions are excluded from the picker and `--continue`, but
  `claude --resume <session-id>` opens one interactively. Log session IDs in the driver
  script; open the failures.

### Permissions (measured, phase A)

- **`PYTHONPATH=src python ...` — this repo's documented invocation — is NOT covered by
  `Bash(python *)`.** Only a fixed known-safe set of env assignments is stripped before
  an allow rule is matched, and `PYTHONPATH` is not in it.
- **An allow rule may name the assignment and it matches literally**:
  `Bash(PYTHONPATH=src python *)` works. Brittle — coupled to that exact string, so
  `PYTHONPATH=/abs/path/src` needs its own rule.
- **`export PYTHONPATH=src` + `Bash(python *)` is the clean form** — zero denials.
- **Absolute interpreter paths never match** a rule written against the bare program
  name, assignment or not.
- **Conclusion for the driver script:** wrap validation in a shell script and allow that
  one command. Never grant a general interpreter to an unattended run.
- **Denials are expensive and the two flags do different jobs.** Same blocked task:
  bare = 12 turns / 6 denials; `--permission-mode dontAsk` = 8 turns / $0.46;
  `--permission-prompts none` = 6 turns / $0.20. `dontAsk` sets the security posture
  (auto-deny anything that would prompt); `--permission-prompts none` is what tells
  Claude nobody can approve *and not to retry*, so it is the one that saves money. Use
  both, plus `--max-turns` as a hard stop.
- **`is_error: false` does NOT mean the task succeeded.** A run with six denials that
  executed nothing still reported `exit 0` and `is_error: false`. The driver script's
  gate is: exit code + `.permission_denials` empty + schema-valid `.structured_output`.
- A run asked to verify-by-executing, with execution denied, declined to fake it by
  reading the file — correct, but a behavioral tendency, not an enforced property.
  Do not build a pipeline that depends on it.

### CLI vs API

The extraction step is **not agentic** — single call, no tools. ~19k of a 29k-token
context was system prompt + tool definitions for a loop that made zero tool calls.

- Cost is NOT the reason to move it to the API (~$21 for 20 specs × 15 variants).
  Determinism is, and so is this:
- **Document citations and `output_config.format` are mutually exclusive (400).**
  Citations return `page_location` + `cited_text` — the only mechanism that turns this
  repo's `citation` field from a string into evidence. So grounding and structured
  output are two passes, not one. Design decision still open.
- Batch API is 50% and async; the schema + few-shot specs are a stable cacheable prefix.
- Likely end state: Claude Code wraps the agentic parts (fetch source, run the loader,
  iterate on validation errors); a plain API call does the extraction.

---

## Session log

_Newest first. Append, do not rewrite._

### Session 3 — 2026-09-16

- **Phase B done, at Cameron's request and against rule 1** — see the override note in Rules.
  `extraction-schema.json` + the `SKILL.md` body. Rule 2 still held: `claude` was never run,
  so **nothing here is measured against a model.** Every claim below is structural.
- **The schema lives beside the skill, not in `build/`.** The driver's placeholder pointed at
  `build/schema.json`, which is gitignored — a designed contract that disappears on a fresh
  clone. Schema and prompt are one artifact: the schema constrains shape, the body carries
  the rules a shape cannot express.
- **D3's shape argument generalised into the schema's design and was then tested.**
  `month_to_season` makes both season failures unrepresentable; `energy` is keyed period →
  season with `required: [summer, winter]`, so a dropped winter column is impossible; `anyOf`
  kills the both-null `Rate`. Each has a test that breaks it deliberately.
- ⭐ **A test that records what the schema CANNOT do.** `0.45397` in place of `0.55397` — wrong
  by ten cents a kWh — validates cleanly, because it is an ordinary California rate. Asserted
  as passing, with the reason, so nobody mistakes the schema for a correctness check. D4
  argued this; now it fails a build if it stops being true.
- **A near-miss worth recording: `exclusiveMinimum: 0` on adders would have rejected the
  repo's own ground truth.** CEA's Rate Relief Credit is `-0.03871`/kWh. D4 flagged zero and
  negative as legitimate in `non_bypassable.components`; it did not mention adders. Found by
  building the ground-truth fixture first and validating against it, which is why that test
  is written before the constraint tests rather than after.
- **TODO #3 dissolved rather than being built.** The driver was going to convert
  `structured_output` into candidate YAML. But the skill's frontmatter already granted
  `Edit(build/candidates/**)` — so the skill writes the YAML itself and returns the structured
  object, and one run produces both. A missing candidate file is now a FAIL, not a SKIP.
- **Still open, and it is the one with teeth: the D2 span gate.** Nothing yet asserts that an
  `evidence.span` occurs verbatim in the source and contains the emitted number. Per D5 it
  must compare numbers **numerically**, not as strings (`0.119` vs a printed `0.11900`).
- **The prompt bets on specificity**, per phase A's cost finding (specific = 1 turn/$0.07;
  vague + schema = 4 turns/$0.39). Unmeasured here — the first real run is the first evidence.

### Session 2 — 2026-09-15
- Scaffolded `.claude/skills/author-rate-spec/SKILL.md` — frontmatter only, body is Cameron's.
  Every key verified against the docs this session: `disable-model-invocation` (explicit
  invocation only; docs confirm `/skill-name` expands inside a `-p` prompt string),
  `arguments: source schedule provider`, `allowed-tools: Read, Edit(build/candidates/**)`,
  `model: inherit`, `effort` deliberately unset so `--model`/`--effort` stay sweepable
  from the command in phase D. No `context: fork` — a forked skill's result adds a
  summarization layer between transcription and `.structured_output`.
- **Verified CLI facts added this session:**
  - A `Write(path)` permission rule is accepted but **never consulted**, and warns at
    startup. `Edit(path)` is the rule that governs the Write tool, including file creation.
    Gitignore syntax; `/path` anchors at the settings source, `//path` is absolute.
  - `--json-schema` accepts `format` but treats it as an **annotation, not a constraint**.
    Any shape rule must be `pattern`.
  - `--effort` is a real CLI flag: `low|medium|high|xhigh|max|ultracode`.
  - `build/` is already gitignored, so generated candidates land outside git by construction.
- **Walked the three schema gaps and settled them: D2 (citation), D3 (seasons), D4 (rates).**
  Net: gap 1 is the only one with no downstream detector and it drove the design; gaps 2
  and 3 both reduce to "choose a shape where the bad value is unrepresentable"; and D2's
  span check turns out to close most of gap 3 for free.
- **Reordering considered and rejected.** Offered: run a thin end-to-end CLI pass with a
  throwaway schema first, then design against real failures instead of hypotheses. Cameron
  chose to finish the schema design first. The three gaps therefore remain **hypotheses
  about what a generator gets wrong** — nobody has measured them. Phase C calibration is
  the first evidence; expect to revise D2-D4 against it.
- Fetched the two calibration sources into `data/sources/` (CEA 2026-06-01, 3CE v29
  2026-02-15) and verified the ground truth reproduces: **all 6 committed CEA rates and
  all 4 committed 3CE E-TOU-D rates appear verbatim in the `-layout` text.** D2's span
  check is viable on both documents. Settled **D5** (extraction contract) from that work,
  and found the 3CE citation's PDF URL 404s.
- SCE investigated and dropped — see D5. No fetchable document with rates in it.
- Noted: phase B is the one stretch of this plan where the CLI is not the point. The skill
  and schema work identically invoked interactively. The CLI becomes load-bearing at C/D
  (unattended permissions, exit-code gating, `.permission_denials`, session resume, model
  and prompt sweeps).

### Session 1 — 2026-09-15
- Read the repo; wrote this plan; installed the standalone CLI (was VS Code extension
  only, no `claude` on PATH — don't symlink the extension's bundled binary).
- Ran steps 1–4: `-p` + stdin, `--output-format json`, `--json-schema`, `stream-json`.
  All findings above are measured, not assumed.
- Corrected two wrong predictions: CLAUDE.md did not trigger the big-file reads, and
  `--json-schema` reduces turns rather than adding them.
- Phase A complete but for `--bare`. Steps 5-7 measured the permission surface; see
  "Permissions" above.
- **Decided: D1, bare `schedule_id` + `provider`.** See "Settled decisions".
- Open: Console API key for `--bare`; whether grounding is a
  second citations pass; which source documents exist for the five CCAs.
