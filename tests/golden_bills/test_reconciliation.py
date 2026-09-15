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
    INTERVAL_GLOBS,
    AmbiguousIntervalExportError,
    FixtureError,
    MissingCustomerFactError,
    customer_facts,
    fixture_utility,
    format_comparison,
    interval_file_for,
    interval_files_for,
    load_fixture,
    parse_interval_file,
    reconcile,
    required_customer_facts,
)
from tariffs.loader import load_spec_versions
from tariffs.schema import Layer

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
