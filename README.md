# Home Energy Advisor

Independent home-energy decision engine for California IOU customers. You bring your
own Green Button interval data; the engine answers, in numbers you can check against
your actual bills, which rate schedule is cheapest and whether solar/battery pays back
under NEM 3.0. See [CLAUDE.md](CLAUDE.md) for the design invariants and
[ROADMAP.md](ROADMAP.md) for milestones.

<!-- Replace OWNER/REPO once the GitHub repo exists (see HANDOFF.md "publishing"). -->
[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](environment.yml)

**[Read the writeup →](https://OWNER.github.io/REPO/)** — methodology, the household worked
end to end, and everything still assumed.

## Bill-reconciliation accuracy

The product's trust artifact: every dollar figure downstream is only as good as the
bill engine's ability to reproduce **real** utility bills from **real** interval data.
Target: **±$2/month** vs. the actual bill. This table is the first thing a reader sees
and is regenerated from the golden-bill regression suite.

<!-- RECONCILIATION-TABLE:START -->
| Utility | Schedule | Bill period | Actual $ | Modeled $ | Δ $ | Within ±$2 |
|---------|----------|-------------|---------:|----------:|----:|:----------:|
| PG&E | E-TOU-C + 3CE (CARE) | 2025-08-02 → 2025-08-25 | 70.57 | 70.73 | +0.16 | ✅ |
| PG&E | E-TOU-C + 3CE (CARE) | 2025-08-26 → 2025-09-24 | 107.52 | 107.74 | +0.22 | ✅ |
| PG&E | E-TOU-C + 3CE (CARE) | 2025-09-25 → 2025-10-26 | 49.11 | 49.32 | +0.21 | ✅ |
| PG&E | E-TOU-C + 3CE (CARE) | 2025-10-27 → 2025-11-24 | 82.08 | 82.10 | +0.02 | ✅ |
| PG&E | E-TOU-C + 3CE (CARE) | 2025-11-25 → 2025-12-26 | 73.77 | 73.87 | +0.10 | ✅ |
| PG&E | E-TOU-C + 3CE (CARE) | 2025-12-27 → 2026-01-27 | 156.88 | 157.09 | +0.21 | ✅ |
| PG&E | E-TOU-C + 3CE (CARE) | 2026-01-28 → 2026-02-26 | 168.75 | 168.93 | +0.18 | ✅ |
| PG&E | E-TOU-C + 3CE (CARE) | 2026-02-27 → 2026-03-29 | 93.86 | 93.97 | +0.11 | ✅ |
| PG&E | E-TOU-C + 3CE (CARE) | 2026-03-30 → 2026-04-27 | 90.05 | 90.12 | +0.07 | ✅ |
| PG&E | E-TOU-C + 3CE (CARE) | 2026-04-28 → 2026-05-27 | 112.20 | 112.32 | +0.12 | ✅ |
| PG&E | E-TOU-C + 3CE (CARE) | 2026-05-28 → 2026-06-25 | 79.47 | 79.62 | +0.15 | ✅ |
<!-- RECONCILIATION-TABLE:END -->

> No feature that produces a dollar figure ships until the row(s) above are green.

**[Read the methodology and case study →](docs/METHODOLOGY.md)** — how the engine computes a
bill, what the residual above is made of, one household worked end to end, and a full list of
what is still assumed or unverified. The same writeup as a standalone static page, with the
residual chart, is [docs/index.html](docs/index.html) (open it locally, or serve `docs/` as the
published site).

## Status

Milestones are defined in [ROADMAP.md](ROADMAP.md); a milestone counts as done only when
its definition of done is *demonstrated*, not merely implemented.

| Milestone | State |
|---|---|
| **M0** — PG&E bill reconciliation | **Done.** All 11 real statements reproduced within ±$2 (worst +$0.22), from the household's own hourly interval data. The table above is the artifact. |
| **M1** — SDG&E engine + CCA overlay | **Engine built, DoD blocked on data.** SDG&E TOU-DR1 / TOU-DR2 / EV-TOU-5 delivery specs, the TOU-DR1 bundled generation (EECC) layer, climate-zone baseline allowances and the non-bypassable-charge set all ship and are tariff-exact — the delivery and generation layers re-sum to SDG&E's own published Total Electric Rate and Total Adjusted CARE Rate on every cell. The DoD needs three real SDG&E bills, which no household can currently supply. The CCA generation overlay is deliberately un-authored until which CCA applies is known. |
| **M2** — Rate optimizer | **Done on the PG&E household.** One command ranks every eligible schedule with CCA on/off, and reports the annual delta, a component-level explanation, a sensitivity note and an assumption audit. The utility's own free comparison tool was unavailable for cross-check, which is stated in the output. |
| **M3** — NEM 3.0 solar + battery | **Engine complete, DoD blocked on data.** Real per-vintage ACC export tables with nine-year PTO lock-in, Net Billing Tariff settlement, the non-bypassable import floor, PVWatts production, greedy *and* LP battery dispatch, payback, and Monte Carlo ranges. The DoD needs one real household with solar/export interval data; none is available, and a synthetic load is not a substitute. |
| **M4** — Public methodology + case study | **Done.** [docs/METHODOLOGY.md](docs/METHODOLOGY.md) covers reconciliation accuracy, engine design, the PG&E household end to end (including the finding that its cheapest move is leaving the CCA, not changing schedule), five findings generic calculators miss, and every open assumption; [docs/index.html](docs/index.html) is the same material as a static page with the residual chart. The table above leads this README, per the definition of done. The case study is self-attributed by decision, not anonymized — see the note in [ROADMAP.md](ROADMAP.md). |
| **M5** — First external users | Not started. |

Two findings the engine produced that generic calculators miss: on SDG&E the published
2025, 2026 and current export-rate tables are byte-identical, so the nine-year vintage
lock-in confers no dollar advantage there — the opposite of the pitch installers cite; and
on Schedule EV-TOU-5 roughly 45% of the super-off-peak delivery charge is non-bypassable
(against ~6.5% in other windows), because the schedule discounts distribution but not the
non-bypassable charges.

## Development

```bash
conda env create -f environment.yml   # first time
conda activate energy-advisor
pytest                                 # run the suite (331 tests)
ruff check . && ruff format --check .  # lint / format
```

Reports (each needs `PYTHONPATH=src`, since only pytest picks up `src/` automatically):

```bash
PYTHONPATH=src python scripts/reconcile_report.py   # the trust artifact: line-item bill comparison
PYTHONPATH=src python scripts/rate_optimizer.py     # M2: rate ranking, sensitivity, assumption audit
PYTHONPATH=src python scripts/nem3_report.py        # M3: solar + battery under the Net Billing Tariff
```

Package layout lives under `src/` (`greenbutton`, `tariffs`, `nem3`, `scenarios`,
`uncertainty`, `report`). Real Green Button exports and bills live in `data/` and
`tests/golden_bills/raw/`, both git-ignored — nothing personally identifiable is ever
committed. Golden-bill tests skip cleanly when `data/` is absent, so the suite is green on
a fresh clone.

## License

Copyright © 2026 Cameron Gordon. Licensed under the
**[GNU Affero General Public License v3.0](LICENSE)**.

AGPL rather than MIT deliberately: the tariff engine is the substance of this project, and
the AGPL's network clause means anyone who runs a modified version as a hosted service has
to publish their source. Reading, learning from, running and contributing to it are all
unrestricted.

Tariff rates, Avoided Cost Calculator tables and utility tariff sheets referenced here are
public regulatory filings and are not covered by this license. Each is cited in the spec
file that uses it. **Nothing here is financial advice**; it is analysis of published tariffs
against a household's own metered data.
