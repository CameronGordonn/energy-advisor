"""Reconciliation harness: compare a modeled bill against a real statement.

Given a golden-bill fixture (the anonymized real statement) + the customer's interval
series + the tariff specs, recompute the bill and produce a line-by-line comparison
plus a pass/fail against the fixture's dollar tolerance. This is M0's trust artifact:
the printed comparison and the ±$2 gate.

**The harness is utility-general.** A fixture names its ``utility:``, and that field —
not a hardcoded PG&E filename glob and not a hardcoded parser import — selects both the
interval export in ``data/`` and the parser that reads it. Anything else would make a
new utility's first reconciliation a harness project rather than a fixture, which is
precisely the wrong thing to discover on the day the customer's data lands.

**Customer facts raise, they never default.** A tariff spec fixes the rate, the hours
and the cap; it cannot know the household's climate zone, PCIA vintage, supplier or
which event days were called. ``compute_bill`` already refuses to guess those (see
``Baseline.allowance_per_day``, ``PerKwhAdder.vintage_rate``,
``bill.MissingEventDaysError``), and this module extends the same rule up one level: it
asks the loaded specs which facts they need and refuses a fixture that omits one, by
name, before any dollar is computed. A wrong climate zone misprices every line on the
bill without any line looking wrong.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel

from greenbutton import parse_pge_interval_csv, parse_sdge_interval_csv
from greenbutton.models import IntervalSeries, ParseReport, Utility
from tariffs.bill import LineItem, compute_bill
from tariffs.loader import load_spec_versions
from tariffs.schema import AppliesTo, Layer, Service, TariffSpec

GOLDEN_DIR = Path("tests/golden_bills")
DATA_DIR = Path("data")


# --- utility dispatch: which file, read by which parser ---------------------

INTERVAL_GLOBS: dict[Utility, tuple[str, ...]] = {
    # PG&E's "Export usage for a range of days" writes one fixed prefix.
    Utility.PGE: ("pge_electric_usage_interval_data*.csv",),
    # SDG&E's portal writes the meter shape (``Electric_60_Minute_<from>_<to>_<run>.csv``,
    # prefixed ``PV_`` on a solar account) and, on the documented range shape, an
    # ``sdge``-prefixed name. Both are real: the four exports surveyed in
    # notes/sdge_public_exports_2026-09.md use the former. Deliberately NOT a bare
    # ``*.csv`` — data/ also holds gas interval and billing-summary exports, and picking
    # one of those up would be a wrong bill rather than a missing one.
    Utility.SDGE: (
        "sdge*.csv",
        "SDGE*.csv",
        "*Electric_15_Minute_*.csv",
        "*Electric_60_Minute_*.csv",
    ),
}

_PARSERS = {
    Utility.PGE: parse_pge_interval_csv,
    Utility.SDGE: parse_sdge_interval_csv,
}


class FixtureError(ValueError):
    """A golden-bill fixture is unusable as written."""


class MissingCustomerFactError(FixtureError):
    """A fixture omits a per-household fact its own tariff specs cannot supply."""


class AmbiguousIntervalExportError(FixtureError):
    """Several interval exports match one utility — say which one this bill belongs to."""


def fixture_utility(fixture: dict) -> Utility:
    """The ``utility:`` field as a :class:`Utility`. Raises if absent or unknown."""
    raw = fixture.get("utility")
    if raw is None:
        raise FixtureError(
            "fixture has no `utility:` field; it selects both the interval export and "
            f"the parser, so it cannot be inferred. Known: {[u.value for u in Utility]}"
        )
    try:
        return Utility(raw)
    except ValueError:
        raise FixtureError(
            f"fixture declares utility {raw!r}, which has no parser; known: "
            f"{[u.value for u in Utility]}"
        ) from None


def interval_files_for(utility: Utility, data_dir: str | Path = DATA_DIR) -> list[Path]:
    """Every interval export in ``data_dir`` written by ``utility``, deduplicated."""
    data_dir = Path(data_dir)
    seen: dict[str, Path] = {}
    for pattern in INTERVAL_GLOBS[utility]:
        for p in data_dir.glob(pattern):
            seen.setdefault(str(p.resolve()), p)  # case-insensitive FS: same file twice
    return sorted(seen.values())


def interval_file_for(utility: Utility, data_dir: str | Path = DATA_DIR) -> Path | None:
    """The one interval export for ``utility``, or None. Raises when several match.

    Two exports for one utility are not a tie to break silently: they may cover
    different date ranges or different meters, and reconciling a statement against the
    wrong one produces a confident wrong dollar rather than an error.
    """
    matches = interval_files_for(utility, data_dir)
    if not matches:
        return None
    if len(matches) > 1:
        raise AmbiguousIntervalExportError(
            f"{len(matches)} {utility.value} interval exports in {data_dir}: "
            f"{[p.name for p in matches]}. Which one covers this statement is a fact "
            "about the file, not something to pick alphabetically — pass the path "
            "explicitly (reconcile(..., series=...)) or leave one in place."
        )
    return matches[0]


def parse_interval_file(utility: Utility, path: str | Path) -> tuple[IntervalSeries, ParseReport]:
    """Parse ``path`` with the parser for ``utility`` — no format sniffing.

    ``report.inspect._detect_and_parse`` sniffs, because it is handed a file by someone
    who may not know what it is. Here the fixture states the utility, so a file that
    fails that utility's parser is a mislabeled fixture or a bad export, and either way
    should surface as that parser's own error rather than be silently read as the other
    utility's format.
    """
    return _PARSERS[utility](path)


def load_interval_series(fixture: dict, data_dir: str | Path = DATA_DIR) -> IntervalSeries:
    """The interval series this fixture's bill should be reconciled against."""
    utility = fixture_utility(fixture)
    path = interval_file_for(utility, data_dir)
    if path is None:
        raise FixtureError(
            f"no {utility.value} interval export in {data_dir} matching "
            f"{list(INTERVAL_GLOBS[utility])}"
        )
    return parse_interval_file(utility, path)[0]


