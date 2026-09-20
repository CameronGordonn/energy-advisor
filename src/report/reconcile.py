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
from tariffs.bucketed import (
    UsageSegment,
    compute_bill_from_usage,
    segments_from_series,
)
from tariffs.climate_credit import credit_for
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


class NoUsageEvidenceError(FixtureError):
    """A fixture offers neither an interval export nor printed per-TOU-period kWh."""


class PrintedUsageDisagreementError(FixtureError):
    """A fixture's printed kWh and its interval export describe different usage."""


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


def _as_date(value: object, where: str) -> date:
    """A YAML date or ISO string as a :class:`datetime.date`."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise FixtureError(f"{where}: {value!r} is not a YYYY-MM-DD date") from None


# --- printed per-TOU-period kWh: the bill-only input ------------------------

DEFAULT_PRINTED_TOLERANCE_KWH = 0.5
"""How far a printed bucket may sit from the metered one before it is a disagreement.

SDG&E prints usage to the whole kWh, so a faithful transcription of a correct statement
lands inside half a kWh of the meter. Anything wider is a different quantity — a different
meter, a different period, a mis-keyed digit — and the point of holding both is to find
that out. A fixture may widen it, with a reason, via ``printed_usage.tolerance_kwh``.
"""


def printed_usage(fixture: dict, *, name: str = "fixture") -> list[UsageSegment] | None:
    """The fixture's ``printed_usage:`` block, or None when it has none.

    This is M1a's whole input: the per-TOU-period kWh an SDG&E statement prints, which a
    customer can photograph without ever exporting a year of 15-minute data. One segment
    per block the statement itself prints, because a statement that spans a rate change
    prints two and the tariff prices them differently (see :mod:`tariffs.bucketed`).

    Every field is required and nothing is defaulted. A blank kWh is refused by period
    name rather than read as zero: the template ships blank, and a template that priced
    itself as an all-zero bill would be a fabricated expectation.
    """
    block = fixture.get("printed_usage")
    if block is None:
        return None
    if not isinstance(block, dict):
        raise FixtureError(f"{name}: `printed_usage:` must be a mapping with a `segments:` list")
    if unknown := sorted(set(block) - {"segments", "tolerance_kwh", "source"}):
        raise FixtureError(
            f"{name}: unknown printed_usage key(s) {unknown}; expected `segments`, "
            "`tolerance_kwh`, `source`"
        )
    raw = block.get("segments")
    if not isinstance(raw, list) or not raw:
        raise FixtureError(
            f"{name}: printed_usage.segments must be a non-empty list of "
            "{start, end, kwh} blocks, one per sub-period the statement prints"
        )

    out: list[UsageSegment] = []
    for i, seg in enumerate(raw):
        where = f"{name}: printed_usage.segments[{i}]"
        if not isinstance(seg, dict):
            raise FixtureError(f"{where} must be a mapping with start, end and kwh")
        if unknown := sorted(set(seg) - {"start", "end", "kwh"}):
            raise FixtureError(f"{where}: unknown key(s) {unknown}; expected start, end, kwh")
        missing = [k for k in ("start", "end", "kwh") if seg.get(k) is None]
        if missing:
            raise FixtureError(
                f"{where} is missing {missing}. `start`/`end` are the block's own dates as "
                "the statement prints them, INCLUSIVE; `kwh` is that block's kWh per TOU "
                "period."
            )
        buckets = seg["kwh"]
        if not isinstance(buckets, dict) or not buckets:
            raise FixtureError(f"{where}.kwh must be a mapping of TOU period name -> kWh")
        vals: dict[str, float] = {}
        for period, v in buckets.items():
            if v is None:
                raise FixtureError(
                    f"{where}.kwh[{period!r}] is blank. Transcribe the kWh the statement "
                    "prints for that period, or write 0 if it printed none — there is "
                    "deliberately no default, because an unfilled bucket read as zero is "
                    "a fabricated usage figure and it lowers the bill."
                )
            try:
                vals[str(period)] = float(v)
            except (TypeError, ValueError):
                raise FixtureError(f"{where}.kwh[{period!r}] is not a number: {v!r}") from None
        out.append(
            UsageSegment(
                start=_as_date(seg["start"], where),
                end=_as_date(seg["end"], where),
                kwh=vals,
            )
        )
    return out


def printed_tolerance_kwh(fixture: dict) -> float:
    block = fixture.get("printed_usage") or {}
    raw = block.get("tolerance_kwh")
    return DEFAULT_PRINTED_TOLERANCE_KWH if raw is None else float(raw)


def cross_check_printed_usage(
    printed: Sequence[UsageSegment],
    series: IntervalSeries,
    layers: Sequence[Sequence[TariffSpec]],
    *,
    tolerance_kwh: float = DEFAULT_PRINTED_TOLERANCE_KWH,
    name: str = "fixture",
) -> None:
    """Raise when a fixture's printed kWh and its own interval export disagree.

    A fixture that carries both is the only place the two halves of M1 meet, and holding
    them without comparing them would waste the one cross-check available: it is exactly
    the M1b claim — that ``greenbutton`` plus ``tou.rules`` reproduce the utility's own
    bucketing — measured against the utility's own answer. A disagreement is reported per
    period, with both numbers, and it is never averaged away.
    """
    for seg in printed:
        metered: dict[str, float] = {}
        for piece in segments_from_series(series, layers, seg.start, seg.end):
            for period, kwh in piece.kwh.items():
                metered[period] = metered.get(period, 0.0) + kwh
        if unknown := sorted(set(seg.kwh) - set(metered)):
            raise PrintedUsageDisagreementError(
                f"{name}: printed segment {seg.start}..{seg.end} names TOU period(s) "
                f"{unknown} that this schedule does not bill ({sorted(metered)})"
            )
        bad = {
            p: (seg.kwh[p], metered.get(p, 0.0))
            for p in seg.kwh
            if abs(seg.kwh[p] - metered.get(p, 0.0)) > tolerance_kwh
        }
        if bad:
            detail = "\n".join(
                f"    {p}: statement {s:,.2f} kWh vs meter {m:,.2f} kWh ({m - s:+,.2f})"
                for p, (s, m) in sorted(bad.items())
            )
            raise PrintedUsageDisagreementError(
                f"{name}: over {seg.start}..{seg.end} the statement's printed kWh and the "
                f"interval export describe different usage, beyond +/-{tolerance_kwh:g} kWh "
                f"per period:\n{detail}\n"
                "  One of them is not this household's, not this billing period, or not "
                "bucketed the way this repo buckets it. Reconciling either against the "
                "printed dollars would produce a confident wrong residual, so neither is "
                "used until the disagreement is explained."
            )


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
    usage_source: str = "interval"
    """Where the kWh came from: ``interval`` (the export) or ``printed`` (the statement).

    Printed on the comparison, because the two carry different claims. An interval
    reconciliation tests the parser, the TOU rules and the rates; a printed one takes the
    utility's own bucketing as given and tests only the rates and the charge structure.
    """

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
    series: IntervalSeries | None = None,
    specs_dir: str | Path = "src/tariffs/specs",
    *,
    name: str = "fixture",
) -> ReconResult:
    """Reconcile one statement, from whichever usage evidence the fixture carries.

    Two entry points share one body, because M1's two halves need different evidence:

    * **interval** — the customer's Green Button export, bucketed by this repo's own
      ``tou.rules``. This is M1b, and it is the only path that tests the parser and the
      bucketing.
    * **printed** — the per-TOU-period kWh the statement itself prints, with no export at
      all. This is M1a, whose DoD explicitly requires no interval data, and it is the path
      that can be run the same day one redacted SDG&E bill arrives.

    Both price through :func:`tariffs.bill.charge_lines`, so identical bucketed kWh give
    identical dollars; :mod:`tariffs.bucketed` has the reasons and the refusals.

    A fixture carrying **both** is cross-checked and then reconciled from the intervals,
    which are strictly the more informative of the two; a fixture carrying **neither** is
    refused by :class:`NoUsageEvidenceError` rather than being skipped, because a skip
    looks like a pass.
    """
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

    # Which usage evidence this fixture carries is settled BEFORE its expectations are
    # read: a fixture with no usage at all is refused as that, not as a missing
    # `expected:` block, and a fixture whose two sources disagree is refused before
    # either is priced.
    printed = printed_usage(fixture, name=name)
    if printed is None and series is None:
        raise NoUsageEvidenceError(
            f"{name} carries neither an interval export nor a `printed_usage:` block, so "
            "there is no usage to price. Supply one of:\n"
            "    - the household's Green Button export in data/ (the interval path, M1b), or\n"
            "    - `printed_usage.segments`, the per-TOU-period kWh the statement itself "
            "prints (the bill-only path, M1a — see sdge_BILL_ONLY_TEMPLATE.yaml.example).\n"
            "  This is an error and not a skip on purpose: a skipped reconciliation reads "
            "as a passing one in a green test run."
        )
    if printed is not None and series is not None:
        cross_check_printed_usage(
            printed,
            series,
            [deliv, gen],
            tolerance_kwh=printed_tolerance_kwh(fixture),
            name=name,
        )

    exp = fixture["expected"]
    obs = [
        LineItem(name=name_, amount=amt)
        for name_, amt in exp.get("observed_adjustments", {}).items()
        if amt is not None
    ]
    # Modeled, not observed. The fixture states what the statement actually credited; the
    # amount and the month come from the cited CPUC/utility table, so this line is a
    # prediction that the ±$2 gate checks — which an `observed_adjustments` entry never was.
    credit = credit_for(fixture_utility(fixture).value, ps, pe)

    if series is not None:
        usage_source = "interval"
        bill = compute_bill(
            series,
            [deliv, gen],
            ps,
            pe,
            care=care,
            observed_adjustments=obs,
            climate_credit=credit,
            **facts,
        )
    else:
        usage_source = "printed"
        facts.pop("event_days", None)  # no such argument: see compute_layer_from_usage
        bill = compute_bill_from_usage(
            printed,
            [deliv, gen],
            ps,
            pe,
            care=care,
            observed_adjustments=obs,
            climate_credit=credit,
            **facts,
        )

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
    # Modeled credits are compared against what the statement actually showed, so a wrong
    # amount or a wrong month lands in the residual instead of being absorbed.
    billed_credits = exp.get("modeled_adjustments", {})
    for a in bill.modeled_adjustments:
        rows.append(
            Row(
                section="adjustment", name=a.name, bill=billed_credits.get(a.name), modeled=a.amount
            )
        )
    for name_, amt in billed_credits.items():
        if not any(a.name == name_ for a in bill.modeled_adjustments):
            rows.append(Row(section="adjustment", name=name_, bill=amt, modeled=None))

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
        usage_source=usage_source,
    )


def format_comparison(r: ReconResult) -> str:
    """The printed line-item comparison (M0 DoD)."""
    lines = [
        f"Statement {r.statement_date}   period {r.period_start} .. {r.period_end}"
        f"   [{r.utility} {r.schedule_label}]",
        f"usage from: {r.usage_source}"
        + (
            "  (the statement's own per-TOU-period kWh; the utility's bucketing is taken as given)"
            if r.usage_source == "printed"
            else "  (Green Button export, bucketed by this repo's TOU rules)"
        ),
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
