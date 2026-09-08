#!/usr/bin/env python
"""Bundle the Python engine the browser tool runs, from src/ — one source of truth.

    PYTHONPATH=src python scripts/build_web_engine.py [--check]

The public tool at docs/index.html runs the **real** parsers and inspector under Pyodide,
not a JavaScript reimplementation, so a visitor's analysis is the analysis the pytest suite
covers. To do that the browser needs the module sources; GitHub Pages serves only ``docs/``,
and the modules live in ``src/``.

Rather than committing a hand-copied duplicate that silently drifts, this generates
``docs/engine.js`` from ``src/`` and ``tests/report/test_web_engine.py`` fails if the
committed bundle no longer matches its sources. Editing a parser and forgetting to rebuild
is therefore a red test, not a subtly stale website.

Only the modules the inspector needs are bundled. The tariff engine, the NEM 3.0 model and
the reconciliation code are deliberately excluded: the browser tool produces no dollar
figures (see report/inspect.py), so shipping the pricing code would be dead weight that
also invites someone to wire it up without the reconciliation gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
OUT = ROOT / "docs" / "engine.js"

# Bundled in dependency order for readability; Python resolves imports itself.
MODULES = [
    "greenbutton/__init__.py",
    "greenbutton/_common.py",
    "greenbutton/models.py",
    "greenbutton/pge.py",
    "greenbutton/sdge.py",
    "report/__init__.py",
    "report/inspect.py",
]

BANNER = """\
// GENERATED FILE — do not edit by hand.
//
// Built from src/ by scripts/build_web_engine.py. These are the real parser and inspector
// modules the pytest suite covers; the browser tool writes them into Pyodide's virtual
// filesystem and imports them, so the analysis a visitor sees is the tested analysis
// rather than a JavaScript reimplementation that could drift from it.
//
// tests/report/test_web_engine.py fails if this file is out of date with src/.
// Rebuild:  PYTHONPATH=src python scripts/build_web_engine.py
"""


def build() -> str:
    files: dict[str, str] = {}
    for rel in MODULES:
        path = SRC / rel
        if not path.is_file():
            raise SystemExit(f"missing module: {path}")
        files[rel] = path.read_text(encoding="utf-8")

    digest = hashlib.sha256(
        "".join(f"{k}\0{v}\0" for k, v in sorted(files.items())).encode("utf-8")
    ).hexdigest()[:16]

    payload = json.dumps(files, indent=1, sort_keys=True, ensure_ascii=False)
    return (
        f"{BANNER}//\n// source digest: {digest}\n\n"
        f"window.ENERGY_ENGINE_DIGEST = {json.dumps(digest)};\n"
        f"window.ENERGY_ENGINE_FILES = {payload};\n"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if docs/engine.js differs from src/ (no write)",
    )
    args = ap.parse_args(argv)

    generated = build()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != generated:
            print(
                "docs/engine.js is STALE relative to src/.\n"
                "Rebuild it:  PYTHONPATH=src python scripts/build_web_engine.py",
                file=sys.stderr,
            )
            return 1
        print(f"docs/engine.js is up to date ({len(generated):,} bytes)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(generated, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(generated):,} bytes, {len(MODULES)} modules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
