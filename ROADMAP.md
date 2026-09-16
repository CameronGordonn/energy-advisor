# ROADMAP

Each milestone has a definition of done (DoD). A milestone is not complete until its DoD is demonstrated, not just implemented. Do not start milestone N+1 features while N is open.

## M0 — Bill reconciliation on PG&E (trust foundation)
Parse own Green Button CSV (PG&E, Santa Cruz account) into a canonical 15-min interval series. Implement the account's current rate schedule as a versioned tariff spec. Compute itemized monthly bills.
**DoD:** last 3 actual PG&E bills reproduced within ±$2 each, with a printed line-item comparison (energy charges by TOU period, fixed charges, taxes/surcharges bucketed). Golden-bill tests committed with anonymized fixtures.

## M1 — SDG&E engine + CCA overlay
Add SDG&E Green Button parser quirks. Implement the relevant SDG&E residential schedules (standard TOU + EV schedules) and the San Diego Community Power generation overlay as separable spec layers (delivery vs generation).

**DoD — split into two halves, amended 2026-09-16 (session 28).** The original read "dad's last 3 SDG&E bills reconciled within ±$2". Dad is no longer a source, and a DoD naming one person is unreachable by anyone else; more importantly the two halves of it **fail independently** and were being hidden behind one checkbox. Split, so partial progress is recordable:

- **M1a — charge layer.** Three real SDG&E statements' printed dollars reproduced within ±$2 **from the statements' own per-TOU-period kWh**, no interval data required, including correct CCA generation line items. Needs bills only — one ordinary (non-solar, non-NEM) household's statements. Reconciliation table published in the README.
- **M1b — interval layer.** One household's Green Button export priced end to end against one of its own bills, within ±$2. This is the half that tests `src/greenbutton/sdge.py` and the interval→TOU-bucket step, and it needs an export and a bill from the *same* household.

_Why the split is not a lowering of the bar: M1a cannot be met by the public 26-bill corpus, whose statements are NEM-2 true-up accruals rather than payable bills — measured, not assumed, in `notes/m1_without_dad_2026-09.md`. Invariant 1 is unchanged under both halves: until a real SDG&E statement reconciles, no San Diego user is shown a dollar figure._

## M2 — Rate optimizer
Re-simulate a household's full year of intervals under every eligible schedule (both IOUs; CCA on/off where applicable). Rank by annual cost; report savings vs current plan and the usage-pattern conditions under which the ranking flips.
**DoD:** for both real households, a one-command report: best plan, annual delta in dollars, and a sensitivity note (e.g., "ranking flips if evening usage grows >X%"). Cross-checked against the utility's own free rate-comparison output; any disagreement explained.

## M3 — NEM 3.0 solar + battery module
PVWatts hourly production by location/system spec. ACC export tables by vintage year with 9-year lock-in logic. Netting rules and non-bypassable-charge bill floor. Battery dispatch: greedy TOU heuristic and cvxpy LP optimum. Payback for solar-only, solar+battery, battery-only.
**DoD:** for one real household, payback distributions (Monte Carlo over rate escalation, degradation, load drift) reported as ranges, plus the vintage-timing comparison (install this year vs next). Must be able to produce a defensible "don't buy" answer on at least one configuration and say why.

## M4 — Public methodology + case study (portfolio checkpoint)
Write up the methodology: reconciliation accuracy, engine design, one honest case study end to end. Publish repo (minus data), writeup, and a small static demo of outputs.
**DoD:** writeup live; repo README leads with the reconciliation accuracy table. This milestone alone justifies the project for the job search regardless of revenue.

_Amended 2026-09-07 (session 7): "anonymized" was changed to "honest". The case study's subject is the repo's author, so anonymization is theatre — the repo carries his name — and blurring the dates or amounts would destroy the property that makes the reconciliation checkable by a third party against the tariff sheets. Decision recorded in SESSION_NOTES: self-attributed, CARE status disclosed, exact dates and amounts kept; unit number, CARE renewal date and tenancy dates scrubbed from all committed docs._

## M5 — First external users (sales checkpoint)
Manual pipeline: 5 strangers (San Diego subreddit / Nextdoor) send Green Button CSVs, receive a report. Zero automation beyond what exists; the goal is learning what people ask, what confuses them, and whether anyone would pay.
**DoD:** 5 delivered reports, notes on each conversation, and a written go/no-go on charging (price point, objections, repeat-question patterns).

## ⚠ Amended 2026-09-16 (session 28) — the web tool now prices, at Cameron's direction

"Web UI" sat under *Later* below, and the public tool deliberately produced no dollar
figure. Cameron asked why the site gives no recommendation even in its own example, and the
answer that came back was **not** the one the code claimed. `docs/index.html` and
`scripts/build_web_engine.py` both said the tool shows no dollars because of invariant 1 —
but invariant 1 is met for PG&E, 11/11 within ±$2. The real limitation was never on the
page: **the PG&E specs describe one household** (baseline territory T, all-electric, 3CE,
PCIA 2018, a Santa Cruz UUT adjustment fitted to his bills).

So the tool now ranks plans for households the specs can be shown to describe, and refuses
by name for everyone else — `src/report/recommend.py`, gated and tested. This is building
ahead of the M5 verdict, deliberately and on the owner's instruction. Invariant 1 is
unchanged and is now enforced in code rather than by omission: SDG&E visitors get the
analysis and no price.

## Later (explicitly out of scope until M5 verdict)
Bayou Energy auto-connect (~$2/meter), web UI, payments, subscription re-analysis ("your optimal plan changed"), B2B white-label for brokers/realtors/independent installers.
