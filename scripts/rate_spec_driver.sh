#!/usr/bin/env bash
# CLI-PLAN.md phase C driver SKELETON. Loops the author-rate-spec skill over a list of
# (source, schedule_id, provider) inputs, headlessly, and gates each result.
#
# Cameron runs this — CLI-PLAN.md rule 2 ("Don't run `claude` — Cameron runs every CLI
# exercise and pastes output back") is why this script is written, not executed, here.
#
# TODO(cameron), in the order they block a real run:
#   1. JSON_SCHEMA_FILE (below) — phase B's schema. This script refuses to run without it
#      rather than silently calling `claude` with no schema (CLI-PLAN.md rule 1: schemas
#      are yours; a driver that guesses one would be inventing the thing rule 1 reserves).
#   2. The author-rate-spec SKILL.md body — currently a TODO placeholder itself.
#   3. structured_output -> build/candidates/<name>.yaml. `--json-schema` validates the
#      extraction OBJECT (CLI-PLAN.md D2-D5's citation/evidence/month_to_season/Rate
#      shape); turning that object into the repo's spec YAML is schema-shaped work, so it
#      isn't done here. Until it exists this script SKIPs the validate_spec.sh step rather
#      than fabricate a YAML to pass it.
#   4. The calibration diff (parsed pydantic object vs. the committed ground-truth spec,
#      per CLI-PLAN.md phase C — "diff the parsed object, not file bytes") is scoring
#      logic (rule 1) and belongs in phase D's scoring loop, not here. What this script
#      calls a PASS is schema validity only, per its own "Done when" line in CLI-PLAN.md.
#
# Verified against https://code.claude.com/docs/en/headless.md and
# https://code.claude.com/docs/en/cli-reference.md (2026-09-15) — see
# notes/phase_c_scaffolding.md for what was checked and why each flag is here.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_ROOT/build/logs"
CANDIDATES_DIR="$REPO_ROOT/build/candidates"
SESSION_INDEX="$LOG_DIR/sessions.tsv"
mkdir -p "$LOG_DIR" "$CANDIDATES_DIR"

# TODO(cameron): phase B's JSON Schema for the extraction object (D2-D5) lands here.
JSON_SCHEMA_FILE="$REPO_ROOT/build/schema.json"

MAX_TURNS=8

# One line per (source .layout.txt, schedule_id, provider), space-separated — matches
# author-rate-spec's `argument-hint: <source-layout-txt> <schedule-id> <provider>`.
# The two rows below are the phase-C calibration targets CLI-PLAN.md names (an
# already-authored spec re-derived from its own cited source): committed ground truth
# already exists for both, at src/tariffs/specs/cea_tou_dr1_generation_2026-06-01.yaml
# and (D1: pre-migration, namespaced) src/tariffs/specs/cce_etou_d_generation_2026-02-15.yaml
# — schedule_id 3CE-E-TOU-D, provider "Central Coast Community Energy (3CE)" in that file.
# `schedule_id`/`provider` below follow D1's BARE convention for newly generated specs —
# "E-TOU-D" / "3CE" here will NOT string-match the pre-D1 file's namespaced `schedule_id`
# or full provider name. Known, accepted consequence of D1 ("existing specs are NOT
# migrated"), not a bug in this list — whatever eventually diffs the two (TODO #4) has to
# know both conventions.
INPUTS=(
  "data/sources/cea_residential_2026-06-01.layout.txt TOU-DR1 CEA"
  "data/sources/cce_pge_residential_2026-02-15_v29.layout.txt E-TOU-D 3CE"
)

if [[ ! -s "$JSON_SCHEMA_FILE" ]]; then
  echo "no schema at $JSON_SCHEMA_FILE — phase B is not done; refusing to run headless" >&2
  echo "(this is TODO(cameron) #1 in this script's header, not a bug)" >&2
  exit 1
fi
JSON_SCHEMA="$(cat "$JSON_SCHEMA_FILE")"

overall_fail=0

