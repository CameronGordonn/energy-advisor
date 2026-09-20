"""Billing from the per-TOU-period kWh a statement prints, with no interval data.

M1a's definition of done is a bill reconciled **from the statement's own bucketed kWh**,
because the ask that closes it is "one redacted SDG&E bill" rather than "a year of
15-minute data plus a bill from the same household" (see
``notes/m1_without_dad_2026-09.md``). ``tariffs.bill.compute_bill`` cannot serve that: it
takes an :class:`~greenbutton.models.IntervalSeries` and buckets it itself.

**This module supplies the missing input, not a second engine.** Every dollar it produces
comes out of :func:`tariffs.bill.charge_lines` and :func:`tariffs.bill.minimum_bill_line`
— the same functions :func:`tariffs.bill.compute_layer` calls — so the two paths cannot
disagree about a rate, a rounding rule or a line name. What lives here is only the part
that genuinely differs: turning printed segments into the ``(spec version, season, days,
usage)`` runs the charge layer bills, and **refusing, by name, every case where printed
buckets are not enough to do that**.

Three things printed buckets cannot do, each a refusal rather than a guess:

1. **Allocate kWh across a rate change or a season boundary.** SDG&E filed five 2026
   TOU-DR1 vintages (1/1, 4/1, 5/1, 6/1, 8/1) and its summer starts 6/1, so a routine
   30-day statement straddles a boundary more often than not, and the two layers change
   on different dates. The statement itself prints a separate block per change; the
   fixture therefore carries a *list* of segments and a segment that spans a boundary
   raises :class:`SegmentStraddlesRateChangeError` instead of being split pro rata.
2. **Recover within-period timing.** The event adder (SDG&E TOU-DR-P's RYU adder) is
   billed on kWh inside named hours on named days, which is strictly finer than any
   bucket a statement prints. ``charge_lines`` raises
   :class:`~tariffs.bill.TimingDependentChargeError` rather than reading the absent
   number as zero.
3. **Check the utility's own bucketing.** The printed split is SDG&E's classification of
   the customer's intervals, so pricing it tests this repo's *rates* and *charge
   structure* and cannot test ``tou.rules`` — the year-round super-off-peak window, the
   weekend table, the holiday calendar. That is not a defect in this module; it is the
   line between M1a and M1b, and it is written down in ``notes/m1a_harness_2026-09.md``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from itertools import pairwise

from pydantic import BaseModel, ConfigDict, Field

from greenbutton.models import IntervalSeries

from .bill import (
    Bill,
    LayerBill,
    LineItem,
    _r,
    _rate_subperiods,
    _usage,
    charge_lines,
    minimum_bill_line,
)
from .schema import Service, TariffSpec


class BucketedUsageError(ValueError):
    """Printed per-TOU-period kWh cannot be priced as given."""


class SegmentCoverageError(BucketedUsageError):
    """The printed segments do not tile the billing period exactly."""


class SegmentStraddlesRateChangeError(BucketedUsageError):
    """One printed segment spans a rate change or a season boundary."""


class UnbucketedPeriodError(BucketedUsageError):
    """A segment's kWh keys are not exactly the TOU periods the schedule defines."""


class UsageSegment(BaseModel):
    """kWh per TOU period over one printed block of a statement, inclusive of both dates.

    One segment per block the statement itself prints. A statement that spans no rate
    change prints one block and needs one segment; SDG&E prints a second block when rates
    change mid-cycle, and the second segment is that block.

    Keys of ``kwh`` are the schedule's own period names (``on_peak`` / ``off_peak`` /
    ``super_off_peak`` on SDG&E residential; ``peak`` / ``offpeak`` on two-period PG&E
    schedules), not the printed labels. A period the statement omits because it saw no
    usage must still be written as ``0`` — see :func:`_run_usage`.
    """

    model_config = ConfigDict(frozen=True)

    start: date
    end: date = Field(description="last day of the block, INCLUSIVE, as the statement prints it")
    kwh: dict[str, float]

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def total_kwh(self) -> float:
        return sum(self.kwh.values())


# --- segments -> the runs the charge layer bills ----------------------------


def _ordered(segments: Sequence[UsageSegment], period_start: date, period_end: date, *, what: str):
    """``segments`` sorted, having checked they tile [period_start, period_end] exactly.

    A gap would silently drop a day's usage and a day of the fixed charge; an overlap
    would bill it twice. Neither is a tie to break — both mean the transcription does not
    match the statement, which is the only thing a bill-only reconciliation has.
    """
    if not segments:
        raise SegmentCoverageError(
            f"{what}: no printed usage segments; the bill-only path has nothing to price"
        )
    ordered = sorted(segments, key=lambda s: s.start)
    for s in ordered:
        if s.end < s.start:
            raise SegmentCoverageError(f"{what}: segment {s.start}..{s.end} ends before it starts")
    if ordered[0].start != period_start or ordered[-1].end != period_end:
        raise SegmentCoverageError(
            f"{what}: printed segments cover {ordered[0].start}..{ordered[-1].end} but the "
            f"billing period is {period_start}..{period_end}. The fixed charge and the "
            "baseline allowance are both per day, so a period the segments do not cover is "
            "a wrong bill, not a partial one."
        )
    for a, b in pairwise(ordered):
        if b.start != a.end + timedelta(days=1):
            gap = "overlap" if b.start <= a.end else "gap"
            raise SegmentCoverageError(
                f"{what}: {gap} between printed segments {a.start}..{a.end} and "
                f"{b.start}..{b.end}; segments must be contiguous and disjoint"
            )
    return ordered


