# The public SDG&E corpus — what exists, 2026-09-09 (session 23)

A ranked survey of publicly available SDG&E Green Button interval exports, run because
M1's DoD is blocked on real SDG&E data and dad is a single point of failure. Supersedes
session 13's finding that the corpus was one file.

**Headline: the corpus is not one file, it is at least six across two repos — but no single
household publishes an export AND its bills.** The two finds are complements, not a pair:
one has a year of intervals with no bills, the other has 26 itemised bills with no intervals.

## 1. steevschmidt/NEC-220.87-Methods — four real exports, Apache-2.0  ⭐ THE FIND

`test_data/SDGE data & instructions/` in https://github.com/steevschmidt/NEC-220.87-Methods
(Apache-2.0, so the bytes MAY be vendored with attribution — unlike corruptbear's).
Published by Home Energy Analytics as test data for NEC 220.87 panel-sizing methods.

| File | Shape | Range | Export register |
|---|---|---|---|
| `PV_Electric_15_Minute_3-1-2024_2-28-2025_20250311.csv` | **15-min**, 35,040 rows | **full year** | **2,944.9 kWh** |
| `Electric_60_Minute_3-1-2024_2-28-2025_20250311.csv` | 60-min, 8,760 rows | full year | none |
| `PV_Electric_15_Minute_2-1-2025_3-4-2025_20250311.csv` | 15-min, 3,072 rows | Feb 2025 | 238.5 kWh |
| `Electric_60_Minute_2-1-2025_3-4-2025_20250311.csv` | 60-min, 768 rows | Feb 2025 | none |

Two different meters: `06536861` (the solar/PV account, 7,319 kWh/yr import) and `06324798`
(a near-zero 1,644 kWh/yr account). Publisher-anonymised name/account/street; **the ZIP
(92122) and the meter numbers are NOT removed**, so these need scrubbing before any vendoring.

This single repo closes **three** of the four never-seen items at once:
- **15-minute** (item 2) — only 60-minute had ever been seen;
- **March / spring-forward** (item 3) — the year files span 2024-03-10 AND 2024-11-03, so
  both DST transitions are now exercised on both shapes;
- **a populated Generation register** (item 4) — and it answers the pre-netting question:
  `Net` IS pre-netted (10,282 negative rows), and the preamble's `Total Usage` is the **NET**
  sum, not the consumption sum (7318.845 - 2944.910 = 4373.935 exactly).

**No bills.** Two dashboard screenshots only — see the reconciliation note below.

## 2. ookla-ariel-ride/SDGE-Analysis — 26 itemised bills, no intervals, MIT

https://github.com/ookla-ariel-ride/SDGE-Analysis. The raw Green Button CSV is deliberately
gitignored, but the **de-identified bill extractions are committed and MIT-licensed**:

- `data/bill_periods_electric.csv` — 26 statements, 5/25/2024 → 6/26/2026: days, net and
  gross kWh, SDG&E delivery $, CCA generation $, total $, and the fixed charge.
- `data/bill_tou_detail.csv` — **216 rows of per-statement, per-season, per-segment,
  per-TOU-period kWh AND printed $/kWh**, split across delivery and generation.
- `data/rate_vintages.csv` — their independent transcription of the printed rates, with an
  explicit evidence/absent column.
- `data/hourly_profile.csv`, `data/monthly.csv` — aggregates only, not interval data.

The household is **CEA (Clean Energy Alliance)** — which we have authored — on **NEM 2**,
and the corpus straddles the bundled→CCA switch (Dec 2024) and the fixed-charge change
(Oct 2025). **Five statements carry two rate segments**, i.e. real printed proof of the
mid-period vintage split our specs model.

⚠ **Unverified third-party extraction.** The bill PDFs are not published, so the extraction
cannot be audited. Treat as a lead, not as a golden fixture.

⚠ **It does not agree with our spec.** Our `sdge_tou_dr1_delivery_2026-06-01.yaml` says the
UDC total is period-flat at **0.32948**; their 5/29/26-6/26/26 statement prints delivery at
**0.30203** on/off-peak and **0.02606** super-off-peak. Either their extraction is
NEM-2-netted rather than tariff rates, or our flat-UDC reading is wrong. **Resolving this is
the single highest-value follow-up in this note** — it is exactly the class of error the
reconciliation gate exists to catch, and it is unresolved.

## 3. Rejected candidates

- `j1fuller/{youpower,youpower-Billing,reallocation}` — three real 15-minute SDG&E exports,
  **no licence AND no anonymisation**: real company names, street addresses, account and
  meter numbers, in public repos. Inadvertent PII disclosure. Not usable, not downloaded,
  local copies deleted. Loads are near-zero commercial submeters anyway.
- Green Button Alliance samples — synthetic and XML, as session 13 found.
- IEEE DataPort "San Diego Residential Energy Consumption" — research instrumentation, not
  Green Button, no bills, gated.
- HuggingFace EnergyBench / EDS-lab, Kaggle "Southern California Energy Consumption" — no
  SDG&E Green Button CSVs, no tariff linkage.
- SDG&E publishes **no** sample export file; every path runs through a portal login.

## The one SDG&E-printed number now reproduced from a real SDG&E export

`SDG&E Peak Power on Bill 2.png` in the NEC repo prints, from the customer's own dashboard:

> Highest Usage Hour (Demand) this month: **6.8 kW on February 16, 2025 from 3:00am to 4:00am**

From `PV_Electric_15_Minute_2-1-2025_3-4-2025`, February's maximum 15-minute interval is
**1.7050 kWh at 3:45 AM on 2/16/25 → 6.82 kW**. Exact.

**So SDG&E's "Highest Usage Hour (Demand)" is the peak 15-MINUTE interval scaled to an hourly
rate (kWh x 4), labelled with the clock hour that contains it — NOT the energy used in that
hour.** The two rejected readings are worth recording so nobody re-derives them: the clock-hour
sum is 6.545 kWh and the rolling-hour maximum is 6.580 kWh. Neither is 6.8.

This is **not** a dollar reconciliation and does **not** close M1's DoD — invariant 1 needs
itemised bills within $2. It is the first time any SDG&E-printed figure has been reproduced
from a real SDG&E export in this project, and it independently confirms the parser reads
timestamps and magnitudes correctly.

## What is still missing

**Item 1 — one household's export paired with its own itemised bills — remains unfound.**
That is still the only thing that closes M1, and it still has to come from a recruited user
or from dad. The public corpus can validate the parser and can now stress the export
register and both DST transitions; it cannot earn the right to show anyone a dollar figure.
