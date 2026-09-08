"""The browser bundle must not drift from src/.

`docs/engine.js` carries the parser and inspector sources that the public tool runs under
Pyodide. If someone edits a parser and forgets to rebuild, the website silently keeps
serving the old logic while the test suite goes on covering the new one — the exact split
between "what is tested" and "what users get" that this project exists to avoid.

So the bundle is a checked-in build artifact with a drift test, rather than a hand-copied
duplicate.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts" / "build_web_engine.py"
BUNDLE = ROOT / "docs" / "engine.js"


def test_the_committed_bundle_matches_src():
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )
    assert result.returncode == 0, (
        f"docs/engine.js is stale — the website would serve different code than these "
        f"tests cover.\n{result.stdout}{result.stderr}"
    )


def test_the_bundle_carries_every_module_the_inspector_needs():
    text = BUNDLE.read_text(encoding="utf-8")
    start = text.index("window.ENERGY_ENGINE_FILES = ") + len("window.ENERGY_ENGINE_FILES = ")
    files = json.loads(text[start:].rstrip().rstrip(";"))
    for required in (
        "greenbutton/__init__.py",
        "greenbutton/_common.py",
        "greenbutton/models.py",
        "greenbutton/pge.py",
        "greenbutton/sdge.py",
        "report/__init__.py",
        "report/inspect.py",
    ):
        assert required in files, f"bundle is missing {required}"
        assert files[required].strip(), f"bundle has {required} empty"


def test_the_bundle_ships_no_pricing_code():
    """The browser tool produces no dollar figures. Shipping the tariff engine anyway would
    be dead weight that also invites wiring it up without the reconciliation gate."""
    text = BUNDLE.read_text(encoding="utf-8")
    start = text.index("window.ENERGY_ENGINE_FILES = ") + len("window.ENERGY_ENGINE_FILES = ")
    files = json.loads(text[start:].rstrip().rstrip(";"))
    assert not [p for p in files if p.startswith(("tariffs/", "nem3/", "scenarios/"))]
    assert "reconcile" not in " ".join(files)


@pytest.mark.parametrize("forbidden", ["import yaml", "from tariffs", "import cvxpy"])
def test_bundled_modules_have_no_dependency_the_browser_cannot_load(forbidden):
    """Pyodide loads pandas and pydantic for this tool and nothing else; an import added
    upstream that the browser cannot satisfy must fail here, not in a visitor's console."""
    text = BUNDLE.read_text(encoding="utf-8")
    start = text.index("window.ENERGY_ENGINE_FILES = ") + len("window.ENERGY_ENGINE_FILES = ")
    files = json.loads(text[start:].rstrip().rstrip(";"))
    for path, source in files.items():
        assert forbidden not in source, f"{path} imports something the browser cannot load"
