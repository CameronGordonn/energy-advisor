"""The browser bundle must not drift from src/.

`docs/engine.js` carries the parser and inspector sources that the public tool runs under
Pyodide. If someone edits a parser and forgets to rebuild, the website silently keeps
serving the old logic while the test suite goes on covering the new one — the exact split
between "what is tested" and "what users get" that this project exists to avoid.

So the bundle is a checked-in build artifact with a drift test, rather than a hand-copied
duplicate.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts" / "build_web_engine.py"
BUNDLE = ROOT / "docs" / "engine.js"


def bundled_files() -> dict[str, str]:
    """The {path: source} map the page writes into Pyodide's filesystem."""
    text = BUNDLE.read_text(encoding="utf-8")
    start = text.index("window.ENERGY_ENGINE_FILES = ") + len("window.ENERGY_ENGINE_FILES = ")
    return json.loads(text[start:].rstrip().rstrip(";"))


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
    files = bundled_files()
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


def test_the_pricing_code_ships_only_together_with_its_gate():
    """⭐ Session 28 reversed this test, and the reversal is the point.

    It used to assert the bundle ships **no** pricing code, on the grounds that the browser
    tool produces no dollar figures. That reasoning was stricter than invariant 1: the PG&E
    path is reconciled 11/11 within ±$2, so refusing to price it was a choice nobody had
    re-examined, while the real limitation — the specs describe one household's territory,
    heat source, supplier and PCIA vintage — appeared nowhere on the page.

    What must still hold is the thing the old test was protecting: **the tariff engine may
    not reach the browser without the gate that decides who it is allowed to price.** So
    this asserts the pair, in both directions.
    """
    files = bundled_files()
    pricing = [p for p in files if p.startswith(("tariffs/", "scenarios/"))]
    assert pricing, "the optimizer cannot run in the browser without the tariff engine"
    assert "report/recommend.py" in files, (
        "the pricing code is bundled without report/recommend.py — that module IS the "
        "reconciliation gate, and shipping the engine without it is exactly what the "
        "original version of this test existed to prevent"
    )
    assert "RECONCILED_UTILITIES" in files["report/recommend.py"]

    # Still out, and for the same reason as before: no browser surface, so shipping them
    # would be weight and temptation with no user.
    assert not [p for p in files if p.startswith("nem3/")]
    assert "report/reconcile.py" not in files


def test_every_spec_the_cli_can_load_is_also_in_the_browser_bundle():
    """A spec authored and not bundled narrows the browser's coverage silently.

    `report.recommend.authored_scope` reads the tool's reach out of these files, so a
    missing one does not error — it quietly refuses a household the CLI would have priced.
    """
    files = bundled_files()
    on_disk = {f"tariffs/specs/{p.name}" for p in (ROOT / "src/tariffs/specs").glob("*.yaml")}
    assert on_disk, "no specs on disk — the glob is wrong"
    assert on_disk <= set(files), sorted(on_disk - set(files))


#: Third-party top-level module -> the Pyodide package that provides it. Small and explicit
#: because the mapping is not derivable: ``import yaml`` comes from ``pyyaml``.
PYODIDE_PACKAGE = {
    "pandas": "pandas",
    "numpy": "numpy",
    "pydantic": "pydantic",
    "yaml": "pyyaml",
}


def test_every_third_party_import_in_the_bundle_is_a_package_the_page_loads():
    """Tied to the page's own ``loadPackage`` call, not to a hand-written forbidden list.

    The previous version forbade three named imports, which meant adding a fourth
    dependency upstream failed in a visitor's console rather than here. This reads the
    packages `docs/index.html` actually loads and requires the bundle's imports to be
    covered by them — so the failure lands on whoever adds the import.
    """
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    match = re.search(r"loadPackage\(\[([^\]]*)\]", page)
    assert match, "could not find the page's loadPackage call"
    loaded = {p.strip().strip(" \"'") for p in match.group(1).split(",") if p.strip()}
    loaded |= {"numpy"}  # pandas pulls numpy in; Pyodide resolves it without naming it

    # Parsed, not grepped: a docstring line beginning "from charges ..." is prose, and a
    # regex over source lines cannot tell it from an import. The first version of this test
    # reported three of those.
    imported: set[str] = set()
    for path, source in bundled_files().items():
        if not path.endswith(".py"):
            continue
        for node in ast.walk(ast.parse(source, filename=path)):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])

    third_party = imported & set(PYODIDE_PACKAGE)
    missing = {PYODIDE_PACKAGE[m] for m in third_party} - loaded
    assert not missing, (
        f"the bundle imports {sorted(third_party)} but docs/index.html does not load "
        f"{sorted(missing)} — a visitor would get an ImportError in the console"
    )

    unknown = {
        m
        for m in imported
        if m not in PYODIDE_PACKAGE
        and m not in {"greenbutton", "report", "tariffs", "scenarios", "nem3"}
        and m not in sys.stdlib_module_names
    }
    assert not unknown, (
        f"the bundle imports {sorted(unknown)}, which is neither stdlib, nor local, nor a "
        "Pyodide package this test knows about — add it to PYODIDE_PACKAGE and to the "
        "page's loadPackage call, or drop the import"
    )
