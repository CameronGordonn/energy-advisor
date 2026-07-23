"""M2: rank every eligible rate plan for the household, from its own interval data.

One command (needs the git-ignored interval export in data/):
    PYTHONPATH=src python scripts/rate_optimizer.py [--as-of 2026-07-23] [--no-care]

Prints: the ranking with annual dollars, the delta vs the current plan, the sensitivity
note (what usage change flips it), and the assumption audit — including the ranking
recomputed under every plausible Santa Cruz UUT Adjustment mechanism.
"""

from __future__ import annotations

import argparse
import glob
import sys
from datetime import date
from pathlib import Path

import yaml

from greenbutton import parse_pge_interval_csv
from scenarios.rate_optimizer import (
    EVENING_HOURS,
    PGE_3CE_CANDIDATES,
    UutPolicy,
    explain,
    flip_factor,
    rank,
)

GOLDEN_DIR = Path("tests/golden_bills")
CURRENT_PLAN = "E-TOU-C + 3CE"
W = 84


def _interval_file() -> str | None:
    m = sorted(glob.glob("data/pge_electric_usage_interval_data*.csv"))
    return m[0] if m else None


def _billing_periods() -> list[tuple[date, date]]:
    """The household's real meter-read periods, from the golden-bill fixtures.

    Real read dates (not calendar months) are what set the per-day fixed charges and the
    baseline allowances, so the counterfactual uses the same period boundaries the actual
    bills used. Only the *dates* are taken from the fixtures; every dollar is re-simulated.
    """
    out = []
    for p in sorted(GOLDEN_DIR.glob("*.yaml")):
        fx = yaml.safe_load(p.read_text())
        out.append((date.fromisoformat(fx["period_start"]), date.fromisoformat(fx["period_end"])))
    return sorted(out)


