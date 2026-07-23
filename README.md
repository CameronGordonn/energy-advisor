# Home Energy Advisor

Independent home-energy decision engine for California IOU customers. You bring your
own Green Button interval data; the engine answers, in numbers you can check against
your actual bills, which rate schedule is cheapest and whether solar/battery pays back
under NEM 3.0. See [CLAUDE.md](CLAUDE.md) for the design invariants and
[ROADMAP.md](ROADMAP.md) for milestones.

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

## Status

**M0 — PG&E bill reconciliation (in progress).** Green Button interval parser →
versioned tariff spec → itemized monthly bill, gated on reproducing the last 3 real
PG&E bills within ±$2 each.

## Development

```bash
conda env create -f environment.yml   # first time
conda activate energy-advisor
pytest                                 # run the suite
ruff check . && ruff format --check .  # lint / format
```

Package layout lives under `src/` (`greenbutton`, `tariffs`, `nem3`, `scenarios`,
`uncertainty`, `report`). Real Green Button exports and bills live in `data/` and
`tests/golden_bills/raw/`, both git-ignored — nothing personally identifiable is ever
committed.