# --- customer facts the tariff cannot know ---------------------------------

CUSTOMER_FACTS = ("service", "territory", "vintage", "event_days")
"""The bill-time arguments that are facts about the household, not about the tariff.

Same list, same names and same reasoning as ``compute_bill``'s keyword arguments.
"""


def required_customer_facts(
    specs: Sequence[TariffSpec], *, service: Service | None = None
) -> dict[str, str]:
    """Which of :data:`CUSTOMER_FACTS` these specs cannot resolve alone -> why.

    Derived from the loaded specs on every run rather than listed per utility, so a spec
    that *gains* a vintaged adder or a climate-zone table immediately starts failing the
    fixtures that do not declare it, instead of quietly billing them under a default.

    ``service`` narrows the answer the same way ``compute_layer`` does: a line the
    customer does not pay demands nothing. A bundled SDG&E household never pays the PCIA,
    so asking it for a PCIA vintage would be a fact it cannot have — which is how a
    required field turns into a guessed one.
    """
    need: dict[str, str] = {}

    def _note(fact: str, spec: TariffSpec, why: str) -> None:
        need.setdefault(fact, f"{spec.provider} {spec.schedule_id} {spec.layer.value}: {why}")

    def _billed(applies_to: AppliesTo) -> bool:
        return service is None or applies_to.covers(service)

    for spec in specs:
        for adder in spec.adders:
            if adder.applies_to is not AppliesTo.ALL:
                _note(
                    "service",
                    spec,
                    f"bills {adder.name!r} only to {adder.applies_to.value} customers",
                )
            if adder.per_kwh_by_vintage and adder.vintage_pin is None and _billed(adder.applies_to):
                _note(
                    "vintage",
                    spec,
                    f"prices {adder.name!r} per PCIA vintage ({sorted(adder.per_kwh_by_vintage)})",
                )
        for sur in spec.surcharges:
            if sur.applies_to is not AppliesTo.ALL:
                _note(
                    "service",
                    spec,
                    f"bills {sur.name!r} only to {sur.applies_to.value} customers",
                )
        base = spec.baseline
        if base is not None and base.allowances and base.territory is None:
            _note(
                "territory",
                spec,
                f"publishes a baseline allowance table by climate zone "
                f"({sorted(base.allowances)}) and pins no zone",
            )
        if spec.event_adder is not None:
            _note(
                "event_days",
                spec,
                f"carries the {spec.event_adder.name} on up to "
                f"{spec.event_adder.max_events_per_year} utility-called days a year",
            )
    return need


def _as_dates(value: object, fixture_name: str) -> list[date]:
    if not isinstance(value, list):
        raise FixtureError(f"{fixture_name}: customer.event_days must be a list of dates")
    out: list[date] = []
    for item in value:
        out.append(item if isinstance(item, date) else date.fromisoformat(str(item)))
    return out