def _run_usage(
    spec: TariffSpec, segments: Sequence[UsageSegment], *, what: str
) -> dict[str, float]:
    """Sum ``segments`` into one ``{period: kWh}`` in the schedule's own period order.

    Refuses a key the schedule does not define and a period the segment leaves out. The
    second half matters more than it looks: a statement prints no line for a period that
    saw no usage, and silently reading that as zero is indistinguishable from silently
    reading a *mis-transcribed* period as zero. Writing ``super_off_peak: 0`` is a
    transcription on the record.
    """
    periods = spec.tou.periods
    out = {p: 0.0 for p in periods}
    for seg in segments:
        if set(seg.kwh) != set(periods):
            missing = sorted(set(periods) - set(seg.kwh))
            unknown = sorted(set(seg.kwh) - set(periods))
            raise UnbucketedPeriodError(
                f"{what}: segment {seg.start}..{seg.end} gives kWh for {sorted(seg.kwh)}, but "
                f"{spec.provider} {spec.schedule_id} {spec.layer.value} bills {periods}"
                + (
                    f"; missing {missing} (write 0 explicitly if the statement printed none)"
                    if missing
                    else ""
                )
                + (f"; unknown {unknown}" if unknown else "")
            )
        for p in periods:
            out[p] += float(seg.kwh[p])
    return out


def _runs_with_segments(
    segments: Sequence[UsageSegment],
    versions: Sequence[TariffSpec],
    period_start: date,
    period_end: date,
    *,
    allow_before_effective: bool = False,
    what: str,
) -> list[tuple[TariffSpec, object, int, dict[str, float]]]:
    """Group printed segments under the (spec version, season) runs that price them.

    Several segments may share a run — the statement may print a block boundary the
    tariff does not have — and they are summed, exactly as the interval path sums whole
    days. A segment that *spans* a run boundary is refused: the tariff prices its two
    halves differently and nothing in a printed bucket says how the kWh divided.
    """
    ordered = _ordered(segments, period_start, period_end, what=what)
    runs = _rate_subperiods(
        period_start, period_end, versions, allow_before_effective=allow_before_effective
    )
    out = []
    for spec, season, d0, d1 in runs:
        mine = [s for s in ordered if s.start >= d0 and s.end <= d1]
        for s in ordered:
            straddles = s.start <= d1 and s.end >= d0 and not (s.start >= d0 and s.end <= d1)
            if straddles:
                cut = d0 if s.start < d0 else d1 + timedelta(days=1)
                raise SegmentStraddlesRateChangeError(
                    f"{what}: printed segment {s.start}..{s.end} spans the boundary at "
                    f"{cut}, where this schedule changes to the {spec.effective_date} "
                    f"rates / the {season.value} season (run {d0}..{d1}). Printed "
                    "per-period kWh says how much energy fell in each TOU bucket, never on "
                    "which side of the boundary it fell, and the two sides are priced "
                    f"differently. Split the segment at {cut} using the statement's own "
                    "sub-period blocks; if the statement does not print them, this bill "
                    "cannot be reconciled without interval data."
                )
        days = sum(s.days for s in mine)
        expect = (d1 - d0).days + 1
        if days != expect:  # unreachable given _ordered + the straddle check; asserted anyway
            raise SegmentCoverageError(
                f"{what}: run {d0}..{d1} is {expect} days but its segments cover {days}"
            )
        out.append((spec, season, days, _run_usage(spec, mine, what=what)))
    return out


# --- the billing functions --------------------------------------------------


def compute_layer_from_usage(
    segments: Sequence[UsageSegment],
    spec: TariffSpec | Sequence[TariffSpec],
    period_start: date,
    period_end: date,
    *,
    care: bool = False,
    service: Service = Service.CCA,
    territory: str | None = None,
    vintage: str | None = None,
    allow_before_effective: bool = False,
) -> LayerBill:
    """:func:`tariffs.bill.compute_layer`, taking printed buckets instead of a series.

    Same arguments, same line items, same rounding — the only difference is where the
    per-TOU-period kWh comes from. There is no ``event_days`` parameter: a schedule
    carrying an event adder raises
    :class:`~tariffs.bill.TimingDependentChargeError` from ``charge_lines``, because the
    day list alone would not help (the adder is billed on kWh inside named *hours*).
    """
    versions = (
        [spec] if isinstance(spec, TariffSpec) else sorted(spec, key=lambda s: s.effective_date)
    )
    if not versions:
        raise ValueError("compute_layer_from_usage: no spec version supplied")
    meta = versions[-1]
    what = f"{meta.provider} {meta.schedule_id} {meta.layer.value}"

    items: list[LineItem] = []
    for run_spec, season, days, usage in _runs_with_segments(
        segments,
        versions,
        period_start,
        period_end,
        allow_before_effective=allow_before_effective,
        what=what,
    ):
        items.extend(
            charge_lines(
                run_spec,
                season,
                days=days,
                usage=usage,
                event_kwh=None,  # raises rather than reading the absent number as zero
                care=care,
                service=service,
                territory=territory,
                vintage=vintage,
            )
        )

    minimum_bill_line(items, meta, (period_end - period_start).days + 1, care=care)
    return LayerBill(
        layer=meta.layer,
        provider=meta.provider,
        schedule_id=meta.schedule_id,
        line_items=items,
        total=_r(sum(li.amount for li in items)),
    )