def _rule(char: str = "-") -> str:
    return char * W


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=date.today().isoformat(), help="rate vintage to compare at")
    ap.add_argument("--no-care", action="store_true", help="bill as a standard (non-CARE) customer")
    ap.add_argument(
        "--pge-comparison",
        help="YAML of PG&E Rate Plan Comparison output to cross-check against (M2 DoD)",
    )
    args = ap.parse_args()
    as_of = date.fromisoformat(args.as_of)
    care = not args.no_care

    f = _interval_file()
    if not f:
        print("no interval export in data/ — cannot run the optimizer", file=sys.stderr)
        return 1
    series, _ = parse_pge_interval_csv(f)
    periods = _billing_periods()
    span = f"{periods[0][0]} .. {periods[-1][1]}"

    plans = rank(series, periods, care=care, as_of=as_of)
    by_name = {p.name: p for p in plans}
    current = by_name[CURRENT_PLAN]
    days = current.days

    print(_rule("="))
    print("RATE PLAN RANKING — PG&E / Santa Cruz, CARE" if care else "RATE PLAN RANKING — PG&E")
    print(f"  {len(periods)} real billing periods, {span}  ({days} days, {current.kwh:.0f} kWh)")
    print(f"  all plans priced at rates in effect {as_of} (not the historical rate vintages)")
    print(_rule("="))
    print(f"{'#':<3}{'plan':<24}{'annual $':>11}{'$/mo':>9}{'vs current':>12}   note")
    print(_rule())
    for i, p in enumerate(plans, start=1):
        delta = p.total - current.total
        mark = "  <- current" if p.name == CURRENT_PLAN else ""
        note = f"CONDITIONAL: {p.eligibility}" if p.eligibility else mark.strip()
        print(
            f"{i:<3}{p.name:<24}{p.total:>11.2f}{p.total / days * 30.4:>9.2f}"
            f"{delta:>+12.2f}   {note}"
        )
    print(_rule())

    eligible = [p for p in plans if not p.eligibility]
    best = eligible[0]
    if best.name == CURRENT_PLAN:
        runner = eligible[1]
        print(
            f"VERDICT: STAY on {CURRENT_PLAN}. It is already the cheapest plan this household\n"
            f"         can take. Nearest alternative {runner.name} costs "
            f"${runner.total - current.total:+,.2f}/yr more."
        )
    else:
        print(
            f"VERDICT: SWITCH to {best.name} — ${current.total - best.total:,.2f}/yr cheaper "
            f"({(current.total - best.total) / days * 30.4:,.2f}/mo)."
        )
    conditional = [p for p in plans if p.eligibility and p.total < best.total]
    for p in conditional:
        print(
            f"         NOT RECOMMENDED but cheaper on paper: {p.name} "
            f"(${p.total - best.total:+,.2f}/yr) — {p.eligibility}."
        )

    # --- why ------------------------------------------------------------------------
    print()
    print(_rule("="))
    print(f"WHY — where the money actually differs vs {eligible[0].name} (annual $)")
    print(_rule("="))
    for p in plans:
        if p.name == eligible[0].name:
            continue
        print(f"  {p.name}  ({p.total - eligible[0].total:+.2f}/yr)")
        for line, d in explain(eligible[0], p):
            print(f"      {d:>+10.2f}   {line}")
    print(
        "\n  Read this before the headline number. The single largest line above is the\n"
        "  baseline credit, which E-TOU-C and E-1 have and E-TOU-D and EV2-A do not — so\n"
        "  for this household the plan choice turns mostly on the baseline credit, and only\n"
        "  secondarily on the peak/off-peak spread. EV2-A nearly closes the gap anyway on\n"
        "  the strength of its 22.6c whole-home off-peak rate."
    )

    # --- sensitivity ----------------------------------------------------------------
    print()
    print(_rule("="))
    print("SENSITIVITY — what would have to change to flip the ranking")
    print(_rule("="))
    cand = {c.name: c for c in PGE_3CE_CANDIDATES}
    top = eligible[0]
    challengers = [p for p in eligible[1:]]
    hours_label = f"{EVENING_HOURS.start}:00-{EVENING_HOURS.stop}:00"
    print(f"Evening window tested: {hours_label} (the 4-9 p.m. block CA peaks sit inside).")
    for ch in challengers:
        for neutral, mode in ((False, "total load changes"), (True, "load-neutral shift")):
            ff = flip_factor(
                series,
                periods,
                cand[top.name],
                cand[ch.name],
                care=care,
                as_of=as_of,
                load_neutral=neutral,
            )
            if ff is None:
                print(f"  [{mode:<18}] {ch.name:<22} never overtakes {top.name} (0.05x-6x).")
            else:
                pct = (ff - 1.0) * 100
                verb = "grew" if pct > 0 else "shrank"
                print(
                    f"  [{mode:<18}] {ch.name:<22} overtakes {top.name} if evening usage "
                    f"{verb} {abs(pct):.0f}% ({ff:.2f}x)"
                )

    # --- assumption audit -----------------------------------------------------------
    print()
    print(_rule("="))
    print("ASSUMPTION AUDIT — every ranking below is the same data, different assumption")
    print(_rule("="))
    print("Santa Cruz UUT Adjustment (mechanism UNVERIFIED — see SESSION_NOTES):")
    orders = {}
    for policy in UutPolicy:
        ps = rank(series, periods, care=care, as_of=as_of, policy=policy)
        orders[policy] = [p.name for p in ps]
        totals = "  ".join(f"{p.name.split(' +')[0]}={p.total:,.0f}" for p in ps)
        print(f"  {policy.value:<13} {policy.description}")
        print(f"      order: {totals}")
    same = len({tuple(v) for v in orders.values()}) == 1
    print(
        f"  => the ranking is {'IDENTICAL' if same else 'NOT identical'} under all three "
        "mechanisms."
    )
    if same:
        print(
            "     The adopted per-day credit is schedule-independent, so it shifts every\n"
            "     total by the same amount and cannot reorder the ranking; the two\n"
            "     schedule-dependent rivals do not reorder it either."
        )
    print()
    print("Other assumptions carried into every number above:")
    print("  - CARE energy rates are DERIVED (care = 0.65 x standard - 0.01038), not printed")
    print("    in the tariff book. Validated on E-TOU-C to <=1e-5 and cross-checked against")
    print("    E-1's printed tier pair. Re-run with --no-care to see the fully tariff-grounded")
    print("    ranking.")
    print("  - Rates are a snapshot: no escalation, no future rate cases. M3 adds distributions.")
    print("  - Load is the customer's actual metered year; no weather normalisation.")
    print("  - PG&E-bundled generation (leaving 3CE) is NOT among the candidates — 3CE opt-out")
    print("    economics need the bundled generation layer, which is a separate spec.")

    _cross_check(args.pge_comparison, plans, current)
    return 0


