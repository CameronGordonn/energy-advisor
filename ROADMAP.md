# ROADMAP

Each milestone has a definition of done (DoD). A milestone is not complete until its DoD is demonstrated, not just implemented. Do not start milestone N+1 features while N is open.

## M0 — Bill reconciliation on PG&E (trust foundation)
Parse own Green Button CSV (PG&E, Santa Cruz account) into a canonical 15-min interval series. Implement the account's current rate schedule as a versioned tariff spec. Compute itemized monthly bills.
**DoD:** last 3 actual PG&E bills reproduced within ±$2 each, with a printed line-item comparison (energy charges by TOU period, fixed charges, taxes/surcharges bucketed). Golden-bill tests committed with anonymized fixtures.

## M1 — SDG&E engine + CCA overlay
Add SDG&E Green Button parser quirks. Implement the relevant SDG&E residential schedules (standard TOU + EV schedules) and the San Diego Community Power generation overlay as separable spec layers (delivery vs generation).
**DoD:** dad's last 3 SDG&E bills reconciled within ±$2, including correct CCA generation line items. Reconciliation table published in repo README (anonymized).

## M2 — Rate optimizer
Re-simulate a household's full year of intervals under every eligible schedule (both IOUs; CCA on/off where applicable). Rank by annual cost; report savings vs current plan and the usage-pattern conditions under which the ranking flips.
**DoD:** for both real households, a one-command report: best plan, annual delta in dollars, and a sensitivity note (e.g., "ranking flips if evening usage grows >X%"). Cross-checked against the utility's own free rate-comparison output; any disagreement explained.

## M3 — NEM 3.0 solar + battery module
PVWatts hourly production by location/system spec. ACC export tables by vintage year with 9-year lock-in logic. Netting rules and non-bypassable-charge bill floor. Battery dispatch: greedy TOU heuristic and cvxpy LP optimum. Payback for solar-only, solar+battery, battery-only.
**DoD:** for one real household, payback distributions (Monte Carlo over rate escalation, degradation, load drift) reported as ranges, plus the vintage-timing comparison (install this year vs next). Must be able to produce a defensible "don't buy" answer on at least one configuration and say why.

## M4 — Public methodology + case study (portfolio checkpoint)
Write up the methodology: reconciliation accuracy, engine design, one honest anonymized case study end to end. Publish repo (minus data), writeup, and a small static demo of outputs.
**DoD:** writeup live; repo README leads with the reconciliation accuracy table. This milestone alone justifies the project for the job search regardless of revenue.

## M5 — First external users (sales checkpoint)
Manual pipeline: 5 strangers (San Diego subreddit / Nextdoor) send Green Button CSVs, receive a report. Zero automation beyond what exists; the goal is learning what people ask, what confuses them, and whether anyone would pay.
**DoD:** 5 delivered reports, notes on each conversation, and a written go/no-go on charging (price point, objections, repeat-question patterns).

## Later (explicitly out of scope until M5 verdict)
Bayou Energy auto-connect (~$2/meter), web UI, payments, subscription re-analysis ("your optimal plan changed"), B2B white-label for brokers/realtors/independent installers.
