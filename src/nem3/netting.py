"""Net Billing Tariff settlement: gross imports billed retail, gross exports credited at ACC.

This is the module that turns "how much solar do I make?" into "what does my bill say?",
and almost every simplification a consumer calculator makes lives here. Schedule NBT
(PG&E Cal. P.U.C. Sheets 57358-E / 57359-E, Special Condition 2) is explicit:

    "Net Billing Tariff customers will be billed based on **no netting** of imports
    (consumption) and exports (generation to the grid)."

so the model is *not* "net kWh x retail rate". It is four separate ledgers:

1. **Imports** are billed on the customer's Otherwise Applicable Schedule (OAS) at full
   retail, on the metered import channel — the same :func:`tariffs.bill.compute_layer`
   that reconciles the golden bills.
2. **Exports** earn the ACC Export Compensation Rate, accrued **separately for delivery
   and generation** (SC 2.d). Delivery credits may only offset volumetric delivery
   charges; generation credits only volumetric generation charges.
3. **Non-bypassable charges** (Public Purpose Program, Nuclear Decommissioning,
   Competition Transition, Wildfire Fund) are billed on *gross* imports and no export
   credit may touch them (SC 2.f). This is the import floor — invariant 4.
4. **ACC Plus** is the one credit that "may be used to offset any charges incurred by the
   customer" (SC 2.c), NBCs and fixed charges included.

Three consequences that separate this from a generic calculator, each of which makes
payback *worse* than the naive model and so must not be quietly dropped:

- **Credits cannot make a bill negative within a month.** They also cannot offset the
  base services charge, the minimum bill, taxes or surcharges (SC 2.d). A household that
  zeroes out its energy still pays the fixed layer every month.
- **The two credit buckets do not fungibly combine.** Delivery credit stranded because
  there are no delivery charges left to offset does not pay a generation charge. It
  carries forward instead (SC 2.e).
- **A CCA customer's generation credit is not the utility's to pay.** SC 2.a: for a DA or
  CCA customer, "credits associated with the generation components of a customer's export
  credits, if any, do not reduce the charges owed to PG&E". SDG&E says the same on its
  export-pricing files: the posted generation rates apply to non-CCA customers only.
  :class:`NbtSettings` therefore refuses to credit the generation component to a CCA
  customer unless the caller supplies the CCA's own export terms.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
from pydantic import BaseModel, ConfigDict

from greenbutton.models import COL_KWH, LOCAL_TZ, Direction, IntervalSeries
from tariffs.bill import LayerBill, compute_layer
from tariffs.schema import Layer, Service, TariffSpec

from .acc import COMPONENTS, ExportRateSchedule

# --- inputs ----------------------------------------------------------------------------


class CcaExportTerms(BaseModel):
    """A CCA's own export compensation for the generation component.

    Required before a CCA customer's generation exports can be credited at all: the
    utility's posted generation table explicitly does not apply to them. A CCA that
    matches the utility's ACC values is the common case, but "commonly true" is not a
    citation, so the caller must say so and supply the source.
    """

    model_config = ConfigDict(frozen=True)

    provider: str
    matches_utility_acc: bool
    citation: str


@dataclass(frozen=True)
class NbtSettings:
    """Customer facts the NBT settlement needs beyond the tariff specs themselves."""

    care: bool = False
    service: Service = Service.CCA
    territory: str | None = None
    low_income: bool = False
    """Drives the ACC Plus tier. NBT's definition is broader than CARE — it also covers
    resident-owners in disadvantaged communities and customers in California Indian
    Country (Sheet 60435-E), so it is a separate flag, not ``care``."""
    acc_plus_eligible: bool = True
    """False for NEM/NEM2 transition customers, change-of-party buyers, non-residential
    customers, and code-mandated systems (Sheet 57353-E)."""
    cca_export_terms: CcaExportTerms | None = None


# --- credit ledger ---------------------------------------------------------------------


@dataclass
class CreditBalance:
    """Unused export credits carried between billing periods.

    SC 2.e: "Unused generation and delivery export credits accrued in a given month can be
    applied to offset generation and delivery volumetric (kWh) charges within a customers'
    Relevant Period. Any excess ... will be carried forward to the customer's next
    Relevant Period." Kept as three buckets because they are not interchangeable.
    """

    delivery: float = 0.0
    generation: float = 0.0
    acc_plus: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "delivery": round(self.delivery, 2),
            "generation": round(self.generation, 2),
            "acc_plus": round(self.acc_plus, 2),
        }


# --- outputs ---------------------------------------------------------------------------


class LayerSettlement(BaseModel):
    """How one layer's retail charges split into offsettable and protected amounts."""

    model_config = ConfigDict(frozen=True)

    layer: Layer
    total: float
    volumetric: float
    """Per-kWh charges (energy, baseline credit, CARE discount, per-kWh adders)."""
    non_bypassable: float
    """The NBC portion of those charges — billed on gross imports, never offsettable."""
    offsettable: float
    """volumetric - non_bypassable, floored at 0: what an export credit may reach."""
    protected: float
    """total - offsettable: fixed charges, minimum bill, taxes and surcharges."""
    credit_accrued: float
    credit_applied: float