for input in "${INPUTS[@]}"; do
  read -r source schedule provider <<<"$input"
  name="$(basename "$source" .layout.txt)__${schedule}__${provider}"
  run_log="$LOG_DIR/${name}.json"

  echo "=== $name ==="

  # --permission-mode dontAsk denies everything that would otherwise prompt (the security
  # posture for an unattended run); --permission-prompts none additionally tells Claude
  # nobody can approve a denied request and not to retry it, which is the one that saves
  # turns/cost. --max-turns is the hard stop under both. All three measured together in
  # CLI-PLAN.md's "Permissions" section — using only one of the first two still works but
  # burns turns retrying denials.
  #
  # No --add-dir: the skill lives in this repo's own .claude/skills/, loaded normally
  # without --bare. --add-dir only matters for --bare's skill-loading exception
  # (code.claude.com/docs/en/headless.md), and --bare itself is still blocked on a
  # Console ANTHROPIC_API_KEY (CLI-PLAN.md phase A).
  claude -p "/author-rate-spec $source $schedule $provider" \
    --output-format json \
    --json-schema "$JSON_SCHEMA" \
    --permission-mode dontAsk \
    --permission-prompts none \
    --max-turns "$MAX_TURNS" \
    >"$run_log" 2>"$LOG_DIR/${name}.stderr" || true
  # `|| true`: a non-zero exit is one of the gate's own inputs below, not a script error —
  # CLI-PLAN.md measured that exit code alone (and even is_error:false alone) doesn't mean
  # the task succeeded, so every signal is read from the JSON, not from $?.

  if ! jq -e . "$run_log" >/dev/null 2>&1; then
    echo "FAIL $name: $run_log is not valid JSON — see ${name}.stderr" >&2
    printf '%s\t%s\t%s\n' "$name" "<none>" "FAIL:invalid-json" >>"$SESSION_INDEX"
    overall_fail=1
    continue
  fi

  session_id="$(jq -r '.session_id // "<none>"' "$run_log")"
  # NOT `.is_error // true` -- jq's `//` falls through on `false` as well as `null`, so
  # that form would silently read a genuine `is_error: false` as `true`. Verified against
  # a mock (notes/phase_c_scaffolding.md) before writing it this way.
  is_error="$(jq -r 'if .is_error == null then true else .is_error end' "$run_log")"
  denials="$(jq -c '.permission_denials // []' "$run_log")"
  structured="$(jq -c '.structured_output // empty' "$run_log")"

  echo "session: $session_id  (reopen with: claude --resume $session_id)"

  outcome=""
  if [[ "$is_error" != "false" ]]; then
    echo "FAIL $name: is_error=$is_error — see $run_log" >&2
    outcome="FAIL:is_error"
  elif [[ "$denials" != "[]" ]]; then
    echo "FAIL $name: permission_denials=$denials — see $run_log" >&2
    outcome="FAIL:permission_denied"
  elif [[ -z "$structured" ]]; then
    echo "FAIL $name: no structured_output — see $run_log" >&2
    outcome="FAIL:no_structured_output"
  else
    echo "$structured" >"$LOG_DIR/${name}.structured_output.json"
    echo "structured_output OK — see ${name}.structured_output.json"

    # TODO(cameron) #3 above: this is where structured_output becomes
    # $CANDIDATES_DIR/${name}.yaml. Until that conversion exists, SKIP rather than
    # fabricate one — a driver that invents a spec YAML to make its own gate pass is
    # exactly the failure mode CLAUDE.md's reconciliation-gated invariant exists to catch.
    candidate="$CANDIDATES_DIR/${name}.yaml"
    if [[ -f "$candidate" ]]; then
      if "$REPO_ROOT/scripts/validate_spec.sh" "$candidate"; then
        outcome="PASS:schema_valid"
      else
        outcome="FAIL:validate_spec"
      fi
    else
      echo "SKIP $name: no $candidate yet (structured_output -> YAML conversion is TODO(cameron) #3)"
      outcome="SKIP:no_candidate_yaml"
    fi
    # TODO(cameron) #4 above: once $candidate exists, the calibration diff against the
    # committed ground-truth spec belongs here (or in phase D's scoring loop) — not
    # written, per rule 1.
  fi

  printf '%s\t%s\t%s\n' "$name" "$session_id" "$outcome" >>"$SESSION_INDEX"
  [[ "$outcome" == PASS:* || "$outcome" == SKIP:* ]] || overall_fail=1
done

echo
echo "session index: $SESSION_INDEX"
exit "$overall_fail"
