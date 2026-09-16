# ACC re-import after the 2026 ACC adoption — the measurement (2026-09-16, session 28)

Written for: the next session, and for whoever re-runs this check after the December
republish. Scope: HANDOFF next-action #4, "re-import both utilities' current/NBT00 tables
and re-run `test_sdge_vintages_are_one_table_wearing_three_labels` and
`tests/nem3/test_acc_pge.py`".

## The result: nothing moved, and that is now a dated fact rather than an assumption

The CPUC adopted the 2026 ACC update on **2026-09-03 (D.26-09-007)**. Thirteen days later,
**neither utility has republished anything.** All eight committed ACC tables' source files
are byte-identical to the files they were imported from.

| source | recorded sha256 | re-fetched 2026-09-16 | publisher `Last-Modified` |
|---|---|---|---|
| SDG&E `Current Year NBT Pricing Upload MIDAS.csv` (NBT00) | `af86b282…` | **same** | 2025-12-23 |
| SDG&E `LY2026 NBT Pricing Upload MIDAS.csv` | `b92d7058…` | **same** | 2025-08-04 |
| SDG&E `LY2025 NBT Pricing Upload MIDAS.csv` | `b97e3215…` | **same** | 2025-08-04 |
| PG&E `PGE-Solar-Billing-Plan-Export-Rates.zip` (all five vintages) | `9b554698…` | **same** | 2024-12-18 |

The PG&E zip's five member CSVs were extracted and hashed individually as well; all five
match their manifests. SDG&E's page still offers 2023–2026 only and PG&E's zip still holds
five vintages with no 2027, so `test_the_2027_vintage_still_has_no_published_table` remains
correct for both utilities.

**Re-import was run anyway, not just hashed.** `scripts/build_acc_tables.py` was re-run
against the freshly downloaded SDG&E NBT00/LY2026 and PG&E Floating/2026 CSVs into a temp
directory: all four rebuilt tables are **byte-identical to the committed `.csv.gz`**, so the
importer itself (and the pandas it runs on) still produces the same table, which a hash
comparison alone would not have shown.

Incidental confirmation at file level: SDG&E's rebuilt `nbtcurrent` and `nbt2026` tables have
the **same content hash**, which is the file-level form of "one table wearing three labels".
PG&E's floating and 2026 tables differ only because their horizons start in different years
(2025 vs 2026); the overlapping years are equal, as `test_pge_vintages_that_collapse_into_one_table`
already pins.

## ⭐ What the check found that the brief did not anticipate: the floating table has a stated expiry

Both utilities' readmes bound how much of the floating (NBT00) table is *effective* rather
than illustrative, and **both bounds end on the same date**:

> **SDG&E**: "For NBT00 customers, only those rates for Pacific Standard Time **for the
> current year** are actual effective rates, and all rates after that are for illustrative
> purposes only." — horizon starts 2026, so: effective through **2026-12-31**.

> **PG&E**: "For NBT00 customers, only those rates for Pacific Standard Time **calendar year
> 2025 and 2026** are actual effective rates…" — horizon starts 2025, so: effective through
> **2026-12-31**.

This matters because every "the lock-in is worth $0" finding in this repo — SDG&E's
NBT25/NBT26/NBT00 identity, PG&E's NBT26 ≡ NBT00 — is a claim about the *currently published*
floating table. The vintage tables are frozen by the lock-in; **the floating one is not**, and
when it moves those findings change without any file in this repo changing. Nothing in the
repo would have noticed.

So the answer to "install this year or next?" as of today is: **the 2026 lock-in is worth
exactly $0 observable, on both utilities, and the first date on which that can change is the
republish due before 2027-01-01** — which will carry D.26-09-007's ACC. That is a real dated
answer, not a hypothetical one, and it is the one an installer's "lock in before rates drop"
pitch cannot give.

`test_the_floating_table_has_not_outlived_its_own_effective_window` now fails on 2027-01-01
if the tables have not been re-imported by then. It is derived from each table's own horizon,
so a re-import moves the window without anyone editing a year.

## Provenance: `verified:` in the manifests

`retrieved:` says when bytes were fetched; it cannot distinguish *old* from *stale*. Only a
re-check can, so each manifest now carries `verified:` — dates on which the publisher was
confirmed to still serve the same bytes. `carry_forward_verifications()` (in `src/nem3/acc.py`,
so it is importable and tested) keeps prior dates **only while the source sha256 is unchanged**;
a reissued file starts a fresh list rather than inheriting a history about different bytes.

## How to re-run this check

```bash
# SDG&E — 3 MB each, CSV inside the zip
curl -sSLO https://www.sdge.com/sites/default/files/CurrentYearNBTPricingUploadMIDAS.zip
curl -sSLO "https://www.sdge.com/sites/default/files/LY2026%20NBT%20Pricing%20Upload%20MIDAS.zip"
# PG&E — one 36 MB zip holding all five vintages
curl -sSLO https://www.pge.com/assets/pge/docs/vanities/PGE-Solar-Billing-Plan-Export-Rates.zip
sha256sum *.zip              # PG&E zip: compare against the citation in pge_nbt*.yaml
unzip -o '*.zip' && sha256sum *.csv   # compare against source_sha256 in each manifest
```

If a hash differs, import it (`PYTHONPATH=src python scripts/build_acc_tables.py --utility …`)
and re-run `tests/nem3/test_acc.py` and `tests/nem3/test_acc_pge.py`. The tests that will tell
you whether the vintage question has become real:
`test_sdge_vintages_are_one_table_wearing_three_labels` and
`test_pge_vintages_that_collapse_into_one_table[2026-current]`. **If either fails after a
re-import, the nine-year lock-in has an observable dollar value for the first time** and the
⭐ findings in HANDOFF, `test_acc_pge.py`'s module docstring and `docs/METHODOLOGY.md` need
restating rather than patching.
