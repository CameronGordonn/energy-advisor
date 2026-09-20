"""Recompute the site's contrast matrix from ``docs/site.css``, arithmetically.

Relative luminance is a formula, not a judgement, so the matrix belongs in a script rather
than in a table somebody retypes. The tokens are read out of the stylesheet's own ``:root``
and ``[data-theme="dark"]`` blocks, which means the numbers cannot drift from the palette
the way a hand-maintained table does — the recorded reason this has to be redone after any
palette change.

Thresholds (WCAG 2.1 AA):

* **4.5** for text.
* **3.0** for graphics — a chart bar is data and has to clear it against the plate it sits
  on; a hairline rule is not data and is exempt.
* ``--sul`` is the standing exception: a **fill only**, never a text colour. It is reported
  so the number stays visible, and it is expected to fail the text threshold on paper.

    PYTHONPATH=src python scripts/contrast_matrix.py [--markdown]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSS = REPO / "docs" / "site.css"

# (foreground, background, threshold, what it is). The thresholds are the point of the
# table: a bar and a word on the same two colours are held to different numbers.
PAIRS: tuple[tuple[str, str, float, str], ...] = (
    ("ink", "paper", 4.5, "body text"),
    ("ink", "paper-2", 4.5, "body text on a plate"),
    ("ink-2", "paper", 4.5, "secondary text"),
    ("ink-2", "paper-2", 4.5, "secondary text on a plate"),
    ("ink-3", "paper", 4.5, "rail, tags, axis labels"),
    ("ink-3", "paper-2", 4.5, "rail, tags, axis labels on a plate"),
    ("ox", "paper", 4.5, "accent text, links, the stamps"),
    ("ox", "paper-2", 4.5, "accent text on a plate"),
    ("mark", "paper", 3.0, "chart bars (graphic)"),
    ("mark", "paper-2", 3.0, "chart bars on a plate, ranking bars (graphic)"),
    ("ox", "band", 3.0, "peak bars on the sulphur band (graphic)"),
    ("ink", "band", 4.5, "the current plan's name, highlighted"),
    ("ink-2", "band", 4.5, "the conditional-plan note on that row"),
    ("sul", "paper", 4.5, "FILL ONLY — never text"),
)


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{6})", block))


def palettes() -> dict[str, dict[str, str]]:
    css = CSS.read_text(encoding="utf-8")
    light = _tokens(re.search(r":root\{(.*?)\}", css, re.S).group(1))
    dark = _tokens(re.search(r':root\[data-theme="dark"\]\{(.*?)\}', css, re.S).group(1))
    # Dark is written as overrides, so anything it does not restate it inherits.
    return {"light": light, "dark": {**light, **dark}}


def luminance(hex_colour: str) -> float:
    def channel(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def ratio(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def main(markdown: bool) -> int:
    themes = palettes()
    rows, failures = [], []

    for fg, bg, threshold, what in PAIRS:
        cells = []
        for theme in ("light", "dark"):
            tokens = themes[theme]
            if fg not in tokens or bg not in tokens:
                cells.append("—")
                continue
            value = ratio(tokens[fg], tokens[bg])
            exempt = fg == "sul" and theme == "light"
            passed = value >= threshold or exempt
            cells.append(f"{value:.2f}" + ("" if passed else " **FAIL**"))
            if not passed:
                failures.append(f"--{fg} on --{bg} ({theme}): {value:.2f} < {threshold}")
        rows.append((f"`--{fg}` on `--{bg}`", cells[0], cells[1], f"{threshold:.1f}", what))

    if markdown:
        print("| pair | light | dark | needs | what it is |")
        print("|---|---|---|---|---|")
        for pair, light, dark, need, what in rows:
            print(f"| {pair} | {light} | {dark} | {need} | {what} |")
    else:
        width = max(len(r[0]) for r in rows)
        for pair, light, dark, need, what in rows:
            print(f"{pair:<{width}}  light {light:>12}  dark {dark:>12}  needs {need}  — {what}")

    print()
    if failures:
        print("FAILURES")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(
        "every pair clears its threshold (--sul on --paper is the documented fill-only "
        "exception and is not held to 4.5)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--markdown" in sys.argv))
