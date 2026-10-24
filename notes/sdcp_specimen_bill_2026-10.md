# The SDCP specimen bill, priced: rates exact, ~$11 of unmodelled lines (2026-10-01, session 31)

Written for: Cameron, and whoever transcribes the first real SDG&E bill into
`tests/golden_bills/sdge_BILL_ONLY_TEMPLATE.yaml.example`.
Question asked: **is there anything on the internet that can be used for M1a now that the
bill-only path exists?** (The session-23 search looked for export + bill pairs; M1a needs only
an ordinary non-solar statement, which is a different search.)

## The find: a complete 2026 TOU-DR1 / SDCP statement, published by SDCP

`sdcommunitypower.org/understanding-your-bill/` embeds four PNG pages of an SDG&E statement
(file names `SDCP_T2b_web-design_understanding-your-bill_BILL-PAGE-{1..4}_2026_V2_DRAFT1_052926*.png`,
under `wp-content/uploads/2026/05/`, retrieved 2026-10-01). `curl` gets 403; `WebFetch` saves
the bytes (HANDOFF's field note, again). Local copies, **gitignored, not vendored**:
`data/sources/sdcp_specimen_bill_2026-03/page{1..4}.png` (sha256 in SESSION_NOTES).

What it prints — every input the bill-only template asks for:

| | |
|---|---|
| Schedule | TOU-DR1 Residential, **Climate Zone Coastal**, Secondary |
| Supplier | San Diego Community Power, "TOU-DR-1 - **2021 Vintage**" (cohort and PCIA vintage) |
| Period | 2/12/26 - 3/13/26, **30 days**, one rate block (no vintage boundary inside it) |
| kWh | On-Peak **73**, Off-Peak **115**, Super Off-Peak **63** = 251 |
| Baseline allowance | **264 kWh** (see below — disagrees with our spec) |
| SDG&E delivery | $100.83 (electric charges $92.42 + taxes & fees $8.41) |
| SDCP generation | $39.81 |
| Total | **$140.64** |

## ⚠ It is a specimen, not a real household's bill — it cannot count toward M1a

- Account `0012 3456 7890 1`, meter `00000000`, CCA account `1234567890`, RIN `USCA-XXSA-0426-0000`.
- SDG&E's own CCA-bill page labels its equivalent images "for illustrative purposes only".
- **Its own arithmetic does not close**: SDCP's three generation lines print $16.39 / $16.98 /
  $3.86, but 73 x 0.22551 = 16.46, 115 x 0.14787 = 17.01, 63 x 0.06163 = 3.88. And Power100
  bills **250** kWh against 251 used. A real billing system does not do either.

So it is **corroboration, the same tier as `tests/published_impacts/`**, and invariant 1 is
untouched: no SDG&E dollar figure is earned by it.

## Priced through `compute_bill_from_usage` — every modelled line matches

`territory=coastal_basic`, `service=cca`, `vintage="2021"`, `SDCP-2021V` generation, one
segment 2026-02-12..2026-03-13. Every rate printed on the statement equals the 2026-01-01
spec value **to the fifth decimal**: UDC 0.34101, Base Services 0.79343/day, baseline credit
-0.10905, PCIA-2021 0.03557, WF-NBC 0.00591, SDCP winter 0.22551/0.14787/0.06163, and — on the
offset "Electricity Generation" line SDG&E prints for CCA customers — bundled EECC winter
0.27508/0.19327/0.10241.

| | printed | ours | gap | cause |
|---|---|---|---|---|
| Base Services Charge | 23.80 | 23.80 | 0 | |
| Delivery energy (+ WF-NBC) | 85.59 + 1.48 | 87.09 | +0.02 | we price at 0.34692 combined; SDG&E rounds two lines |
| Baseline Adjustment Credit | -27.37 | -27.37 | 0 | |
| PCIA 2021 | 8.93 | 8.93 | 0 | |
| Economic Development Program Credit | -0.01 | — | +0.01 | **not modelled** |
| City of San Diego Franchise Fee Differential | 4.74 | — | -4.74 | **not modelled** (spec says deliberately; customer fact) |
| Franchise Fee Equivalent Surcharge | 3.42 | — | -3.42 | **not modelled** |
| State Regulatory Fee | 0.25 | — | -0.25 | **not modelled; never seen before** |
| SDCP energy | 37.23 | 37.35 | +0.12 | the specimen's own lines don't equal kWh x rate |
| SDCP Power100 | 2.50 | — | -2.50 | opt-in product, customer fact, **not modelled** |
| State Surcharge Tax | 0.08 | — | -0.08 | **not modelled** (= 251 x 0.0003, the CEC surcharge) |
| **Total** | **140.64** | **129.80** | **-10.84** | |

The unmodelled lines total $10.98; with them our figure would be $140.78, and the remaining
+$0.14 is exactly the specimen's internal inconsistency ($0.12) plus the two-line rounding
($0.02). **Nothing is unexplained.**

## ⭐ What this changes: "M1a needs nothing but transcription" is false a third time

The bill-only harness is built and correct, but **a real SDCP / City of San Diego statement
would miss ±$2 by about $8–11** — every one of those lines sits on an ordinary bill, not on an
edge case. Sessions 24 and 29 each found "ready" was a sentence; this is the same finding one
layer down, measured before a real bill rather than on one. Before the first real bill arrives:

1. **City of San Diego Franchise Fee Differential** — 5.78% x $82.01. The base is total electric
   charges **excluding PCIA and the Wildfire Fund charge** (92.42 - 8.93 - 1.48 = 82.01 exactly).
   It is a *city* fact, so it belongs in `customer:` (like `territory`), and its rate and the
   cities it applies in need a tariff citation (Schedule TOU-DR1 refers to it; locate the
   franchise-fee sheet).
2. **Franchise Fee Equivalent Surcharge** — 6.88% x $49.71, CCA customers only. **The base is
   not derived**: it is not EECC generation (48.76), SDCP energy (37.23/37.35), or either plus
   the PCIA. Needs SDG&E's franchise-fee surcharge schedule. Do not fit it.
3. **State Regulatory Fee** — 251 kWh x $0.001000. Not in any SDG&E Total Rates Table we hold.
   Find its authority (likely a CPUC/state fee new for 2026) before encoding; `UNVERIFIED` until then.
4. **CEC Electrical Energy Surcharge** — $0.0003/kWh, printed on the CCA side as "State
   Surcharge Tax". HANDOFF's flagged-approximations list says SDG&E's tables show no such
   column "so it is deliberately NOT asserted either way". **This specimen is the first
   SDG&E-territory document that shows it billed.**
5. **Economic Development Program Credit** — -$0.01 here; source and rate unknown.
6. **SDCP Power100 / Power100 Plus** — the customer's product choice; a `customer:` fact,
   $0.01/kWh here, from SDCP's rate sheet (citable).

Items 1–3 are ~$8.41 on a $140 bill. **This is code + citation work that needs no household
data**, which makes it the highest-value build available while the project waits for a bill.

## Two disagreements with what the repo currently states

- **Baseline allowance.** The specimen prints **264 kWh** for 30 Coastal winter days =
  8.8/day. Our spec (Sheet 29294-E, re-verified session 15) says Coastal Basic winter
  **9.2/day = 276**. No dollar effect here (251 < 264), but on a heavier bill it is a
  ~12 kWh x $0.109 = $1.31/month swing. A cropped **real 2024 CEA statement** (GPL-3.0,
  `mykwhnow/static-website/content/images/sdge-bill-tou.png`, 2/15/24-3/15/24, Coastal,
  30 days) prints **276** — agreeing with our spec. So the specimen is probably built on an
  older or different template. Weak evidence either way; noted, spec unchanged.
- **How SDG&E prints the delivery rate.** `test_our_delivery_rate_less_the_import_floor_is_what_sdge_printed`
  (tests/tariffs/test_sdge_layers.py) states as a general fact that SDG&E prints the
  delivery Rate/kWh **excluding the whole 0.02099 NBC/PPP bundle**. On this non-NEM TOU-DR1
  statement the printed rate is **0.34101 = our rate - 0.00591 (WF-NBC only)**; PPP, ND and
  CTC are *inside* the printed rate, and only the Wildfire Fund charge is a separate line. The
  likeliest reconciliation is that NEM statements (the EV-TOU-5 corpus is NEM-2) pull the NBCs
  out to bill them on gross consumption, while ordinary statements do not — the 2024 CEA
  excerpt above prints a "Non Bypassable Charges Usage" field, consistent with that. **The
  test's numbers are right; its docstring over-generalises.** No dollar impact (the sum is the
  same), but it decides which `expected.line_items` a transcriber maps the delivery lines to.