class NbtPeriod(BaseModel):
    """One billing period settled under the NBT."""

    model_config = ConfigDict(frozen=True)

    period_start: date
    period_end: date
    days: int
    import_kwh: float
    export_kwh: float
    gross_retail: float
    """What the imports alone would cost — the bill with no solar credit at all."""
    layers: list[LayerSettlement]
    acc_plus_accrued: float
    acc_plus_applied: float
    amount_due: float
    nbc_floor: float
    """$ of non-bypassable charges on this period's gross imports. No amount of export
    can reduce this (only the ACC Plus credit can, per SC 2.c)."""
    balance_carried: dict[str, float]

    @property
    def credit_applied(self) -> float:
        return round(sum(ls.credit_applied for ls in self.layers) + self.acc_plus_applied, 2)


class NbtYear(BaseModel):
    """A full Relevant Period (annual true-up cycle) settled under the NBT."""

    model_config = ConfigDict(frozen=True)

    periods: list[NbtPeriod]
    vintage_application_year: int
    pto_date: date
    lock_in_through: date | None
    notes: list[str] = []

    @property
    def amount_due(self) -> float:
        return round(sum(p.amount_due for p in self.periods), 2)

    @property
    def gross_retail(self) -> float:
        return round(sum(p.gross_retail for p in self.periods), 2)

    @property
    def import_kwh(self) -> float:
        return round(sum(p.import_kwh for p in self.periods), 1)

    @property
    def export_kwh(self) -> float:
        return round(sum(p.export_kwh for p in self.periods), 1)

    @property
    def nbc_floor(self) -> float:
        return round(sum(p.nbc_floor for p in self.periods), 2)

    @property
    def stranded_credit(self) -> dict[str, float]:
        """Credit that accrued but had nothing left to offset at the end of the year.

        A large number here is the honest-broker signal that the array is oversized for
        this tariff: those dollars are real credit the customer earned and cannot spend.
        """
        return self.periods[-1].balance_carried if self.periods else {}

    @property
    def net_surplus_kwh(self) -> float:
        """Exports minus imports over the Relevant Period; >0 triggers NSC at true-up."""
        return round(self.export_kwh - self.import_kwh, 1)


# --- settlement ------------------------------------------------------------------------


def _sum_kwh(series: IntervalSeries, d0: date, d1_inclusive: date) -> float:
    idx = series.frame.index
    lo = pd.Timestamp(d0, tz=LOCAL_TZ)
    hi = pd.Timestamp(d1_inclusive + timedelta(days=1), tz=LOCAL_TZ)
    return float(series.frame.loc[(idx >= lo) & (idx < hi), COL_KWH].sum())


def export_credits(
    exports: IntervalSeries,
    schedule: ExportRateSchedule,
    d0: date,
    d1_inclusive: date,
) -> dict[str, float]:
    """$ of export compensation accrued in a period, per ACC component.

    Priced interval by interval against the 576-cell table — never against a monthly
    average — because the whole point of the ACC is that an exported kWh at 6 p.m. in
    September is worth an order of magnitude more than the same kWh at noon in April.
    """
    idx = exports.frame.index
    lo = pd.Timestamp(d0, tz=LOCAL_TZ)
    hi = pd.Timestamp(d1_inclusive + timedelta(days=1), tz=LOCAL_TZ)
    sub = exports.frame[(idx >= lo) & (idx < hi)]
    if sub.empty:
        return dict.fromkeys(COMPONENTS, 0.0)
    rates = schedule.rates(sub.index)
    kwh = sub[COL_KWH].to_numpy()
    return {c: float((kwh * rates[c].to_numpy()).sum()) for c in COMPONENTS}


