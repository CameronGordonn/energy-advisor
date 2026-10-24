# Independent cross-check: SDG&E specs vs. `corruptbear/my_sdge`

**Date:** 2026-09-08 (session 15) · **Result: zero errors found in our specs.**
**Scope:** the three 2026 vintages both projects cover — 1/1, 4/1, 6/1 — plus our 5/1
window-split vintage, which has no counterpart in theirs.

## Why this was worth doing

Our SDG&E engine has never met a real bill. Invariant 1 (reconciliation-gated) is
unmet for SDG&E and stays unmet — **this exercise does not and cannot change that.**
What an independent transcription *can* test is the layer underneath: whether we read
the tariff sheets correctly. A second party reading the same PDFs and arriving at the
same numbers does not prove the bill engine is right; it removes transcription error as
an explanation if it later turns out to be wrong.

## The comparand

`github.com/corruptbear/my_sdge` — an unaffiliated SDG&E bill calculator, active since
Dec 2022, hand-maintaining SDG&E residential rates in YAML across 9 vintages. Session 13
already drew on this repo from the other direction: its
`example/Electric_60_Minute_11-1-2022_11-30-2022_20230819.csv` is the real anonymised export
that exposed the two `src/greenbutton/sdge.py` parser defects. This pass looks at its rates.

- Rates: `rates/historical_rates/sdge_rates_{20260101,20260401}.yaml`,
  `rates/sdge_rates_20260601.yaml`
- Period/season/holiday logic: `sdge_hourly.py` (in code, **not** versioned with the rates)
- Mirrored source PDFs: `rates/20260601_schedules/`,
  `rates/historical_rates/original_pdfs/20260101_schedules/`

**Nothing from that repo is vendored here** — it has no LICENSE file. It was read in a
scratch directory and is cited by URL only. Their model is *totals* (delivery+generation
fused, `TOU-DR1.summer.peak`), ours is *layers*; the comparison reconstructs their totals
by summing our two layers, which is itself a check that our layer split is coherent.

## Results

| Quantity | Cells | Result |
|---|---|---|
| TOU-DR1 total $/kWh, 6 season×period cells × 4 of our vintages | 24 | **exact, all 24** |
| PCIA by vintage year (18 years × 3 sheets) | 54 | **exact, all 54** |
| Baseline Adjustment Credit (per vintage) | 4 | **exact** (.10905 / .10892 / .10892 / .10663) |
| Base Services Charge $/day | 4 | **exact** (0.79343) |
| Baseline allowances, Basic, 4 zones × 2 seasons | 8 | **exact** |
| SDCP 2021V PowerOn generation @ 5/1 (their 6/1 CCA file) | 6 | **exact** |
| TOU-DR2 total $/kWh, 4 cells × 3 vintages, + 3 credits † | 15 | **exact, all 15** |
| TOU period hour-sets, weekday + weekend/holiday | — | **exact** |

**115 value-level comparisons, zero mismatches** (some values, e.g. the 0.79343 fixed
charge, repeat across vintages). Every one of our four 2026 TOU-DR1 vintages reconstructs
their published total to the fifth decimal.

† **The TOU-DR2 rows cover uncommitted work.** Eight spec files were sitting untracked in
`src/tariffs/specs/` when this cross-check ran — earlier TOU-DR2 and EV-TOU-5 vintages from
another session working HANDOFF action 3, including the first TOU-DR2 **generation** specs.
They were not written here and were not modified here, but they are in scope, so they were
checked: TOU-DR2 delivery+generation reconstructs their published total exactly at 1/1, 4/1
and 6/1, the baseline credit matches at all three, and the delivery and generation layers
carry byte-identical `tou.rules` at every vintage. The four EV-TOU-5 delivery vintages
correctly mirror the 4-way window split (`months: [3, 4]` at 1/1 and 4/1, year-round at 5/1
and 6/1). **Whoever picks that work up: those files cross-check clean.**