## Searched and not useful (so nobody re-runs them)

- `sdge.com/understanding-your-cca-bill`, `sdge.com/BillHighlights`: illustrative images, no
  numbers.
- `thecleanenergyalliance.org/understanding-your-bill/`: points at SDG&E's sample, no figures
  in the page.
- `mykwhnow.com` bill guide: two cropped real 2024 CEA statement excerpts (above) — labels and
  the baseline allowance, no charges.
- No public ordinary non-solar SDG&E statement with real identifiers removed was found. The
  real-bill ask in HANDOFF next-action #1 stands.

## Second pass, same session: a REAL homeowner's SOLAR bill (Cameron asked explicitly)

Searched where homeowners post their own statements rather than where utilities post samples.
**Real solar bills exist publicly; none is usable as a golden bill.** Ranked:

| Source | What it is | Why it is not a fixture |
|---|---|---|
| `ookla-ariel-ride/SDGE-Analysis` (MIT) | 26 real de-identified SDG&E statements, NEM-2 + solar, CEA, EV-TOU-5 | Already known (session 23/28). Totals are NEM-2 true-up accruals, and this engine models NBT, not NEM-2 carryforward. **Still the best real solar-bill corpus public.** |
| r/solar post `1wlu212` "Solar PG&E NEM 3", re-hosted by thecooldown.com (`wp-content/uploads/2026/09/solar-pg-e-nem-3-v0-om1zxkqrxqqh1.webp`) | **Real PG&E NBT ("Solar Billing Plan") statement**, SVCE, statement date 2026-09-10, page 1 of 9 | Page 1 only — no TOU import/export, no export-credit detail. No licence. **The owner's redaction is see-through** (name/address legible under the boxes) — do not save, transcribe or vendor it. Reddit itself 403s every fetch route, so pages 2–9 (if posted) are unreachable from here. |
| CPUC C.26-03-034 *Howe v. SDG&E* | Real SDG&E solar homeowner (NEM-1/2, battery, EV-TOU-5), public record | Account is the subject of a **faulty-meter** dispute (billed on averages 2020–2025) — the one bill we must not reconcile against. Full PII in the filing. |
| CPUC C.25-06-009 *Riggins v. PG&E* | Real PG&E solar homeowner, NEM-2, monthly statements attached as Exhibit 2 | NEM-2; a $9,000 true-up dispute and a later non-export system; exhibits not in the public answer. |
| `ericbusboom/garage-renovation` | Homeowner's own 2026 monthly bills | Pre-solar, monthly totals only, no itemisation. |

