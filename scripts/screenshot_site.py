"""Render the published pages in a real browser and save screenshots.

The jsdom render test checks structure; it does no layout, so it cannot catch a label
collision, a clipped caption or an unreadable bar. This does — it is the "render it and
look at it" step, and it caught two real defects the first time it ran: the hour chart's
peak-band caption overlapping its direct label, and non-peak bars sitting at 1.5:1 against
the panel in both themes.

Chromium is an OPTIONAL local extra and is deliberately not in environment.yml, so CI is
not made to download it:

    pip install playwright && python -m playwright install chromium

The report state is rendered through the page's own ``__renderInspection`` hook using the
committed reference inspection, so no Pyodide boot and no network are needed.

    PYTHONPATH=src python scripts/screenshot_site.py [outdir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAGES = ("index", "methodology", "privacy", "terms")


def main(outdir: Path) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(__doc__)
        print("playwright is not installed — see the install line above.", file=sys.stderr)
        return 2

    outdir.mkdir(parents=True, exist_ok=True)
    inspection = json.loads((REPO / "tools" / "reference-sample.json").read_text())
    written: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for scheme in ("light", "dark"):
            for name in PAGES:
                page = browser.new_page(
                    viewport={"width": 1280, "height": 900}, color_scheme=scheme
                )
                page.goto((REPO / "docs" / f"{name}.html").as_uri())
                page.wait_for_timeout(600)
                shot = outdir / f"{name}-{scheme}.png"
                page.screenshot(path=shot, full_page=True)
                written.append(shot)

                # index also has a second state: the report, drawn from a real inspection.
                if name == "index":
                    page.evaluate("d => window.__renderInspection(d, false)", inspection)
                    page.wait_for_timeout(400)
                    shot = outdir / f"report-{scheme}.png"
                    page.screenshot(path=shot, full_page=True)
                    written.append(shot)
                    for chart in ("hourChart", "monthChart"):
                        shot = outdir / f"{chart}-{scheme}.png"
                        page.locator(f"#{chart}").screenshot(path=shot)
                        written.append(shot)
                page.close()
        browser.close()

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "build" / "screenshots"
    raise SystemExit(main(target))