def _settle_layer(
    bill: LayerBill,
    spec: TariffSpec,
    *,
    import_kwh: float,
    care: bool,
    accrued: float,
    balance: float,
) -> tuple[LayerSettlement, float]:
    """Split one layer into offsettable/protected and spend what credit it can absorb."""
    volumetric = round(sum(li.amount for li in bill.line_items if li.volumetric), 2)

    nbc = 0.0
    if spec.non_bypassable is not None:
        nbc = round(import_kwh * spec.non_bypassable.per_kwh(care=care), 2)
        if not spec.non_bypassable.included_in_energy_rate:
            # The NBCs are billed as their own lines rather than folded into the energy
            # rate, so they are not part of `volumetric` and nothing needs carving out.
            nbc = 0.0

    offsettable = max(0.0, volumetric - nbc)
    available = balance + accrued
    applied = min(available, offsettable)
    return (
        LayerSettlement(
            layer=bill.layer,
            total=bill.total,
            volumetric=volumetric,
            non_bypassable=nbc,
            offsettable=round(offsettable, 2),
            protected=round(bill.total - offsettable, 2),
            credit_accrued=round(accrued, 2),
            credit_applied=round(applied, 2),
        ),
        available - applied,
    )


def settle_period(
    imports: IntervalSeries,
    exports: IntervalSeries,
    delivery: TariffSpec | Sequence[TariffSpec],
    generation: TariffSpec | Sequence[TariffSpec],
    schedule: ExportRateSchedule,
    period_start: date,
    period_end: date,
    *,
    settings: NbtSettings,
    balance: CreditBalance,
    allow_before_effective: bool = False,
) -> NbtPeriod:
    """Settle one billing period. ``balance`` is mutated to carry credit forward."""
    if imports.direction is not Direction.IMPORT:
        raise ValueError("imports series must have direction=import")
    if exports.direction is not Direction.EXPORT:
        raise ValueError("exports series must have direction=export")

    kw = dict(
        care=settings.care,
        service=settings.service,
        territory=settings.territory,
        allow_before_effective=allow_before_effective,
    )
    d_bill = compute_layer(imports, delivery, period_start, period_end, **kw)
    g_bill = compute_layer(imports, generation, period_start, period_end, **kw)
    d_spec = (
        delivery
        if isinstance(delivery, TariffSpec)
        else max(delivery, key=lambda s: s.effective_date)
    )
    g_spec = (
        generation
        if isinstance(generation, TariffSpec)
        else max(generation, key=lambda s: s.effective_date)
    )

    import_kwh = _sum_kwh(imports, period_start, period_end)
    export_kwh = _sum_kwh(exports, period_start, period_end)
    accrued = export_credits(exports, schedule, period_start, period_end)

    # SC 2.a — a CCA customer's generation-component credit is not the utility's to pay.
    if settings.service is Service.CCA and settings.cca_export_terms is None:
        accrued["generation"] = 0.0

    d_set, balance.delivery = _settle_layer(
        d_bill,
        d_spec,
        import_kwh=import_kwh,
        care=settings.care,
        accrued=accrued["delivery"],
        balance=balance.delivery,
    )
    g_set, balance.generation = _settle_layer(
        g_bill,
        g_spec,
        import_kwh=import_kwh,
        care=settings.care,
        accrued=accrued["generation"],
        balance=balance.generation,
    )

    # ACC Plus: a flat $/kWh on exports that may offset ANY remaining charge (SC 2.c),
    # including the NBCs and the fixed charges the ACC credits cannot touch.
    plus_rate = 0.0
    if schedule.acc_plus_active(period_start):
        plus_rate = schedule.acc_plus_rate(
            low_income=settings.low_income, eligible=settings.acc_plus_eligible
        )
    plus_accrued = export_kwh * plus_rate
    gross = round(d_bill.total + g_bill.total, 2)
    after_credits = gross - d_set.credit_applied - g_set.credit_applied
    plus_available = balance.acc_plus + plus_accrued
    plus_applied = min(plus_available, max(0.0, after_credits))
    balance.acc_plus = plus_available - plus_applied

    nbc_floor = round(d_set.non_bypassable + g_set.non_bypassable, 2)
    return NbtPeriod(
        period_start=period_start,
        period_end=period_end,
        days=(period_end - period_start).days + 1,
        import_kwh=round(import_kwh, 1),
        export_kwh=round(export_kwh, 1),
        gross_retail=gross,
        layers=[d_set, g_set],
        acc_plus_accrued=round(plus_accrued, 2),
        acc_plus_applied=round(plus_applied, 2),
        amount_due=round(after_credits - plus_applied, 2),
        nbc_floor=nbc_floor,
        balance_carried=balance.as_dict(),
    )


