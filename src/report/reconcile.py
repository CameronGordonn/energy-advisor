"""Reconciliation harness: compare a modeled bill against a real statement.

Given a golden-bill fixture (the anonymized real statement) + the customer's interval
series + the tariff specs, recompute the bill and produce a line-by-line comparison
plus a pass/fail against the fixture's dollar tolerance. This is M0's trust artifact:
the printed comparison and the ±$2 gate.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel

from greenbutton.models import IntervalSeries
from tariffs.bill import LineItem, compute_bill
from tariffs.loader import load_specs
from tariffs.schema import Layer

GOLDEN_DIR = Path("tests/golden_bills")


class Row(BaseModel):
    section: str  # "delivery" | "generation" | "adjustment" | "net"
    name: str
    bill: float | None
    modeled: float | None

    @property
    def delta(self) -> float | None:
        if self.bill is None or self.modeled is None:
            return None
        return round(self.modeled - self.bill, 2)


class ReconResult(BaseModel):
    statement_date: str
    period_start: date
    period_end: date
    rows: list[Row]
    net_bill: float
    net_modeled: float
    tolerance: float

    @property
    def delta(self) -> float:
        return round(self.net_modeled - self.net_bill, 2)

    @property
    def within_tolerance(self) -> bool:
        return abs(self.delta) <= self.tolerance


def load_fixture(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def reconcile(
    fixture: dict, series: IntervalSeries, specs_dir: str | Path = "src/tariffs/specs"
) -> ReconResult:
    ps = date.fromisoformat(fixture["period_start"])
    pe = date.fromisoformat(fixture["period_end"])
    care = fixture.get("customer_class") == "CARE"

    deliv = load_specs(fixture["specs"]["delivery"], Layer.DELIVERY, on=ps, specs_dir=specs_dir)
    gen = load_specs(fixture["specs"]["generation"], Layer.GENERATION, on=ps, specs_dir=specs_dir)

    exp = fixture["expected"]
    obs = [
        LineItem(name=name, amount=amt)
        for name, amt in exp.get("observed_adjustments", {}).items()
        if amt is not None
    ]
    bill = compute_bill(series, [deliv, gen], ps, pe, care=care, observed_adjustments=obs)

    rows: list[Row] = []
    for layer in bill.layers:
        modeled = layer.bucket()
        expected = exp[layer.layer.value]["line_items"]
        for name in list(expected) + [k for k in modeled if k not in expected]:
            rows.append(
                Row(
                    section=layer.layer.value,
                    name=name,
                    bill=expected.get(name),
                    modeled=modeled.get(name),
                )
            )
        rows.append(
            Row(
                section=layer.layer.value,
                name=f"— {layer.layer.value} total —",
                bill=exp[layer.layer.value]["total"],
                modeled=layer.total,
            )
        )
    for a in obs:  # observed inputs: bill == modeled by construction
        rows.append(Row(section="adjustment", name=a.name, bill=a.amount, modeled=a.amount))

    return ReconResult(
        statement_date=fixture["statement_date"],
        period_start=ps,
        period_end=pe,
        rows=rows,
        net_bill=exp["electric_net_total"],
        net_modeled=bill.total,
        tolerance=fixture.get("tolerance_dollars", 2.0),
    )


def format_comparison(r: ReconResult) -> str:
    """The printed line-item comparison (M0 DoD)."""
    lines = [
        f"Statement {r.statement_date}   period {r.period_start} .. {r.period_end}",
        f"{'line item':<52}{'bill $':>10}{'model $':>10}{'Δ $':>8}",
        "-" * 80,
    ]
    section = None
    for row in r.rows:
        if row.section != section:
            section = row.section
            lines.append(f"[{section}]")
        b = f"{row.bill:.2f}" if row.bill is not None else "—"
        m = f"{row.modeled:.2f}" if row.modeled is not None else "—"
        d = f"{row.delta:+.2f}" if row.delta is not None else ""
        flag = "  <<" if row.delta is not None and abs(row.delta) >= 0.50 else ""
        lines.append(f"  {row.name:<50}{b:>10}{m:>10}{d:>8}{flag}")
    verdict = "PASS ✓" if r.within_tolerance else "FAIL ✗"
    lines += [
        "=" * 80,
        f"{'ELECTRIC NET':<52}{r.net_bill:>10.2f}{r.net_modeled:>10.2f}{r.delta:>+8.2f}",
        f"tolerance ±${r.tolerance:.2f}  ->  {verdict}",
    ]
    return "\n".join(lines)