Separately, using their **mirrored PDFs** as a second copy of the source document (this
checks our transcription, not their reading), the full UDC component decomposition —
Transm / Distr / PPP / ND / CTC / LGC / RS / TRAC / UDC Total / WF-NBC+DWR-BC / EECC —
verified line-for-line for TOU-DR1 @ 1/1 and @ 6/1, TOU-DR2 @ 6/1, and EV-TOU-5 @ 6/1.
Our `non_bypassable` component values (PPP 0.01515, ND 0.00000, CTC −0.00007,
WF-NBC/DWR-BC 0.00591) are confirmed against both sheets, as is the absence of any CEC
surcharge column — the flagged approximation that we deliberately do not assert either
way is correct to leave unasserted.

The HANDOFF claim that **~45% of EV-TOU-5's super-off-peak delivery charge is
non-bypassable** is confirmed off the sheet: (0.01515 − 0.00007 + 0.00591) / 0.04705 = 44.6%.

## (a) The 2026-05-01 super-off-peak window — the important question

**Corroborated on the substance. Not corroborated on the date. And the tariff book now
actively contradicts both of us.** Three separate findings, which point different ways:

**1. They independently found the same rule change, and previously held our old rule.**
Before commit [`be51c30`](https://github.com/corruptbear/my_sdge/commit/be51c303) their
code read:

```python
is_march_or_april = 1 if (date.month == 3 or date.month == 4) else 0
...
if is_march_or_april:
    WEEKDAY_HOURS["super_offpeak"] = {0, 1, 2, 3, 4, 5, 10, 11, 12, 13}
```

— which is exactly our `{period: super_off_peak, hours: [[10, 14]], days: weekday,
months: [3, 4]}`. That commit, **2026-06-10, "apply extended super-offpeak hours"**,
deletes the month condition and makes 10:00–14:00 weekday super-off-peak unconditional.
So an unaffiliated party maintaining this code since 2022 held the March/April rule,
then removed it in 2026 for the same reason we did. **That is real corroboration that
the change happened**, from a source that is not SDG&E marketing and not a CCA.

**2. It is not corroboration of 2026-05-01.** Their windows live in code with no
effective date, so the change applies retroactively to all nine of their vintages —
their 2023–2026-04 files now price March/April-only months as year-round. They cannot
distinguish 5/1 from 6/1, and the commit landing 2026-06-10 alongside their 6/1 rate
update is equally consistent with either. On the *date* they are silent, and their
handling is strictly worse than ours: unversioned windows are the exact failure our open
decision 8 (rate-date vs window-date splitting) exists to prevent.

**3. ⚠ NEW, and it cuts against the change: the tariff book still says March and April.**
`sdge.com/sites/default/files/elec_elec-scheds_tou-dr1.pdf`, retrieved 2026-09-08 from
SDG&E's *current and effective tariffs* library, prints under **Time Periods**:

```
 Off-Peak      6:00 a.m. – 4:00 p.m.
               Excluding 10:00 a.m. – 2:00 p.m. in March and April;
               9:00 p.m. - midnight
 Super Off-Peak   Midnight – 6:00 a.m.
                  10:00 a.m. – 2:00 p.m. in March and April
```

Cal. P.U.C. Sheets 29952–29955-E, **Advice Ltr. 3167-E, effective Jan 1 2018** — the
same sheets our specs cite. This explains why sessions 8 and 9 never located a
superseding advice letter: **the tariff book was never updated.** It does not by itself
mean the window did not change — that PDF is a 2018 snapshot whose *rates* are also 2018
(EECC 0.29722 etc.), and SDG&E moves rates through Total Rates Tables while the tariff
book lags. But it means the operative filed tariff, as published today, still restricts
the window to March and April, and no filed document contradicting it has been found.

Two incidental confirmations from the same sheet: the weekend/holiday table
(SOP midnight–2pm, off-peak 2–4pm & 9pm–midnight, on-peak 4–9pm) matches ours exactly;
and the March/April carve-out is printed **only in the Winter column**, which makes our
season-free `months: [3, 4]` rule exactly equivalent, since March and April are winter
months under Schedule EECC.

**Independent documentary support for the 5/1 date did improve**, from a direction worth
recording. Their repo mirrors SDCP's `Res_2021V_042026.pdf` — an *April*-named file whose
body says **"Effective May 1, 2026"** five times, and whose PowerOn TOU-DR1 rates
(0.29579 / 0.08635 / 0.01000 / 0.22513 / 0.14758 / 0.06144) are cell-for-cell our
`sdcp_2021v_tou_dr1_generation_2026-05-01.yaml`. Its printed TOU table shows weekday
super-off-peak "Midnight – 6:00 a.m.; 10:00 a.m. – 2:00 p.m." in **both** seasons with no
month exclusion — while the SDCP sheet their 1/1 file uses (Effective February 1, 2025)
still prints "Excluding 10:00 a.m. – 2:00 p.m. in March and April". Same publisher,
consecutive dated sheets, the change stamped **May 1, 2026**.

**Net:** open decision 1 stays resolved as modeled — year-round from 2026-05-01, earlier
vintages `months: [3, 4]`. The residual caveat does not close, and should be restated
more sharply than "the advice letter was never located": *SDG&E's filed tariff sheet, as
served today, still says March and April, and the 5/1 date rests entirely on
customer-facing publications plus dated CCA sheets.* Our per-vintage split is the right
structure precisely because it survives being wrong about the date — one file changes.

## (b) DR-SES and EV-TOU-2 — worth adding? (not added)

**DR-SES — yes, and it is the more valuable of the two.** "Domestic Time-of-Use for
Households with a Solar Energy System" @ 6/1/2026: UDC Total flat **0.26328** (TRAC
0.00000, against TOU-DR1's 0.06620) → delivery 0.26919 vs TOU-DR1's 0.33539, i.e.
**6.6¢/kWh cheaper on every imported kWh**. But its EECC is far steeper (summer on-peak
0.47019 vs 0.34920; summer super-off-peak 0.08147 vs 0.04121) and — the part a careless
comparison would miss — **it carries no Baseline Adjustment Credit at all**, where
TOU-DR1 credits −0.10663/kWh up to 130% of baseline.

That combination is squarely our territory: which schedule wins is a pure function of
the household's import shape and baseline allowance, it cannot be answered from a
marketing page, and it is aimed at exactly the population M3 exists to advise. Ranking a
solar household's schedules without DR-SES on the menu is a genuine gap. Deferred, not
dismissed — and gated behind the same unmet SDG&E reconciliation as everything else.

**EV-TOU-2 — no, not now.** Whole-house EV schedule @ 6/1/2026: UDC Total 0.30372
on/off-peak, 0.16275 super-off-peak (vs EV-TOU-5's 0.31711 / 0.04114). Cameron has no
EV, EV-TOU-5 is already specced and is the current EV offering, and EV-TOU-2's
enrolment status is unverified — do not assert it. Add if an EV household appears.

One thing to carry forward if either is ever added: **PPP is not a schedule-independent
constant.** It is 0.01515 on TOU-DR1 / TOU-DR2 / EV-TOU-5 / DR-SES but **0.01713** on
EV-TOU and EV-TOU-2, which also carry LGC 0.01235. Our `non_bypassable` block is
per-spec, so this is not a live bug — but a copy-paste of the TOU-DR1 NBC block onto an
EV-TOU spec would silently misstate the NBT import floor.

## Discrepancies found — all three are theirs

Recorded because they are instructive, not to score points.

1. **Stale CCA sheet on their 1/1/2026 file.** Their `CCA-TOU-DR1` for 1/1/2026 pairs
   correct SDG&E 1/1/26 rates with SDCP generation read from
   `Schedule-for-WebsiteRes_2021V.pdf`, whose body says **"Effective February 1, 2025"** —
   11 months stale. Their implied summer super-off-peak generation is **0.08111** against
   the January-2026 sheet's **0.01000** we carry: 8× wrong, and precisely on the
   battery-charging window. A layered model makes this kind of drift visible; a fused
   total hides it.
2. **All-electric baseline allowances wrong.** Their `summer_electric = [6, 8.7, 15.2,
   17]` / `winter_electric = [8.8, 12.2, 22.1, 17.1]` (sourced to
   `sdge.com/baseline-allowance-calculator`, uncited) match no current table.
   **Adjudicated against the tariff:** Schedule DR, Special Condition 3, Cal. P.U.C.
   Sheet 29294-E (Advice 3130-E, eff. Dec 1 2017), retrieved 2026-09-08, prints
   Basic S 9.0/10.4/13.6/15.9, W 9.2/9.6/12.9/10.9 and **All Electric S 8.3/10.1/16.5/18.5,
   W 13.5/15.8/26.0/20.0** — **our** numbers, exactly, on all sixteen cells. Their Basic
   row is right; their All-Electric row is not. Their winter coastal all-electric (8.8)
   is also *below* Basic (9.2), which is backwards for a heating-electrified household.
3. **Holiday calendar too broad.** They use pandas `USFederalHolidayCalendar` (11 days);
   SDG&E Electric Rule 1, which we implement, lists 8 — no MLK Day, Juneteenth, or
   Columbus Day. On those three weekdays they apply the weekend schedule, pricing
   06:00–10:00 as super-off-peak instead of off-peak. Small (~$1–3/yr) but systematic.
   Their observance rule also shifts Saturday holidays to Friday; Rule 1 does not.

## What this exercise could *not* check

Stated so the corroboration is not read as broader than it is.

- **CARE — no cross-check exists.** They do not model CARE at all. Our CARE derivation
  (exact split on all four vintages, `test_sdge_vintages.py`) remains checked only
  against SDG&E's own printed CARE tables. Open decision 9 (CARE composition on a CCA)
  is untouched by any of this.
- **The EV-TOU-5 generation layer.** We hold delivery only, so EV-TOU-5 totals cannot be
  reconstructed from our specs. Their total *minus* our delivery yields EECC values matching
  the mirrored PDF's EECC column exactly — which corroborates our delivery numbers, but is
  not a check on a generation layer we do not have. (TOU-DR2 *was* fully checkable once the
  untracked generation specs were taken into account — see † above.)
- **Minimum bill.** Confirmed at $0.329/day and $0.164/day CARE from the current-and-
  effective Schedule DR sheet retrieved today — but that sheet is still the Advice 3167-E
  / Jan 1 2018 filing. The flagged approximation stands as recorded: no 2026 table
  restates it. Marginally stronger than before (SDG&E serves this as current), not resolved.
- **NEM 3.0 / ACC, netting, NBC settlement, franchise fee, climate credit.** Entirely
  outside their scope.
- **Anything about whether our bill engine produces a correct bill.** Agreement on rate
  transcription is not reconciliation. M1's DoD is unchanged and still blocked on one
  real SDG&E export plus three itemised bills.

## Sources

- https://github.com/corruptbear/my_sdge — rates YAML, `sdge_hourly.py`, commit `be51c303`
- https://www.sdge.com/sites/default/files/elec_elec-scheds_tou-dr1.pdf — Sheets 29952–29955-E
- https://www.sdge.com/sites/default/files/elec_elec-scheds_dr.pdf — Sheet 29294-E (SC 3)
- SDG&E Total Rates Tables, TOU-DR1 / TOU-DR2 / EV-TOU-5 / DR-SES / EV-TOU-2, 1/1/26 and 6/1/26
- SDCP `Res_2021V_042026.pdf` (Effective May 1, 2026) and `Schedule-for-WebsiteRes_2021V.pdf`
  (Effective February 1, 2025)