def settle_year(
    imports: IntervalSeries,
    exports: IntervalSeries,
    delivery: TariffSpec | Sequence[TariffSpec],
    generation: TariffSpec | Sequence[TariffSpec],
    schedule: ExportRateSchedule,
    periods: Sequence[tuple[date, date]],
    *,
    settings: NbtSettings,
    allow_before_effective: bool = False,
) -> NbtYear:
    """Settle a Relevant Period (one true-up cycle) period by period, carrying credit."""
    balance = CreditBalance()
    out = [
        settle_period(
            imports,
            exports,
            delivery,
            generation,
            schedule,
            ps,
            pe,
            settings=settings,
            balance=balance,
            allow_before_effective=allow_before_effective,
        )
        for ps, pe in periods
    ]
    year = NbtYear(
        periods=out,
        vintage_application_year=schedule.vintage.application_year,
        pto_date=schedule.vintage.pto_date,
        lock_in_through=schedule.vintage.lock_in_through,
        notes=_notes(out, settings, schedule),
    )
    return year


def _notes(
    periods: list[NbtPeriod], settings: NbtSettings, schedule: ExportRateSchedule
) -> list[str]:
    """Caveats the report must carry — the failure conditions, not just the number."""
    notes: list[str] = []
    if settings.service is Service.CCA and settings.cca_export_terms is None:
        notes.append(
            "CCA customer: the generation component of the export credit is EXCLUDED "
            "(valued at $0). Schedule NBT SC 2.a says generation-component credits do not "
            "reduce charges owed to the utility, and the utility's posted generation "
            "export rates apply to non-CCA customers only. Supply the CCA's own export "
            "terms to value it — this result is a lower bound until you do."
        )
    if not settings.acc_plus_eligible:
        notes.append("ACC Plus adder excluded: customer is flagged ineligible (Sheet 57353-E).")
    stranded = periods[-1].balance_carried if periods else {}
    for bucket, amount in stranded.items():
        if amount >= 1.0:
            notes.append(
                f"${amount:.2f} of {bucket} export credit is stranded at the end of the "
                "Relevant Period — it accrued but there were no charges of that kind left "
                "to offset. It carries forward only while the customer stays on the NBT "
                "(SC 2.e) and is forfeited on the last true-up if they leave."
            )
    total_export = sum(p.export_kwh for p in periods)
    total_import = sum(p.import_kwh for p in periods)
    if total_export > total_import:
        notes.append(
            f"Net Surplus Electricity of {total_export - total_import:.0f} kWh over the "
            "Relevant Period. Net Surplus Compensation is paid at the DLAP-based NSC rate "
            "(Sheet 60441-E), which is not modeled here and is NOT available to CCA or "
            "Direct Access customers at all. Surplus beyond onsite load is worth far less "
            "than the export credit — treat this as a sign the array is oversized."
        )
    if schedule.vintage.lock_in_through is not None:
        notes.append(
            f"Export rates are locked to the {schedule.vintage.application_year} ACC "
            f"vintage through {schedule.vintage.lock_in_through} (nine years from PTO); "
            "after that they follow whatever ACC is current, which this model takes from "
            "the utility's published current-year table."
        )
    return notes