def compute_bill_from_usage(
    segments: Sequence[UsageSegment],
    specs: Sequence[TariffSpec | Sequence[TariffSpec]],
    period_start: date,
    period_end: date,
    *,
    care: bool = False,
    service: Service = Service.CCA,
    territory: str | None = None,
    vintage: str | None = None,
    observed_adjustments: list[LineItem] | None = None,
    climate_credit: float | None = None,
    allow_before_effective: bool = False,
) -> Bill:
    """:func:`tariffs.bill.compute_bill`, taking printed buckets instead of a series.

    Each layer validates the segments against **its own** version list, because delivery
    and generation change on different dates (PG&E's 2026-03-01 against 3CE's
    2026-02-15). A transcription that is fine for one layer and straddles a change in the
    other is refused by the layer it breaks, named.
    """
    layers = [
        compute_layer_from_usage(
            segments,
            s,
            period_start,
            period_end,
            care=care,
            service=service,
            territory=territory,
            vintage=vintage,
            allow_before_effective=allow_before_effective,
        )
        for s in specs
    ]
    modeled = (
        [LineItem(name="California Climate Credit", amount=_r(climate_credit))]
        if climate_credit
        else []
    )
    return Bill(
        period_start=period_start,
        period_end=period_end,
        total_kwh=_r(sum(s.total_kwh for s in segments)),
        layers=layers,
        observed_adjustments=observed_adjustments or [],
        modeled_adjustments=modeled,
    )


# --- the bridge: real intervals -> the buckets a statement would print -------


def segments_from_series(
    series: IntervalSeries,
    specs: Sequence[TariffSpec | Sequence[TariffSpec]],
    period_start: date,
    period_end: date,
    *,
    allow_before_effective: bool = False,
) -> list[UsageSegment]:
    """Bucket a real interval series into the segments a statement would have printed.

    This is what makes the bill-only path testable before any bill-only fixture exists:
    the eleven PG&E golden bills have real intervals *and* real printed dollars, so
    bucketing them here and pricing the result through :func:`compute_bill_from_usage`
    must reproduce :func:`tariffs.bill.compute_bill` to the cent. It is a *test*
    instrument, not a reconciliation input — a fixture that has intervals should be
    reconciled from them.

    Segments are split at the union of every layer's run boundaries, so the result is
    priceable by all of them. Where layers disagree about which TOU period a timestamp
    belongs to the result would be ambiguous, so that is checked rather than assumed —
    the same invariant :func:`tariffs.bill.marginal_energy_price` enforces.
    """
    version_lists = [
        [s] if isinstance(s, TariffSpec) else sorted(s, key=lambda v: v.effective_date)
        for s in specs
    ]
    cuts = {period_start, period_end + timedelta(days=1)}
    for versions in version_lists:
        for _spec, _season, d0, _d1 in _rate_subperiods(
            period_start, period_end, versions, allow_before_effective=allow_before_effective
        ):
            cuts.add(d0)
    bounds = sorted(cuts)

    out: list[UsageSegment] = []
    for lo, nxt in pairwise(bounds):
        hi = nxt - timedelta(days=1)
        buckets = None
        for versions in version_lists:
            spec = _rate_subperiods(
                lo, hi, versions, allow_before_effective=allow_before_effective
            )[0][0]
            u = _usage(series, spec, lo, hi)
            if buckets is None:
                buckets = u
            elif sorted(buckets) != sorted(u) or any(
                abs(buckets[k] - u[k]) > 1e-9 for k in buckets
            ):
                raise UnbucketedPeriodError(
                    f"layers disagree about the TOU bucketing of {lo}..{hi}: "
                    f"{spec.provider} {spec.schedule_id} {spec.layer.value} gives "
                    f"{ {k: round(v, 3) for k, v in u.items()} } where an earlier layer "
                    f"gives { {k: round(v, 3) for k, v in buckets.items()} }"
                )
        out.append(UsageSegment(start=lo, end=hi, kwh=buckets or {}))
    return out


__all__ = [
    "BucketedUsageError",
    "SegmentCoverageError",
    "SegmentStraddlesRateChangeError",
    "UnbucketedPeriodError",
    "UsageSegment",
    "compute_bill_from_usage",
    "compute_layer_from_usage",
    "segments_from_series",
]
