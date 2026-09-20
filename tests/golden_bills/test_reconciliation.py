"""The reconciliation merge gate: every golden bill must model within its tolerance.

Golden fixtures are committed and anonymized. The real interval export is git-ignored;
the dollar tests skip when it is absent (CI without data) but run locally and in any env
that has the customer's data.

The rest of this file is the PLUMBING gate, and it needs no data at all. It exists
because the harness was PG&E-shaped for its whole life — a hardcoded filename glob, a
hardcoded parser import, and a ``compute_bill`` call that passed neither the climate
zone nor the PCIA vintage nor the event days, so an SDG&E fixture could not have been
reconciled at all. Discovering that on the day a customer's bill arrives is a session of
harness work under time pressure; these tests turn it into a fixture. They deliberately
assert no SDG&E dollar: no real SDG&E bill exists yet, and invariant 1 says a dollar
figure has to be earned against one.

Session 29 added a second entry point and a second plumbing gate below it. M1a's DoD is a
statement reconciled **from its own printed per-TOU-period kWh, with no interval export**,
because the ask that closes it is one redacted bill rather than a year of 15-minute data
(``notes/m1_without_dad_2026-09.md``). The same rule applies to that path: its tests need
no data, they fail loudly when a spec starts demanding something new, and they assert no
SDG&E dollar. What they *do* assert is parity — given identical bucketed kWh the two
paths produce identical dollars — which is measured on the PG&E golden bills, the only
place this repo holds both an interval export and a real statement.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from greenbutton import GreenButtonParseError
from greenbutton.models import Utility
from report.reconcile import (
    CUSTOMER_FACTS,
    DEFAULT_PRINTED_TOLERANCE_KWH,
    INTERVAL_GLOBS,
    AmbiguousIntervalExportError,
    FixtureError,
    MissingCustomerFactError,
    NoUsageEvidenceError,
    PrintedUsageDisagreementError,
    customer_facts,
    fixture_utility,
    format_comparison,
    interval_file_for,
    interval_files_for,
    load_fixture,
    parse_interval_file,
    printed_tolerance_kwh,
    printed_usage,
    reconcile,
    required_customer_facts,
)
from tariffs.bill import TimingDependentChargeError, compute_bill
from tariffs.bucketed import (
    SegmentCoverageError,
    SegmentStraddlesRateChangeError,
    UnbucketedPeriodError,
    UsageSegment,
    compute_bill_from_usage,
    segments_from_series,
)
from tariffs.climate_credit import credit_for
from tariffs.loader import load_spec_versions
from tariffs.schema import Layer, Service

GOLDEN = Path(__file__).parent
FIXTURES = sorted(GOLDEN.glob("*.yaml"))
SDGE_TEMPLATE = GOLDEN / "sdge_TEMPLATE.yaml.example"


def _series_for(utility: Utility):
    path = interval_file_for(utility)
    return None if path is None else parse_interval_file(utility, path)[0]


def test_fixtures_exist():
    assert FIXTURES, "no golden-bill fixtures committed"


@pytest.mark.parametrize("fx_path", FIXTURES, ids=lambda p: p.stem)
def test_bill_reconciles(fx_path):
    fixture = load_fixture(fx_path)
    utility = fixture_utility(fixture)
    series = _series_for(utility)
    if series is None:
        pytest.skip(f"real {utility.value} interval export not present")
    r = reconcile(fixture, series, name=fx_path.name)
    assert r.within_tolerance, "\n" + format_comparison(r)


# --- utility dispatch -------------------------------------------------------


@pytest.mark.parametrize("fx_path", FIXTURES, ids=lambda p: p.stem)
def test_every_fixture_names_a_utility_with_a_parser(fx_path):
    """The `utility:` field is load-bearing, not decoration.

    It was loaded and ignored until session 24 — the harness globbed PG&E's filename and
    called PG&E's parser regardless of what the fixture said.
    """
    assert fixture_utility(load_fixture(fx_path)) in INTERVAL_GLOBS


def test_unknown_utility_raises_rather_than_falling_back_to_pge():
    with pytest.raises(FixtureError, match="SCE"):
        fixture_utility({"utility": "SCE"})
    with pytest.raises(FixtureError, match="no `utility:` field"):
        fixture_utility({"statement_date": "01-29-2026"})


def _pge_csv() -> str:
    return (
        "Name,ANONYMIZED\n"
        "Address,ANONYMIZED\n"
        "\n"
        "TYPE,DATE,START TIME,END TIME,USAGE (kWh),COST,NOTES\n"
        "Electric usage,2026-01-01,00:00,00:59,0.5,$0.10,\n"
        "Electric usage,2026-01-01,01:00,01:59,0.4,$0.08,\n"
    )


def _sdge_csv() -> str:
    """The meter shape SDG&E's portal actually writes (session 13/23's real files)."""
    return (
        "Title,Electric Usage\n"
        "\n"
        "Meter Number,Date,Start Time,Duration,Consumption,Generation,Net\n"
        "00000000,1/1/2026,12:00 AM,60,0.5,0,0.5\n"
        "00000000,1/1/2026,1:00 AM,60,0.4,0,0.4\n"
    )


@pytest.mark.parametrize(
    ("utility", "text", "filename"),
    [
        (Utility.PGE, _pge_csv(), "pge_electric_usage_interval_data_x.csv"),
        (Utility.SDGE, _sdge_csv(), "Electric_60_Minute_1-1-2026_1-1-2026_20260102.csv"),
    ],
)
def test_dispatch_reads_each_utilitys_own_shape(tmp_path, utility, text, filename):
    p = tmp_path / filename
    p.write_text(text)
    assert interval_files_for(utility, tmp_path) == [p]
    series, _ = parse_interval_file(utility, p)
    assert round(float(series.frame["kwh"].sum()), 3) == 0.9


@pytest.mark.parametrize(
    ("utility", "text"),
    [(Utility.PGE, _sdge_csv()), (Utility.SDGE, _pge_csv())],
)
def test_dispatch_does_not_sniff_its_way_out_of_a_mislabeled_fixture(tmp_path, utility, text):
    """A fixture naming the wrong utility must fail, not be quietly re-detected.

    ``report.inspect`` sniffs on purpose — it is handed a file by someone who may not
    know what it is. Here the fixture asserts the utility, so sniffing would let a
    mislabeled fixture reconcile and hide the mislabeling.
    """
    p = tmp_path / "usage.csv"
    p.write_text(text)
    with pytest.raises(GreenButtonParseError):
        parse_interval_file(utility, p)


@pytest.mark.parametrize(
    "filename",
    [
        "PV_Electric_15_Minute_3-1-2024_2-28-2025_20250311.csv",
        "Electric_60_Minute_3-1-2024_2-28-2025_20250311.csv",
        "PV_Electric_15_Minute_2-1-2025_3-4-2025_20250311.csv",
        "sdge_electric_usage_interval_data_x.csv",
    ],
)
def test_the_real_sdge_export_filenames_are_matched(tmp_path, filename):
    """Every SDG&E export name actually observed in the wild.

    The first three are the Home Energy Analytics files surveyed in
    notes/sdge_public_exports_2026-09.md; the fourth is the documented range shape.
    """
    (tmp_path / filename).write_text("placeholder")
    assert [p.name for p in interval_files_for(Utility.SDGE, tmp_path)] == [filename]


@pytest.mark.parametrize(
    "filename",
    [
        "pge_electric_usage_interval_data_Service 1_1_2025-08-02_to_2026-07-18.csv",
        "pge_natural_gas_usage_interval_data_Service 2_2.csv",
        "pge_electric_billing_billing_data_Service 1_1.csv",
    ],
)
def test_sdge_globs_do_not_swallow_the_pge_or_gas_exports(tmp_path, filename):
    """data/ holds gas and billing-summary exports too; a bare *.csv would take them."""
    (tmp_path / filename).write_text("placeholder")
    assert interval_files_for(Utility.SDGE, tmp_path) == []


def test_only_the_pge_electric_interval_export_matches_pge(tmp_path):
    for name in (
        "pge_electric_usage_interval_data_Service 1_1_2025-08-02_to_2026-07-18.csv",
        "pge_natural_gas_usage_interval_data_Service 2_2.csv",
        "pge_electric_billing_billing_data_Service 1_1.csv",
        "Electric_60_Minute_3-1-2024_2-28-2025_20250311.csv",
    ):
        (tmp_path / name).write_text("placeholder")
    assert [p.name for p in interval_files_for(Utility.PGE, tmp_path)] == [
        "pge_electric_usage_interval_data_Service 1_1_2025-08-02_to_2026-07-18.csv"
    ]


def test_two_exports_for_one_utility_raise_rather_than_pick_alphabetically(tmp_path):
    """A tie here is a wrong dollar, not a missing one — the files may differ in range."""
    for name in (
        "Electric_60_Minute_3-1-2024_2-28-2025_20250311.csv",
        "Electric_60_Minute_2-1-2025_3-4-2025_20250311.csv",
    ):
        (tmp_path / name).write_text("placeholder")
    assert interval_file_for(Utility.PGE, tmp_path) is None
    with pytest.raises(AmbiguousIntervalExportError, match="2 SDG&E interval exports"):
        interval_file_for(Utility.SDGE, tmp_path)


# --- customer facts: raise, never default -----------------------------------


def _sdge_specs(*, generation_provider: str = "SDG&E", schedule: str = "TOU-DR1"):
    deliv = load_spec_versions(schedule, Layer.DELIVERY)
    gen = load_spec_versions(schedule, Layer.GENERATION, provider=generation_provider)
    return [*deliv, *gen]


def _sdge_fixture(customer: dict | None) -> dict:
    """A fixture skeleton with NO `expected:` block.

    Deliberate: there is no real SDG&E bill, so there are no SDG&E dollars to expect.
    These tests exercise the fact-threading, which happens before any arithmetic.
    """
    fx: dict = {
        "utility": "SDG&E",
        "customer_class": "standard",
        "specs": {"delivery": "TOU-DR1", "generation": "TOU-DR1"},
    }
    if customer is not None:
        fx["customer"] = customer
    return fx


def test_sdge_specs_demand_the_facts_the_engine_would_raise_on():
    need = required_customer_facts(_sdge_specs())
    assert set(need) == {"service", "territory", "vintage"}
    assert "coastal_basic" in need["territory"]
    assert "PCIA vintage" in need["vintage"]


def test_pge_specs_demand_only_service():
    """PG&E's delivery spec pins its territory (T) and its PCIA vintage, so it needs
    neither — but it does carry `applies_to: cca` lines, and `service` used to default
    silently to CCA inside compute_bill."""
    specs = [
        *load_spec_versions("E-TOU-C", Layer.DELIVERY),
        *load_spec_versions("MBRETCH1", Layer.GENERATION),
    ]
    assert set(required_customer_facts(specs)) == {"service"}


@pytest.mark.parametrize("fact", ["service", "territory", "vintage"])
def test_an_sdge_fixture_missing_one_fact_fails_by_name(fact):
    full = {"service": "cca", "territory": "coastal_basic", "vintage": "2018"}
    del full[fact]
    with pytest.raises(MissingCustomerFactError) as e:
        customer_facts(_sdge_fixture(full), _sdge_specs(), name="sdge_fake.yaml")
    msg = str(e.value)
    assert fact in msg and "sdge_fake.yaml" in msg
    assert "no default" in msg


def test_an_sdge_fixture_with_no_customer_block_names_every_missing_fact():
    with pytest.raises(MissingCustomerFactError) as e:
        customer_facts(_sdge_fixture(None), _sdge_specs(), name="sdge_fake.yaml")
    msg = str(e.value)
    assert all(f in msg for f in ("service", "territory", "vintage"))


def test_tou_dr_p_additionally_demands_event_days():
    specs = _sdge_specs(schedule="TOU-DR-P")
    assert "event_days" in required_customer_facts(specs)
    with pytest.raises(MissingCustomerFactError, match="event_days"):
        customer_facts(
            _sdge_fixture({"service": "bundled", "territory": "coastal_basic"}),
            specs,
            name="sdge_fake.yaml",
        )
    facts = customer_facts(
        _sdge_fixture({"service": "bundled", "territory": "coastal_basic", "event_days": []}),
        specs,
        name="sdge_fake.yaml",
    )
    assert facts["event_days"] == []  # the explicit zero-event case, on the record


def test_supplied_facts_reach_compute_bill_in_its_own_vocabulary():
    facts = customer_facts(
        _sdge_fixture(
            {
                "service": "cca",
                "territory": "inland_all_electric",
                "vintage": 2018,  # YAML may hand us an int; the tariff keys are strings
                "event_days": ["2026-09-05"],
            }
        ),
        _sdge_specs(),
        name="sdge_fake.yaml",
    )
    assert facts["service"].value == "cca"
    assert facts["territory"] == "inland_all_electric"
    assert facts["vintage"] == "2018"
    assert facts["event_days"] == [date(2026, 9, 5)]
    assert set(facts) <= set(CUSTOMER_FACTS)


def test_a_typo_in_a_customer_fact_is_refused_not_ignored():
    with pytest.raises(FixtureError, match="climate_zone"):
        customer_facts(
            _sdge_fixture({"service": "cca", "climate_zone": "coastal_basic"}),
            _sdge_specs(),
            name="sdge_fake.yaml",
        )


def test_an_unknown_service_is_refused():
    with pytest.raises(FixtureError, match=r"customer\.service"):
        customer_facts(
            _sdge_fixture(
                {"service": "direct-access", "territory": "coastal_basic", "vintage": "2018"}
            ),
            _sdge_specs(),
            name="sdge_fake.yaml",
        )


@pytest.mark.parametrize("fx_path", FIXTURES, ids=lambda p: p.stem)
def test_every_committed_fixture_declares_what_its_specs_demand(fx_path):
    """Runs with no interval data, so CI proves the fixtures are complete even where it
    cannot prove they reconcile."""
    fixture = load_fixture(fx_path)
    spec_ids = fixture["specs"]
    specs = [
        *load_spec_versions(
            spec_ids["delivery"], Layer.DELIVERY, provider=spec_ids.get("delivery_provider")
        ),
        *load_spec_versions(
            spec_ids["generation"],
            Layer.GENERATION,
            provider=spec_ids.get("generation_provider"),
        ),
    ]
    customer_facts(fixture, specs, name=fx_path.name)  # raises if one is missing


# --- the template ------------------------------------------------------------


def test_the_sdge_template_is_not_picked_up_as_a_fixture():
    assert SDGE_TEMPLATE.exists()
    assert SDGE_TEMPLATE not in FIXTURES


def test_the_sdge_template_declares_every_fact_the_sdge_specs_demand():
    """Keeps the template honest: a spec that starts demanding a new customer fact fails
    here, rather than being discovered while a real bill is waiting."""
    fixture = yaml.safe_load(SDGE_TEMPLATE.read_text())
    specs = _sdge_specs(generation_provider=fixture["specs"]["generation_provider"])
    facts = customer_facts(fixture, specs, name=SDGE_TEMPLATE.name)
    assert facts["territory"] in ("coastal_basic",)


def test_the_sdge_template_carries_no_dollar_figures():
    """Invariant 1: no SDG&E dollar may be committed before a real SDG&E bill earns it."""
    exp = yaml.safe_load(SDGE_TEMPLATE.read_text())["expected"]
    assert exp["delivery"]["line_items"] == {}
    assert exp["generation"]["line_items"] == {}
    assert exp["observed_adjustments"] == {}
    assert exp["electric_net_total"] is None
    assert exp["delivery"]["total"] is None and exp["generation"]["total"] is None


# --- end to end: reconcile() itself threads the facts -----------------------


def _sdge_month_csv(kwh: float = 0.5, days: int = 31, month: int = 1, year: int = 2026) -> str:
    """A month of hourly SDG&E meter-shape rows. Synthetic; no real usage data."""
    rows = [
        "Title,Electric Usage",
        "",
        "Meter Number,Date,Start Time,Duration,Consumption,Generation,Net",
    ]
    for d in range(1, days + 1):
        for h in range(24):
            suffix = "AM" if h < 12 else "PM"
            rows.append(f"00000000,{month}/{d}/{year},{h % 12 or 12}:00 {suffix},60,{kwh},0,{kwh}")
    return "\n".join(rows) + "\n"


def _sdge_series(tmp_path, kwh: float = 0.5):
    p = tmp_path / "Electric_60_Minute_1-1-2026_1-31-2026_20260201.csv"
    p.write_text(_sdge_month_csv(kwh))
    assert interval_file_for(Utility.SDGE, tmp_path) == p  # dispatch, by filename
    return parse_interval_file(Utility.SDGE, p)[0]


def _sdge_period_fixture(customer: dict) -> dict:
    fx = _sdge_fixture(customer)
    fx["statement_date"] = "02-01-2026"
    fx["period_start"] = "2026-01-01"
    fx["period_end"] = "2026-01-31"
    fx["specs"]["generation_provider"] = "SDG&E"
    return fx


def test_reconcile_gates_an_sdge_fixture_before_it_computes_anything(tmp_path):
    """The fact gate runs inside ``reconcile``, not only when called directly.

    Before session 24 this fixture reached ``compute_bill`` with no territory and no
    vintage and blew up inside the tariff engine — or, worse, was billed as a CCA
    customer because ``service`` defaulted to ``Service.CCA``.
    """
    fx = _sdge_period_fixture({"service": "bundled"})  # territory withheld
    with pytest.raises(MissingCustomerFactError, match="territory"):
        reconcile(fx, _sdge_series(tmp_path), name="sdge_fake.yaml")


def test_a_complete_sdge_fixture_gets_all_the_way_through_compute_bill(tmp_path):
    """Proves the threading, and deliberately proves no dollar.

    Two halves. First: with the customer facts supplied, ``reconcile`` gets past the fact
    gate and stops on the absent ``expected:`` block — the only thing still missing is a
    real SDG&E bill to compare against. Second: the very same facts drive ``compute_bill``
    to a full itemised SDG&E bill without raising, which is the substantive claim, since
    the delivery spec raises on a missing climate zone and the PCIA on a missing vintage.
    No dollar is asserted: invariant 1 says an SDG&E dollar has to be earned against a
    real statement, and none exists yet.
    """
    from tariffs.bill import compute_bill

    fx = _sdge_period_fixture({"service": "bundled", "territory": "coastal_basic"})
    series = _sdge_series(tmp_path)
    with pytest.raises(KeyError, match="expected"):
        reconcile(fx, series, name="sdge_fake.yaml")

    specs = _sdge_specs()
    facts = customer_facts(fx, specs, name="sdge_fake.yaml")
    bill = compute_bill(
        series,
        [
            [s for s in specs if s.layer is Layer.DELIVERY],
            [s for s in specs if s.layer is Layer.GENERATION],
        ],
        date(2026, 1, 1),
        date(2026, 1, 31),
        **facts,
    )
    assert [layer.layer for layer in bill.layers] == [Layer.DELIVERY, Layer.GENERATION]
    assert all(layer.line_items for layer in bill.layers)
    # `service: bundled` reached the engine: the CCA-only PCIA line is absent, which is
    # the line the old `service=Service.CCA` default would have billed this household.
    assert not [li for li in bill.layers[0].line_items if "Power Charge Indifference" in li.name]


def test_the_climate_zone_the_fixture_supplies_actually_moves_the_bill(tmp_path):
    """Why the gate exists: the zone is not cosmetic.

    Same synthetic month, same schedule, two zones — the baseline credit differs by tens
    of dollars on a single statement, because the allowance it is capped against nearly
    doubles between them. A harness that defaulted the zone would return a confident
    wrong number instead of an error, and nothing on the bill would look wrong.
    """
    from tariffs.bill import compute_bill

    series = _sdge_series(tmp_path, kwh=1.5)  # 36 kWh/day: above every zone's allowance
    specs = _sdge_specs()

    def credit(zone: str) -> float:
        fx = _sdge_period_fixture({"service": "bundled", "territory": zone})
        bill = compute_bill(
            series,
            [
                [s for s in specs if s.layer is Layer.DELIVERY],
                [s for s in specs if s.layer is Layer.GENERATION],
            ],
            date(2026, 1, 1),
            date(2026, 1, 31),
            **customer_facts(fx, specs, name="sdge_fake.yaml"),
        )
        return bill.layers[0].bucket()["Baseline Credit"]

    gap = abs(credit("coastal_basic") - credit("desert_all_electric"))
    assert gap > 20.0, f"one month, two climate zones, only ${gap:.2f} apart"


# --- the bill-only path (M1a) -----------------------------------------------
#
# M1a's DoD is a statement reconciled from its OWN per-TOU-period kWh, with no interval
# export (ROADMAP, amended 2026-09-16). Everything from here down needs no data, for the
# same reason the dispatch gate above needs none: the harness work has to be finished
# BEFORE the first real SDG&E bill lands, not discovered on the day it does. And as
# above, no SDG&E dollar is asserted anywhere — none has been earned.

BILL_ONLY_TEMPLATE = GOLDEN / "sdge_BILL_ONLY_TEMPLATE.yaml.example"


def _sdge_layers(*, generation_provider: str = "SDG&E", schedule: str = "TOU-DR1"):
    """(delivery versions, generation versions) — the shape compute_bill wants."""
    return (
        load_spec_versions(schedule, Layer.DELIVERY),
        load_spec_versions(schedule, Layer.GENERATION, provider=generation_provider),
    )


def _seg(start: str, end: str, **kwh) -> UsageSegment:
    return UsageSegment(start=date.fromisoformat(start), end=date.fromisoformat(end), kwh=kwh)


# --- parity: the two paths are one charge layer ------------------------------


@pytest.mark.parametrize("fx_path", FIXTURES, ids=lambda p: p.stem)
def test_the_two_paths_produce_identical_dollars_on_every_golden_bill(fx_path):
    """The substantive claim of the bill-only path, measured where both inputs exist.

    The eleven PG&E golden bills are the only place this repo holds a real interval
    export AND a real statement, so they are the only place the bill-only path can be
    validated before a bill-only fixture exists. Bucket their real intervals the way a
    statement would print them, price those buckets, and every line must land on the
    interval path's line to the cent — not within the ±$2 gate, EXACTLY, because the two
    paths are supposed to be the same arithmetic reached by different roads.

    Mutation-checked while writing: changing any rate, rounding or line name reached by
    one path and not the other is impossible by construction, which is the point —
    ``tariffs.bill.charge_lines`` is the only copy.
    """
    fixture = load_fixture(fx_path)
    utility = fixture_utility(fixture)
    series = _series_for(utility)
    if series is None:
        pytest.skip(f"real {utility.value} interval export not present")

    ps = date.fromisoformat(fixture["period_start"])
    pe = date.fromisoformat(fixture["period_end"])
    spec_ids = fixture["specs"]
    layers = [
        load_spec_versions(
            spec_ids["delivery"], Layer.DELIVERY, provider=spec_ids.get("delivery_provider")
        ),
        load_spec_versions(
            spec_ids["generation"], Layer.GENERATION, provider=spec_ids.get("generation_provider")
        ),
    ]
    facts = customer_facts(fixture, [s for versions in layers for s in versions], name=fx_path.name)
    care = fixture.get("customer_class") == "CARE"
    credit = credit_for(utility.value, ps, pe)

    from_intervals = compute_bill(series, layers, ps, pe, care=care, climate_credit=credit, **facts)
    segments = segments_from_series(series, layers, ps, pe)
    from_printed = compute_bill_from_usage(
        segments, layers, ps, pe, care=care, climate_credit=credit, **facts
    )

    assert from_printed.total == from_intervals.total
    for printed, metered in zip(from_printed.layers, from_intervals.layers, strict=True):
        assert printed.bucket() == metered.bucket()
        assert printed.total == metered.total


@pytest.mark.parametrize("fx_path", FIXTURES, ids=lambda p: p.stem)
def test_reconcile_dispatches_to_the_bill_only_path_and_lands_on_the_same_residual(fx_path):
    """Parity again, but through ``reconcile`` — the thing a fixture actually calls.

    Separate from the test above because the dispatch, the customer-fact gate, the
    climate credit and the observed adjustments all sit between a fixture and
    ``compute_bill``, and a bill-only fixture meets every one of them.
    """
    fixture = load_fixture(fx_path)
    series = _series_for(fixture_utility(fixture))
    if series is None:
        pytest.skip("real interval export not present")

    spec_ids = fixture["specs"]
    layers = [
        load_spec_versions(
            spec_ids["delivery"], Layer.DELIVERY, provider=spec_ids.get("delivery_provider")
        ),
        load_spec_versions(
            spec_ids["generation"], Layer.GENERATION, provider=spec_ids.get("generation_provider")
        ),
    ]
    ps = date.fromisoformat(fixture["period_start"])
    pe = date.fromisoformat(fixture["period_end"])
    bill_only = dict(fixture)
    bill_only["printed_usage"] = {
        "segments": [
            {"start": s.start, "end": s.end, "kwh": dict(s.kwh)}
            for s in segments_from_series(series, layers, ps, pe)
        ]
    }

    from_intervals = reconcile(fixture, series, name=fx_path.name)
    from_printed = reconcile(bill_only, None, name=fx_path.name)

    assert from_printed.usage_source == "printed"
    assert from_intervals.usage_source == "interval"
    assert from_printed.net_modeled == from_intervals.net_modeled
    assert from_printed.delta == from_intervals.delta
    assert [(r.section, r.name, r.modeled) for r in from_printed.rows] == [
        (r.section, r.name, r.modeled) for r in from_intervals.rows
    ]
    # And the statement itself is still reproduced — the bill-only path is not a
    # different answer that merely agrees with the old one's bug.
    assert from_printed.within_tolerance, "\n" + format_comparison(from_printed)


# --- the two paths agree on SDG&E-shaped specs too, with no data and no dollar ---


def test_the_two_paths_agree_on_the_sdge_charge_structure(tmp_path):
    """Parity where PG&E cannot reach: the baseline allowance TABLE and the minimum bill.

    PG&E's specs pin one territory and carry no minimum bill, so the golden-bill parity
    test above never exercises ``Baseline.allowances`` or ``minimum_bill_line`` — exactly
    the two blocks SDG&E adds. A synthetic month drives both paths here and they must
    agree line for line. **No amount is asserted**: the load is synthetic and invariant 1
    says an SDG&E dollar is earned against a real statement, not against this.
    """
    series = _sdge_series(tmp_path)
    deliv, gen = _sdge_layers()
    ps, pe = date(2026, 1, 1), date(2026, 1, 31)
    facts = customer_facts(
        _sdge_period_fixture({"service": "cca", "territory": "coastal_basic", "vintage": "2018"}),
        [*deliv, *gen],
        name="sdge_fake.yaml",
    )
    from_intervals = compute_bill(series, [deliv, gen], ps, pe, **facts)
    segments = segments_from_series(series, [deliv, gen], ps, pe)
    from_printed = compute_bill_from_usage(segments, [deliv, gen], ps, pe, **facts)

    assert from_printed.total == from_intervals.total
    for printed, metered in zip(from_printed.layers, from_intervals.layers, strict=True):
        assert printed.bucket() == metered.bucket()
    # The blocks this test exists for were actually reached.
    assert "Baseline Credit" in from_printed.layers[0].bucket()
    assert any("Power Charge Indifference" in n for n in from_printed.layers[0].bucket())


# --- refusals: what printed buckets cannot do -------------------------------


def test_a_fixture_with_neither_an_export_nor_printed_kwh_is_refused_not_skipped():
    """A skipped reconciliation reads as a passing one in a green run."""
    fx = _sdge_period_fixture({"service": "bundled", "territory": "coastal_basic"})
    with pytest.raises(NoUsageEvidenceError) as e:
        reconcile(fx, None, name="sdge_fake.yaml")
    msg = str(e.value)
    assert "printed_usage" in msg and "sdge_BILL_ONLY_TEMPLATE" in msg


def test_printed_kwh_that_contradicts_the_export_is_refused_by_period(tmp_path):
    """A fixture holding both is the only place M1b's bucketing claim can be measured.

    Holding them and not comparing them would waste the one cross-check available, so the
    disagreement is reported per TOU period with both numbers, and neither is used.
    """
    series = _sdge_series(tmp_path)  # 0.5 kWh every hour of January 2026
    fx = _sdge_period_fixture({"service": "bundled", "territory": "coastal_basic"})
    truth = segments_from_series(series, list(_sdge_layers()), date(2026, 1, 1), date(2026, 1, 31))
    wrong = dict(truth[0].kwh)
    wrong["on_peak"] = wrong["on_peak"] + 40.0
    fx["printed_usage"] = {
        "segments": [{"start": truth[0].start, "end": truth[0].end, "kwh": wrong}]
    }
    with pytest.raises(PrintedUsageDisagreementError) as e:
        reconcile(fx, series, name="sdge_fake.yaml")
    msg = str(e.value)
    assert "on_peak" in msg and "+40.00" in msg.replace("-40.00", "+40.00")


def test_a_transcription_inside_the_printing_tolerance_is_accepted(tmp_path):
    """SDG&E prints kWh to the whole kWh; the tolerance exists for that and nothing more."""
    series = _sdge_series(tmp_path)
    fx = _sdge_period_fixture({"service": "bundled", "territory": "coastal_basic"})
    truth = segments_from_series(series, list(_sdge_layers()), date(2026, 1, 1), date(2026, 1, 31))
    rounded = {p: round(v) for p, v in truth[0].kwh.items()}
    fx["printed_usage"] = {
        "segments": [{"start": truth[0].start, "end": truth[0].end, "kwh": rounded}]
    }
    with pytest.raises(KeyError, match="expected"):  # got past the cross-check; no bill to expect
        reconcile(fx, series, name="sdge_fake.yaml")


def test_a_segment_spanning_an_sdge_rate_change_is_refused_not_split_pro_rata():
    """The case that makes this a LIST of segments rather than one bucket set.

    SDG&E filed five 2026 TOU-DR1 vintages, so an ordinary 30-day statement straddles a
    rate change more often than not. Printed buckets say how much energy fell in each TOU
    period and never on which side of the change it fell.
    """
    deliv, gen = _sdge_layers()
    with pytest.raises(SegmentStraddlesRateChangeError) as e:
        compute_bill_from_usage(
            [_seg("2026-04-15", "2026-05-14", on_peak=80, off_peak=200, super_off_peak=120)],
            [deliv, gen],
            date(2026, 4, 15),
            date(2026, 5, 14),
            service=Service.BUNDLED,
            territory="coastal_basic",
        )
    msg = str(e.value)
    assert "2026-04-15..2026-05-14" in msg and "2026-05-01" in msg


def test_a_segment_spanning_the_summer_boundary_is_refused_even_at_constant_rates():
    """Season is a rate change the tariff makes, not one the utility files.

    Nov 1 on SDG&E: no filed rate change sits there (the latest 2026 vintage is 8/1), and
    the delivery energy rate is flat across all six season/period cells anyway — but the
    generation rate is not, and the baseline allowance is not. A statement that spans it
    still cannot be priced from one bucket set.
    """
    deliv, gen = _sdge_layers()
    with pytest.raises(SegmentStraddlesRateChangeError) as e:
        compute_bill_from_usage(
            [_seg("2026-10-20", "2026-11-18", on_peak=80, off_peak=200, super_off_peak=120)],
            [deliv, gen],
            date(2026, 10, 20),
            date(2026, 11, 18),
            service=Service.BUNDLED,
            territory="coastal_basic",
        )
    assert "2026-11-01" in str(e.value) and "season" in str(e.value)


def test_segments_split_at_the_statements_own_blocks_price_fine():
    """The other half of the previous two tests: the fix is transcription, not code."""
    deliv, gen = _sdge_layers()
    bill = compute_bill_from_usage(
        [
            _seg("2026-04-15", "2026-04-30", on_peak=40, off_peak=100, super_off_peak=60),
            _seg("2026-05-01", "2026-05-14", on_peak=40, off_peak=100, super_off_peak=60),
        ],
        [deliv, gen],
        date(2026, 4, 15),
        date(2026, 5, 14),
        service=Service.BUNDLED,
        territory="coastal_basic",
    )
    assert [layer.layer for layer in bill.layers] == [Layer.DELIVERY, Layer.GENERATION]
    assert bill.total_kwh == 400.0
    # `service: bundled` reached the engine through this path too.
    assert not [n for n in bill.layers[0].bucket() if "Power Charge Indifference" in n]


@pytest.mark.parametrize(
    ("segments", "match"),
    [
        ([("2026-01-02", "2026-01-31")], "billing period"),  # starts late
        ([("2026-01-01", "2026-01-30")], "billing period"),  # ends early
        ([("2026-01-01", "2026-01-10"), ("2026-01-12", "2026-01-31")], "gap"),
        ([("2026-01-01", "2026-01-15"), ("2026-01-10", "2026-01-31")], "overlap"),
    ],
)
def test_segments_that_do_not_tile_the_billing_period_are_refused(segments, match):
    """A missed day is a missed Base Services Charge and a smaller baseline allowance."""
    deliv, gen = _sdge_layers()
    with pytest.raises(SegmentCoverageError, match=match):
        compute_bill_from_usage(
            [_seg(a, b, on_peak=10, off_peak=20, super_off_peak=10) for a, b in segments],
            [deliv, gen],
            date(2026, 1, 1),
            date(2026, 1, 31),
            service=Service.BUNDLED,
            territory="coastal_basic",
        )


def test_a_tou_period_left_out_of_a_segment_is_refused_rather_than_read_as_zero():
    """Reading an omitted bucket as zero is indistinguishable from reading a typo as zero."""
    deliv, gen = _sdge_layers()
    with pytest.raises(UnbucketedPeriodError) as e:
        compute_bill_from_usage(
            [_seg("2026-01-01", "2026-01-31", on_peak=80, off_peak=200)],
            [deliv, gen],
            date(2026, 1, 1),
            date(2026, 1, 31),
            service=Service.BUNDLED,
            territory="coastal_basic",
        )
    assert "super_off_peak" in str(e.value) and "write 0 explicitly" in str(e.value)


def test_a_tou_period_the_schedule_does_not_bill_is_refused():
    deliv, gen = _sdge_layers()
    with pytest.raises(UnbucketedPeriodError, match="mid_peak"):
        compute_bill_from_usage(
            [
                _seg(
                    "2026-01-01",
                    "2026-01-31",
                    on_peak=80,
                    off_peak=200,
                    super_off_peak=1,
                    mid_peak=1,
                )
            ],
            [deliv, gen],
            date(2026, 1, 1),
            date(2026, 1, 31),
            service=Service.BUNDLED,
            territory="coastal_basic",
        )


def test_tou_dr_p_cannot_be_reconciled_from_printed_buckets_at_all():
    """The one charge in the SDG&E book that printed per-period kWh cannot reach.

    The RYU Event Period Adder is billed on kWh inside 16:00-21:00 ON the days SDG&E
    called — strictly finer than any bucket a statement prints. Zero is both the usual
    outcome and the flattering one, so this raises by name instead.
    """
    deliv, gen = _sdge_layers(schedule="TOU-DR-P")
    with pytest.raises(TimingDependentChargeError) as e:
        compute_bill_from_usage(
            [_seg("2026-06-01", "2026-06-30", on_peak=80, off_peak=200, super_off_peak=120)],
            [deliv, gen],
            date(2026, 6, 1),
            date(2026, 6, 30),
            service=Service.BUNDLED,
            territory="coastal_basic",
        )
    msg = str(e.value)
    assert "RYU" in msg and "16:00-21:00" in msg and "interval data" in msg


def test_the_interval_path_still_bills_the_event_adder(tmp_path):
    """The refusal above is about the bill-only path, not about the adder.

    Stated as a test because a refusal that had quietly disabled the charge everywhere
    would look identical from the bill-only side.
    """
    series = _sdge_series(tmp_path)
    deliv, gen = _sdge_layers(schedule="TOU-DR-P")
    bill = compute_bill(
        series,
        [deliv, gen],
        date(2026, 1, 1),
        date(2026, 1, 31),
        service=Service.BUNDLED,
        territory="coastal_basic",
        event_days=[date(2026, 1, 15)],
        allow_before_effective=True,
    )
    ryu = [n for n in bill.layers[1].bucket() if "RYU" in n or "Event" in n]
    assert ryu, bill.layers[1].bucket()


# --- the bill-only template --------------------------------------------------


def test_the_bill_only_template_is_not_picked_up_as_a_fixture():
    assert BILL_ONLY_TEMPLATE.exists()
    assert BILL_ONLY_TEMPLATE not in FIXTURES
    assert BILL_ONLY_TEMPLATE.suffixes[-1] == ".example"


def test_the_bill_only_template_declares_every_fact_the_sdge_specs_demand():
    """Same gate as the interval template: a spec that starts demanding a new customer
    fact fails here, rather than being discovered while a real bill is waiting."""
    fixture = yaml.safe_load(BILL_ONLY_TEMPLATE.read_text())
    specs = _sdge_specs(generation_provider=fixture["specs"]["generation_provider"])
    facts = customer_facts(fixture, specs, name=BILL_ONLY_TEMPLATE.name)
    assert facts["territory"] in ("coastal_basic",)


def test_the_bill_only_template_buckets_exactly_the_periods_the_sdge_specs_bill():
    """The bill-only analogue of the customer-fact gate, and the reason it is needed:
    a schedule that gained a fourth TOU period would make every transcription of this
    template silently incomplete, and the engine would refuse the fixture on the day the
    bill arrived instead of here."""
    fixture = yaml.safe_load(BILL_ONLY_TEMPLATE.read_text())
    deliv, gen = _sdge_layers(generation_provider=fixture["specs"]["generation_provider"])
    expected = set(deliv[-1].tou.periods)
    assert expected == set(gen[-1].tou.periods), "layers disagree about the period set"
    for seg in fixture["printed_usage"]["segments"]:
        assert set(seg["kwh"]) == expected


def test_the_bill_only_template_carries_no_dollar_figures():
    """Invariant 1: no SDG&E dollar may be committed before a real SDG&E bill earns it."""
    exp = yaml.safe_load(BILL_ONLY_TEMPLATE.read_text())["expected"]
    assert exp["delivery"]["line_items"] == {}
    assert exp["generation"]["line_items"] == {}
    assert exp["observed_adjustments"] == {}
    assert exp["electric_net_total"] is None
    assert exp["delivery"]["total"] is None and exp["generation"]["total"] is None


def test_the_bill_only_template_carries_no_kwh_figures_and_says_so_by_name():
    """A load is an expectation too. The template ships blank and refuses to be priced,
    naming the period that is unfilled — because an unfilled bucket read as zero is a
    fabricated usage figure, and it lowers the bill."""
    fixture = yaml.safe_load(BILL_ONLY_TEMPLATE.read_text())
    for seg in fixture["printed_usage"]["segments"]:
        assert all(v is None for v in seg["kwh"].values())
    with pytest.raises(FixtureError) as e:
        printed_usage(fixture, name=BILL_ONLY_TEMPLATE.name)
    msg = str(e.value)
    assert "is blank" in msg and BILL_ONLY_TEMPLATE.name in msg


def test_the_bill_only_templates_tolerance_is_the_harness_default():
    """Kept in step deliberately: a template that quietly widened the cross-check would
    be advice to ignore a disagreement."""
    fixture = yaml.safe_load(BILL_ONLY_TEMPLATE.read_text())
    assert fixture["printed_usage"]["tolerance_kwh"] == DEFAULT_PRINTED_TOLERANCE_KWH
    assert printed_tolerance_kwh(fixture) == DEFAULT_PRINTED_TOLERANCE_KWH


def test_a_fixture_with_no_printed_usage_block_is_not_a_bill_only_fixture():
    assert printed_usage({"utility": "SDG&E"}) is None


@pytest.mark.parametrize(
    ("block", "match"),
    [
        ({"segments": []}, "non-empty list"),
        ({"segments": [{"start": "2026-01-01", "kwh": {"on_peak": 1}}]}, r"\['end'\]"),
        ({"segments": [{"start": "2026-01-01", "end": "2026-01-31"}]}, r"\['kwh'\]"),
        (
            {"segments": [{"start": "2026-01-01", "end": "2026-01-31", "kwh": {"on_peak": "x"}}]},
            "not a number",
        ),
        (
            {"segments": [{"start": "nope", "end": "2026-01-31", "kwh": {"on_peak": 1}}]},
            "not a YYYY-MM-DD date",
        ),
        ({"segmets": []}, "unknown printed_usage key"),
    ],
)
def test_a_malformed_printed_usage_block_is_refused_by_name(block, match):
    with pytest.raises(FixtureError, match=match):
        printed_usage({"printed_usage": block}, name="sdge_fake.yaml")


@pytest.mark.parametrize("fx_path", FIXTURES, ids=lambda p: p.stem)
def test_every_committed_fixture_offers_some_usage_evidence(fx_path):
    """Needs no data: a fixture with no export in data/ AND no printed block would skip
    forever rather than fail, which is the failure mode this whole section exists for."""
    fixture = load_fixture(fx_path)
    has_printed = printed_usage(fixture, name=fx_path.name) is not None
    has_export_glob = bool(INTERVAL_GLOBS[fixture_utility(fixture)])
    assert has_printed or has_export_glob
