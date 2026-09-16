# Closing M1 without dad's data — the routes, one of them measured shut (2026-09-16, session 28)

Written for: Cameron, and the next session that is tempted to re-open the public-bill route.
Question asked: **how does M1's DoD get met without dad's SDG&E bills?**

## The finding: the one public SDG&E bill corpus cannot reconcile, and now we know why

`ookla-ariel-ride/SDGE-Analysis` (MIT) publishes 26 de-identified itemised SDG&E statements —
`bill_periods_electric.csv` (totals, delivery $, CCA generation $, fixed charge, net and gross
kWh) and `bill_tou_detail.csv` (216 rows of per-statement, per-season, per-segment,
per-TOU-period kWh **and printed $/kWh**). Session 23 used it to corroborate our EV-TOU-5
rates. It looked like the cheapest possible M1 route: bucketed kWh plus printed dollars is
exactly what `RECRUITING.md`'s "Ask 1" says is enough to test the charge layer without any
interval data.

**It is not enough, and the reason is structural rather than fixable.** Priced four ways over
the seven 2026 statements — energy at the printed rates, plus the fixed charge, plus the
0.02099/kWh non-bypassable bundle on net kWh, on gross kWh, and on the difference — nothing
lands near the printed delivery total:

| decomposition | mean residual | worst |
|---|---|---|
| energy + fixed | −$26.47 | $66.94 |
| + NBC on gross kWh | +$11.51 | $100.79 |
| + NBC on net kWh | −$6.28 | $87.61 |
| + NBC on exported kWh | −$8.68 | $76.61 |

The residuals swing **both ways** (−$67 to +$63), which rules out a missing line item. The
generation side behaves the same: our energy total agrees with the printed CCA generation
charge to **$0.32** on one statement and is **$59.27** out on another.

**The corpus's own author reports the identical gap and names its cause.** Their
`rate_rebilling_residuals.csv` carries a `cca_generation_gap_usd` column running $0.32 → $59.27
(up to 104%), and their `bill_decomposition.json` quotes the statements directly:

> "*Payment not required for NEM charges. Your account will true up on Dec 26, 2024"
> — Net Metering Account Summary: **"Payment Required This Month: No"**

**This household is NEM-2 with solar, so its monthly statements are true-up accruals, not
payable bills.** The printed "current charges" are not the period's charges: credits carry
forward and settle annually. Reproducing them within ±$2 would mean modelling NEM-2 credit
carryforward — which this engine does not do (it models NBT/NEM-3), and which M1's DoD is not
about.

Worth recording as a cross-check that the arithmetic is understood rather than merely failing:
our per-period energy dollars reproduce their `printed_tou_energy_usd` **exactly** on every
2026 statement (e.g. $319.45 on 2026-07-02). The rates and the bucketing are right. The
statement total is a different quantity.

**So the route is closed, with a measurement rather than an opinion.** Do not re-open it. The
corpus keeps the job it already has: corroborating EV-TOU-5's rates and the NBC decomposition
(`test_our_delivery_rate_less_the_import_floor_is_what_sdge_printed`), which it does well.

## What M1 actually needs, restated precisely

Not "dad". **One ordinary — i.e. non-solar, non-NEM — SDG&E residential statement**, whose
total is a payable amount that a tariff can reproduce. Everything else about M1 is built:

- The specs are tariff-exact across all five 2026 vintages, both layers, three schedules.
- The harness is utility-general since session 24; it dispatches on the fixture's `utility:`,
  gates on the customer facts the specs demand, and needs **nothing but transcription**.
- Both San Diego CCAs are authored.

The ask that closes the charge half is therefore much smaller than M5's recruiting drive:
**one redacted bill image or PDF from one person in San Diego, no interval export, no
conversation about a year of 15-minute data.** A friend, a colleague, one post. The interval
half — the parser and the interval→TOU-bucket step — still needs an export from that same
household, and that is the only part that genuinely needs a willing participant.

## The DoD question this raises

M1's DoD names dad specifically ("dad's last 3 SDG&E bills"). With that source gone, the
milestone as written is unreachable by anyone, and a milestone that cannot be reached records
no progress. Three honest options, for Cameron:

**A. Keep the DoD, change the source.** "Three real SDG&E bills from any household." One
person, one ask, no other change. M1 closes when three statements reconcile.

**B. Split it in two, because the two halves fail independently.**
- *M1a — charge layer:* three real SDG&E statements' printed dollars reproduced within ±$2
  **from the statements' own bucketed kWh**, no interval data. Needs bills only.
- *M1b — interval layer:* one household's export priced end to end against one of its own
  bills. Needs export + bill from the same household.

B is the honest shape of the evidence and it makes the bill-only harness worth building, since
that harness is also what consumes the first real bill when it arrives. It records the progress
that A hides.

**C. Retire M1's DoD as unreachable**, mark SDG&E "engine complete, never validated", and keep
invariant 1 in force (no SDG&E dollar figure shown to anyone, ever). Costs nothing today and
is the honest answer if no bill is ever going to arrive.

**DECIDED 2026-09-16 — Cameron chose B.** ROADMAP, README and HANDOFF are amended; M1a and
M1b are the milestone now. The consequence is that the **bill-only harness is the next build**,
and it can be validated before any real bill arrives: bucket the 11 PG&E golden bills' real
intervals, run them through the bill-only path, and measure what bucketing loses against the
full-interval reconciliation those same fixtures already pass.

**Recommended was: B, then the one-bill ask.** Under any of the three, invariant 1 is unchanged:
until a real SDG&E statement reconciles, the tool shows San Diego users no dollar figure.