TMC and diysolarforum threads where owners discuss NBT bills return 403 to both fetchers.

**One thing the r/solar page 1 does give, as corroboration only:** "Current charges include a
discount of $36.18 for CA Climate Credit" on a PG&E statement dated 2026-09-10 (period
08/03–09/01/2026). That is `src/tariffs/climate_credit.yaml`'s PG&E 2026 figure ($36.18, paid
Aug/Sep under the CPUC's 2026 move) on a real customer bill — the first outside sighting of the
new months on a statement. It does not settle *which* statement receives a credit (HANDOFF's
open question), since one sighting can't distinguish the candidate rules.

**Conclusion, stated so the next session does not re-search:** a usable real solar bill (all
pages, itemised imports/exports and export credits, clean account, NBT) is not on the public
web in a form this project can reach or ethically use. M3's DoD still needs a recruited
household. The ask for that household is: all pages of 1–3 NBT statements **plus** the Green
Button export covering them.

## Built (same session, branch `sdge-fee-lines`)

Cameron approved building the fee lines. What landed, against the specimen:

| Line | Printed | Ours | Source |
|---|---|---|---|
| City of San Diego Franchise Fee Differential | 4.74 | **4.74** | TOU-DR1 Sheet 29955-E; Schedule CCA Sheet 23574-E |
| Franchise Fee Equivalent Surcharge | 3.42 | **3.35** | Schedule CCA Sheets 23574-E / 19741-E (on *imputed* EECC); 6.88% / 1.1% from sdge.com |
| State Surcharge Tax (CEC) | 0.08 | **0.08** | CDTFA L-1020, $0.0003/kWh for 2026 |
| State Regulatory Fee | 0.25 | — | no authority found → observed adjustment |
| Economic Development Program Credit | -0.01 | — | unknown → observed adjustment |
| SDCP Power100 | 2.50 | — | opt-in product → observed adjustment |