CROSS_CHECK_HOWTO = """\
  NOT YET DONE — this is the one part of the M2 definition of done that is still open.
  PG&E's Rate Plan Comparison is behind an account login (pge.com/rateanalysis-pge), so it
  cannot be fetched here; it has to be run by the account holder.

  To close it:
    1. Sign in at pge.com -> Rate Plan Comparison ("Compare rate plans based on your
       actual usage"). It uses the same 12 months of interval data this report uses.
    2. Write its output to a YAML file, one line per plan, annual dollars:
           source: PG&E Rate Plan Comparison, run YYYY-MM-DD
           plans:
             E-TOU-C: 1104.22
             E-1: 1160.91
             E-TOU-D: 1208.80
             EV2-A: 1130.52
    3. Re-run:  PYTHONPATH=src python scripts/rate_optimizer.py --pge-comparison FILE

  Expect a level difference, and do not treat it as an error on its own: PG&E's tool
  prices BUNDLED service (PG&E generation), while this household buys generation from 3CE.
  The comparison that matters is the RANKING and the SPREADS between plans, not the totals.
"""


def _cross_check(path: str | None, plans, current) -> None:
    print()
    print(_rule("="))
    print("CROSS-CHECK vs PG&E's own rate comparison (M2 definition of done)")
    print(_rule("="))
    if not path:
        print(CROSS_CHECK_HOWTO)
        print("  Cross-checks that ARE complete, and what each one proves:")
        print("    - Every rate in every spec above traces to a Cal. P.U.C. tariff sheet")
        print("      number; the unbundled components sum to the printed total rate exactly")
        print("      on all four schedules (an arithmetic check PG&E's own sheet must pass).")
        print("    - The E-TOU-C generation credit derived from the tariff (-0.12699/-0.10031)")
        print("      reproduces the value independently least-squares-fitted from Cameron's")
        print("      bills (-0.12705/-0.10030) to 6e-05.")
        print("    - 3CE's published rate sheet reproduces this repo's bill-derived MBRETCH1")
        print("      generation rates exactly, and its 2026-02-15 effective date matches the")
        print("      changeover date derived from Cameron's interval data.")
        print("    - The E-TOU-C leg of this ranking is the same engine that reproduces all")
        print("      11 real statements within $0.22 (scripts/reconcile_report.py).")
        return

    ref = yaml.safe_load(Path(path).read_text())
    theirs = ref["plans"]
    print(f"  reference: {ref.get('source', path)}")
    print(f"  {'plan':<14}{'PG&E $':>11}{'ours $':>11}{'Δ $':>9}{'Δ %':>8}")
    ours = {p.delivery: p.total for p in plans}
    for k, v in theirs.items():
        if k not in ours:
            print(f"  {k:<14}{v:>11.2f}{'—':>11}   not modeled")
            continue
        d = ours[k] - v
        print(f"  {k:<14}{v:>11.2f}{ours[k]:>11.2f}{d:>+9.2f}{d / v * 100:>+7.1f}%")
    order_theirs = [k for k, _ in sorted(theirs.items(), key=lambda kv: kv[1])]
    order_ours = [p.delivery for p in plans if p.delivery in theirs]
    agree = order_theirs == order_ours
    print(f"\n  ranking: PG&E {' < '.join(order_theirs)}")
    print(f"  ranking: ours {' < '.join(order_ours)}")
    print(f"  => rankings {'AGREE' if agree else 'DISAGREE — explain before shipping'}.")
    if not agree:
        print("     Check first: bundled-vs-CCA generation, CARE handling, and whether PG&E's")
        print("     tool used a different 12-month window than the 11 periods used here.")


if __name__ == "__main__":
    sys.exit(main())
