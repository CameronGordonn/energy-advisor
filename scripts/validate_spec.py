#!/usr/bin/env python
"""Validate one candidate tariff spec YAML against the repo's loader.

    scripts/validate_spec.sh build/candidates/some_candidate.yaml

Exit 0: the file parses as a ``TariffSpec`` with no ``UNVERIFIED`` fields — schema-valid,
which is all this checks. It says nothing about whether the transcribed numbers are RIGHT;
that is CLI-PLAN.md's D2 span check plus a human diff against the source, neither of which
lives here. See CLI-PLAN.md phase C ("Done when: one spec generated end to end and passes
schema validation") and phase D (the scoring loop this gate feeds).

This is the "one command" CLI-PLAN.md's Permissions section calls for: an unattended
`claude -p` run needs a way to check its own output without a general interpreter, because
`PYTHONPATH=src python ...` — this repo's documented invocation — is not covered by a
`Bash(python *)` allow rule. See .claude/settings.json and validate_spec.sh.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tariffs.loader import load_spec_file


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: validate_spec.py <candidate.yaml>", file=sys.stderr)
        return 2

    path = Path(argv[0])
    if not path.is_file():
        print(f"FAIL {path}: no such file", file=sys.stderr)
        return 1

    try:
        spec = load_spec_file(path)
    except Exception as exc:
        print(f"FAIL {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(
        f"OK {path}: schedule_id={spec.schedule_id!r} layer={spec.layer.value} "
        f"provider={spec.provider!r} effective_date={spec.effective_date}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