def customer_facts(fixture: dict, specs: Sequence[TariffSpec], *, name: str = "fixture") -> dict:
    """The fixture's ``customer:`` block as ``compute_bill`` keyword arguments.

    Raises :class:`MissingCustomerFactError`, naming every missing key and the spec that
    demands it, when the fixture omits a fact the specs need. Facts the fixture declares
    but the specs do not need are still passed through — the engine is the authority on
    whether a declared fact contradicts the schedule, and swallowing it here would hide a
    fixture that names, say, an SDG&E climate zone on a PG&E bill.
    """
    block = fixture.get("customer") or {}
    if not isinstance(block, dict):
        raise FixtureError(f"{name}: `customer:` must be a mapping of household facts")
    if unknown := sorted(set(block) - set(CUSTOMER_FACTS)):
        raise FixtureError(
            f"{name}: unknown customer fact(s) {unknown}; this harness threads "
            f"{list(CUSTOMER_FACTS)} into compute_bill"
        )

    out: dict = {}
    if (raw_service := block.get("service")) is not None:
        try:
            out["service"] = Service(raw_service)
        except ValueError:
            raise FixtureError(
                f"{name}: unknown customer.service {raw_service!r}; expected one of "
                f"{[s.value for s in Service]}"
            ) from None

    # Service is resolved first because it decides which lines are billed at all, and a
    # line that is not billed demands nothing else.
    need = required_customer_facts(specs, service=out.get("service"))
    missing = [k for k in CUSTOMER_FACTS if k in need and block.get(k) is None]
    if missing:
        detail = "\n".join(f"    {k}: required because {need[k]}" for k in missing)
        raise MissingCustomerFactError(
            f"{name} is missing customer fact(s) {missing}. These are facts about the "
            "HOUSEHOLD, printed on its bill, that no tariff can supply:\n"
            f"{detail}\n"
            "  Add them under a `customer:` block in the fixture. There is deliberately "
            "no default: a wrong climate zone or PCIA vintage misprices every kWh on the "
            "statement without any single line looking wrong."
        )

    if (territory := block.get("territory")) is not None:
        out["territory"] = str(territory)
    if (vintage := block.get("vintage")) is not None:
        out["vintage"] = str(vintage)
    if (event_days := block.get("event_days")) is not None:
        out["event_days"] = _as_dates(event_days, name)
    return out


# --- the comparison --------------------------------------------------------


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
    utility: str
    schedule_label: str
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


def _short_provider(provider: str) -> str:
    """``Central Coast Community Energy (3CE)`` -> ``3CE``; anything else unchanged."""
    m = re.search(r"\(([^)]+)\)\s*$", provider)
    return m.group(1) if m else provider


def reconcile(
    fixture: dict,
    series: IntervalSeries,
    specs_dir: str | Path = "src/tariffs/specs",
    *,
    name: str = "fixture",
) -> ReconResult:
    ps = date.fromisoformat(fixture["period_start"])
    pe = date.fromisoformat(fixture["period_end"])
    care = fixture.get("customer_class") == "CARE"
    spec_ids = fixture["specs"]

    deliv = load_spec_versions(
        spec_ids["delivery"],
        Layer.DELIVERY,
        provider=spec_ids.get("delivery_provider"),
        specs_dir=specs_dir,
    )
    gen = load_spec_versions(
        spec_ids["generation"],
        Layer.GENERATION,
        provider=spec_ids.get("generation_provider"),
        specs_dir=specs_dir,
    )
    facts = customer_facts(fixture, [*deliv, *gen], name=name)

    exp = fixture["expected"]
    obs = [
        LineItem(name=name_, amount=amt)
        for name_, amt in exp.get("observed_adjustments", {}).items()
        if amt is not None
    ]
    bill = compute_bill(series, [deliv, gen], ps, pe, care=care, observed_adjustments=obs, **facts)

    rows: list[Row] = []
    for layer in bill.layers:
        modeled = layer.bucket()
        expected = exp[layer.layer.value]["line_items"]
        for line_name in list(expected) + [k for k in modeled if k not in expected]:
            rows.append(
                Row(
                    section=layer.layer.value,
                    name=line_name,
                    bill=expected.get(line_name),
                    modeled=modeled.get(line_name),
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

    label = f"{deliv[0].schedule_id} + {_short_provider(gen[0].provider)}"
    return ReconResult(
        statement_date=fixture["statement_date"],
        utility=fixture_utility(fixture).value,
        schedule_label=f"{label} (CARE)" if care else label,
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
        f"Statement {r.statement_date}   period {r.period_start} .. {r.period_end}"
        f"   [{r.utility} {r.schedule_label}]",
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
