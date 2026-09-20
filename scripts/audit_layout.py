"""Check the published pages for the defects neither jsdom nor a screenshot will report.

Three classes of failure, all of which have actually shipped here before:

* **Reflow (WCAG 1.4.10).** 640 and 320 CSS px are 200% and 400% zoom of a 1280 viewport.
  A page that scrolls sideways at either fails, and the cause is usually structural rather
  than cosmetic — a grid item whose ``min-width`` defaults to min-content, or a ``.vh``
  caption inside a box that is not ``position:relative``. Session 20 found three of these
  that both the jsdom test and the screenshot pass had missed.
* **Heading order.** One ``h1``, no skipped levels, counted over the headings that are
  actually in the accessibility tree — which is why this runs on the tool page twice, once
  as a visitor first sees it with ``#results`` hidden, and once with the report open.
* **``scope`` on every ``th``.** A bare ``th`` in a table with row headers is ambiguous.

Chromium is an optional local extra, exactly as for ``screenshot_site.py``; this is
deliberately not in CI for the same reason.

    pip install playwright && python -m playwright install chromium
    PYTHONPATH=src python scripts/audit_layout.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAGES = ("index", "methodology", "privacy", "terms")
WIDTHS = (1280, 640, 320)

# Walks only what a screen reader would reach: `hidden`, `display:none` and `.vh`-style
# offscreen text all behave differently, and only the first two take a heading out of the
# tree. `offsetParent === null` catches a hidden ancestor without catching `.vh`.
PROBE = """
() => {
  const visible = el => el.offsetParent !== null || el === document.body;
  const heads = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")]
    .filter(visible)
    .map(el => ({ level: +el.tagName[1], text: el.textContent.trim().slice(0, 60) }));
  const bare = [...document.querySelectorAll("th")]
    .filter(el => !el.hasAttribute("scope"))
    .map(el => el.textContent.trim().slice(0, 40));
  return {
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    heads,
    bare,
  };
}
"""


def _heading_faults(heads: list[dict]) -> list[str]:
    faults = []
    ones = [h for h in heads if h["level"] == 1]
    if len(ones) != 1:
        faults.append(f"expected exactly one h1, found {len(ones)}")
    previous = 0
    for head in heads:
        if previous and head["level"] > previous + 1:
            faults.append(f"h{previous} -> h{head['level']} skips a level at {head['text']!r}")
        previous = head["level"]
    return faults


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(__doc__)
        print("playwright is not installed — see the install line above.", file=sys.stderr)
        return 2

    inspection = json.loads((REPO / "tools" / "reference-sample.json").read_text())
    case_study = json.loads((REPO / "docs" / "case-study.json").read_text())["recommendation"]
    faults: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in PAGES:
            # The tool page is audited in both of its states. A visitor meets it with the
            # report hidden, and that is the state whose heading order is easiest to break
            # by accident, because every heading inside #results is out of the tree.
            states = [("", False)] + ([("report", True)] if name == "index" else [])
            for label, opened in states:
                where = f"{name}.html" + (f" [{label}]" if label else "")
                for width in WIDTHS:
                    page = browser.new_page(viewport={"width": width, "height": 900})
                    page.goto((REPO / "docs" / f"{name}.html").as_uri())
                    if opened:
                        page.evaluate("d => window.__renderInspection(d, false)", inspection)
                        page.evaluate("r => window.__renderRecommendation(r)", case_study)
                    page.wait_for_timeout(400)
                    r = page.evaluate(PROBE)
                    page.close()

                    if r["scrollWidth"] > r["clientWidth"]:
                        faults.append(
                            f"{where} @ {width}px scrolls sideways: "
                            f"{r['scrollWidth']} > {r['clientWidth']}"
                        )
                    if width == WIDTHS[0]:
                        faults += [f"{where}: {f}" for f in _heading_faults(r["heads"])]
                        faults += [f"{where}: <th> without scope: {t!r}" for t in r["bare"]]
                    print(
                        f"  {where} @ {width}px — {len(r['heads'])} headings, "
                        f"{r['scrollWidth']}/{r['clientWidth']} wide"
                    )
        browser.close()

    if faults:
        print("\nFAULTS")
        for fault in faults:
            print(f"  - {fault}")
        return 1
    print("\nreflow, heading order and th/scope all clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
