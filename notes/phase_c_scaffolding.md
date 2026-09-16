# Phase C scaffolding — validation wrapper, permission rule, driver skeleton

Written 2026-09-15, stream C of `notes/session25_handoff_prompts.md`. Scope was fixed by
that prompt: build the parts of CLI-PLAN.md phase C that don't depend on the JSON schema
(Cameron's, per rule 1), verify every CLI/permission fact against the docs rather than
memory (rule 3), and never run `claude` (rule 2). Findings only — SESSION_NOTES.md and
HANDOFF.md are stream A's, untouched here.

## What exists now

- `scripts/validate_spec.py` — thin wrapper around `tariffs.loader.load_spec_file`.
  Exit 0 + a one-line summary on a schema-valid spec; exit 1 + the loader's own exception
  message on anything else (missing file, bad YAML, an `UNVERIFIED` field, a pydantic
  validation error). Follows `scripts/inspect_export.py`'s existing convention
  (`sys.path.insert(...,"src")` before the first-party import) rather than depending on
  `PYTHONPATH` — so the wrapper's own Python half needs no environment variable at all.
- `scripts/validate_spec.sh` — the one command an unattended run allowlists. Takes a
  candidate YAML path, execs the script above, nothing else.
- `.claude/settings.json` (new file, project-level, committed — no
  `settings.local.json` existed to put a personal-only rule in instead):
  ```json
  { "permissions": { "allow": ["Bash(scripts/validate_spec.sh *)"] } }
  ```
- `scripts/rate_spec_driver.sh` — phase C driver skeleton. Loops `(source, schedule_id,
  provider)` triples, invokes `claude -p "/author-rate-spec ..."` headlessly, gates the
  result, logs `session_id` → outcome to `build/logs/sessions.tsv`. Four TODO(cameron)
  markers in its header, in blocking order: the schema file, the skill body, the
  `structured_output` → candidate-YAML conversion, and the calibration diff. None of
  those are guessed at — see "What is deliberately not here" below.

## Why a wrapper script at all — the finding this executes on

CLI-PLAN.md's Permissions section (session 1) measured that `PYTHONPATH=src python ...`
— this repo's own documented invocation — is **not** matched by a `Bash(python *)` allow
rule, and separately that granting a general `python *` allow rule to an unattended run
is the wrong shape regardless (it would let a misbehaving run execute anything, not just
the validation step). A wrapper script collapses both problems: Claude's permission check
only ever sees `scripts/validate_spec.sh <path>`, a single exact-prefix-matchable command,
and never sees (so never needs a rule for) the `python3` call inside it — that call runs
as ordinary shell execution once the outer command is already approved, the same way `git
commit`'s hooks or `make`'s recipe lines aren't separately permission-checked.

## Verified against the docs (rule 3) — not from memory

Fetched 2026-09-15: `cli-reference.md`, `permissions.md`, `headless.md`, `skills.md`, all
under `https://code.claude.com/docs/en/`. Specific facts the scripts and settings file
depend on, and where each is confirmed:

- **The exact claim stream C asked me to re-verify**: "Claude Code checks file
  permissions against `Edit(path)` and `Read(path)` rules only. If you write a path rule
  for `Write`, ... Claude Code accepts the rule but never consults it, and warns at
  startup" — `permissions.md`, verbatim. Confirms CLI-PLAN.md's session-1 finding exactly;
  no scaffolding here uses a `Write(...)` rule as a result.
- **Bash rule syntax**: `Tool(specifier)`, parentheses literal, `*` for prefix matching,
  a trailing `*` with a preceding space also matches the bare command
  (`Bash(scripts/validate_spec.sh *)` matches both the bare script and any argument
  list) — `permissions.md` § Permission rule syntax.
- **Env-var stripping**: "Claude Code strips a leading assignment of certain known-safe
  environment variables, so `Bash(npm test *)` matches `NODE_ENV=test npm test`. An
  allow rule won't match past an assignment of any other variable" — `permissions.md`.
  `PYTHONPATH` is not documented as one of the known-safe set, consistent with CLI-PLAN's
  measurement that `Bash(python *)` doesn't cover `PYTHONPATH=src python ...`. This is
  exactly the gap the wrapper script sidesteps rather than tests for.
- **`-p` + skills**: "User-invoked skills and custom commands work in `-p` mode: include
  `/skill-name` in the prompt string and Claude Code expands it before running" —
  `headless.md`, verbatim. Confirms the driver's
  `claude -p "/author-rate-spec $source $schedule $provider"` form.
- **`--json-schema` / `structured_output`**: "the response includes ... the structured
  output in the `structured_output` field" — `headless.md`, with the accompanying `jq`
  example the driver's extraction follows.
- **`--permission-prompts none`**: "Claude Code denies [prompts] unless a
  `PermissionRequest` hook allows it, ... and the flag also tells Claude not to retry ...
  denials appear ... the final result message lists them in `permission_denials`" —
  `headless.md`. Requires Claude Code v2.1.259+, stated there; not otherwise checked.
- **`--permission-mode dontAsk`**: "denies every call that would otherwise prompt" —
  `headless.md`. Using it alongside `--permission-prompts none` (as the driver does)
  matches CLI-PLAN's own phase-A cost measurement (both together beat either alone) and
  is not contradicted by anything in the two flags' separate doc entries — they compose
  rather than conflict.
- **`--add-dir` is a `--bare` concern, not a plain `-p` one**: "A directory you name with
  `--add-dir` is a partial exception [for] bare mode" — `headless.md`. The driver does
  NOT pass `--add-dir`; the skill lives in this repo's own `.claude/skills/`, which a
  non-bare `-p` session loads the ordinary way. Flagging this because an earlier draft of
  this scaffolding assumed `--add-dir` was needed unconditionally and that assumption
  didn't survive reading the doc page.
- **Exit code is not the gate**: nothing new here — CLI-PLAN.md's own phase-A measurement
  ("`is_error: false` does NOT mean the task succeeded ... six denials ... still reported
  exit 0") is why the driver reads `is_error` / `permission_denials` / `structured_output`
  from the JSON body rather than `$?`. Re-confirmed, not re-discovered.

## A real bug the mock harness caught

Rule 2 forbids running `claude` here, so the driver's gate logic (not the skill, not the
model call) was tested against a **stubbed** `claude` binary on `$PATH` that prints
canned JSON for `*CEA*` / `*3CE*` / anything else, run from a scratch copy of the repo
tree so nothing under version control was touched. This is not a substitute for a real
run — it can't be, there's no schema and no skill body yet — but it is the only way to
find a bug in bash/jq plumbing that never talks to the model.

It found one: `is_error="$(jq -r '.is_error // true' "$run_log")"` is wrong. jq's `//`
treats `false` the same as `null` — "falls through" on both — so a genuine
`"is_error": false` was silently read back as `true`, and every successful run would
have been misreported as failed. Fixed to
`jq -r 'if .is_error == null then true else .is_error end'`, which only substitutes the
safe default when the key is truly absent. Re-verified against the mock afterward: PASS
(valid spec present), FAIL×2 (permission-denied JSON, and a deliberately-broken candidate
YAML), SKIP (structured output present, no candidate YAML yet — the honest state today),
and the invalid-JSON path (mock exits 1 with a non-JSON stdout). All five outcomes landed
in `sessions.tsv` with the right `session_id` and label.

`scripts/validate_spec.sh`/`.py` were separately run for real (no mock needed — they
don't touch `claude`) against a committed spec (pass), a missing file (fail, exit 1), and
a spec with a value forced to `UNVERIFIED` (fail, exit 1, names the field). `ruff check`
and `ruff format --check` pass on `validate_spec.py`.

## What is deliberately not here (rule 1, and CLI-PLAN's own "Done when")

- **No JSON Schema.** `rate_spec_driver.sh` reads `build/schema.json` and refuses to run
  at all if it's missing/empty — a hard stop with a named reason, not a driver that
  invents a schema to have something to pass to `--json-schema`.
- **No skill body.** `.claude/skills/author-rate-spec/SKILL.md` is still the
  frontmatter-only file from session 2; not touched here.
- **No `structured_output` → spec-YAML conversion.** `--json-schema` validates the
  *extraction object* (D2's citation+evidence, D3's 12-key season map, D4's rate bounds);
  turning that object into the repo's actual spec YAML shape is itself schema-shaped and
  is marked TODO rather than guessed. Until it exists, the driver SKIPs the
  `validate_spec.sh` step for a given input rather than fabricate a YAML to pass it —
  a driver that invents a candidate spec to make its own gate go green would be exactly
  the failure CLAUDE.md's reconciliation-gated invariant exists to catch, just one layer
  removed.
- **No calibration diff.** CLI-PLAN.md phase C's own "Done when" line is "one spec
  generated end to end and passes schema validation" — schema validity, not a ground-truth
  match. The diff against a committed spec (CEA or 3CE, "parsed pydantic object, not file
  bytes") is real work but it's scoring logic, which rule 1 reserves and which CLI-PLAN's
  own phase list puts in **D**, not C.

## The calibration input list, and a naming mismatch worth knowing before touching it

`INPUTS` in the driver has two rows, matching the two sources D5 already fetched and the
two schedules with committed ground truth:

| source | schedule_id (new, D1-bare) | provider (new) | ground truth |
|---|---|---|---|
| `cea_residential_2026-06-01.layout.txt` | `TOU-DR1` | `CEA` | `src/tariffs/specs/cea_tou_dr1_generation_2026-06-01.yaml` — already D1-bare, matches directly |
| `cce_pge_residential_2026-02-15_v29.layout.txt` | `E-TOU-D` | `3CE` | `src/tariffs/specs/cce_etou_d_generation_2026-02-15.yaml` — `schedule_id: 3CE-E-TOU-D`, `provider: Central Coast Community Energy (3CE)` |

The second row's generated identifiers will **not** string-match the committed file's —
that file predates D1 and, per D1's decision, existing specs are not being migrated.
Whatever eventually writes the calibration diff has to know both conventions (or the
committed 3CE-family specs need the deliberate, human-driven migration D1 already flagged
as future work). Recording this now so it isn't rediscovered as a mystery "the generated
spec doesn't match anything" failure later — it's known, expected drift, not a generator
bug.

## One more thing worth flagging rather than fixing silently

`scripts/rate_spec_driver.sh` is a **skeleton**: it has never executed a real `claude`
call (rule 2), so nothing about the actual skill invocation string, the real shape of
`--json-schema`'s output for this schema, or how long a real extraction run takes under
`--max-turns 8` has been observed. Treat the flag choices above as doc-verified, not
field-verified — the first real run is also the first test of whether `MAX_TURNS=8` is
enough headroom, and that number should move on evidence exactly the way CLI-PLAN's own
model/effort table says to.
