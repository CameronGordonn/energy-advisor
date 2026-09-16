#!/usr/bin/env bash
# Run one candidate tariff spec YAML through the repo's loader; exit non-zero on failure.
#
#   scripts/validate_spec.sh build/candidates/some_candidate.yaml
#
# This exists so an unattended `claude -p` run has exactly ONE command to allowlist
# (see .claude/settings.json) instead of a general interpreter. CLI-PLAN.md's Permissions
# section measured that `PYTHONPATH=src python ...` — this repo's documented invocation —
# is NOT covered by a `Bash(python *)` allow rule, and that granting `python *` to an
# unattended run is the wrong shape regardless. This script is the wrapper: Claude Code's
# permission check only ever sees the single, exact-prefix-matchable command below: it
# never sees (and so never needs a rule for) the `python` call inside it.
#
# Mechanical schema validity ONLY — see validate_spec.py's docstring for what this does
# and does not prove.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: validate_spec.sh <candidate.yaml>" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$repo_root/scripts/validate_spec.py" "$1"