Modelled total **$137.97**; plus the three observed lines, $140.71 vs $140.64 printed (+$0.07,
the FFES base gap). Design:

- **`jurisdiction`** (`city_of_san_diego` | `other`) is a new customer fact, threaded like
  `territory`: required by any spec carrying a city-dependent fee, refused when missing or
  unknown, a fixture `customer:` key, and a field on `NbtSettings`.
- **The differential's base** is `pretax` minus an explicit `exclude:` list — the PCIA line
  and the Wildfire Fund NBC component (rebuilt as kWh x rate because it is folded into our
  energy rate). Ours is 82.04 vs 82.01 printed: +0.01 unmodelled EDP credit, +0.02 SDG&E
  rounding delivery and WF as two lines. Both named in the test.
- **The equivalent surcharge is bill-level** (`of: imputed_generation`): the engine prices
  the provider's EECC on the customer's own usage as a bundled customer and takes 6.88% / 1.1%
  of it. Its imputed base on the specimen is 48.76, the printed "Electricity Generation"
  line, exactly. The printed base is 49.71; **that 0.95 is unexplained and not fitted.**
- **Refused, not guessed** (`UnverifiedChargeError`): the differential for a **bundled**
  customer in the city (is EECC inside the base?), and either line for a **CARE** customer
  (before or after the discount? imputed at which rate?).
- NBT netting bills the equivalent surcharge as non-volumetric, so no export credit reaches it.
- Tier 2 strips these surcharges before pricing SDG&E's rate alerts: the alerts price the
  Total Rates Table, which contains no franchise fee.

**Closed in session 32 (2026-10-23).** The gap was TOU-DR1-only lines: TOU-DR2, EV-TOU-5 and
TOU-DR-P billed a City of San Diego household with no differential and no refusal. Reading
the sheets closed it, and also settled the bundled case refused above:

- **Schedule EECC carries its own clause** (Sheet 13, Cal. P.U.C. Sheet 30030-E): "A Franchise
  Fee Differential of 5.78% will be applied to the total bills calculated under this
  schedule, including DWR charges, for all customers residing within the corporate limits of
  the City of San Diego." Applicability (30018-E): all bundled customers. So a bundled bill
  pays 5.78% on delivery (the delivery schedule's clause) **and** on generation (EECC's), as
  two lines. Cross-check: Schedule CCA's 6.88% in-city vs 1.1% outside is a 5.78-point gap.
- Delivery clauses read: TOU-DR2 Sheet 29959-E; TOU-DR (TOU-DR-P's delivery) Sheet 29915-E;
  EECC-TOU-DR-P Sheet 29436-E for TOU-DR-P generation. All say the same as TOU-DR1.
- **EV-TOU-5's own schedule sheet was not found** (the obvious URL 404s; searches return
  only rate tables). Its delivery line is `unverified_for: [bundled, cca, care]`, so a city
  household on it refuses. Every sheet read has the clause, but analogy is not a citation.
- **Still refused:** CARE on any line (Schedule E-CARE is silent on franchise fees); a CCA
  customer on TOU-DR2 / TOU-DR-P / EV-TOU-5 in the city (those specs carry no PCIA to
  exclude).
- Engine: the imputed EECC layer is priced with `surcharges=False`, so EECC's own
  differential never enters the Schedule CCA base (still 48.76 on the specimen).
- `test_every_sdge_spec_carries_the_city_differential` fails for any SDG&E spec without the
  line, so the gap cannot quietly come back with a new schedule or vintage.
- **Not validated against a real bundled statement** — none exists. The first bundled City of
  San Diego bill should check whether SDG&E prints one combined line or two.
