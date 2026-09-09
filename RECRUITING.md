# RECRUITING — M5 external users (SDG&E validation first)

Templates and intake instructions for M5. **Not published.** This file lives at the repo root
deliberately: `docs/` is served by GitHub Pages and may be being edited by another session.
It is still in a public repository, so nothing here may contain a real person's data, and see
the contact decision below before pasting a personal address into it.

Read alongside HANDOFF.md ("READ BEFORE STARTING M5") and ROADMAP.md M5.

---

## The sequencing rule this file exists to obey

M1's DoD is unmet: **the engine has never been run against a single real SDG&E bill or
export.** Invariant 1 (reconciliation-gated) therefore forbids sending any San Diego
household a dollar figure. The first recruit who supplies the data closes M1's DoD, and only
then does the SDG&E path earn the right to produce dollars for anyone else.

So there are two asks, deliberately separated, because their friction differs by an order of
magnitude:

| | Ask 1 — bill only | Ask 2 — full validation user |
|---|---|---|
| What we need | 1 itemised SDG&E bill (PDF or photos) | 13-month Green Button export + 3 itemised bills |
| Effort for them | ~5 minutes | ~20–30 minutes |
| Privacy conversation | almost none — no load shape | real; a year of 15-minute data is a picture of a home |
| What it validates | the whole charge-computation layer: rate math, baseline credit, NBCs, PCIA vintage, CCA layering | all of the above **plus** the parser, the interval pipeline, and TOU bucketing from raw data |
| Milestone effect | large partial credit; settles open decision 9 | **closes M1's DoD**, unblocks the SDG&E half of M2 |

Ask 1 works because **an SDG&E TOU bill prints kWh *and* dollars per TOU period.** Given the
bucketed kWh off the bill, every downstream charge is determined by the tariff specs — so the
bill alone tests the dollars-from-bucketed-kWh half of the gate without any interval data.
It does **not** test `src/greenbutton/sdge.py`, which session 13 showed would reject the real
export format outright, or the interval→TOU-bucket step. Ask 2 is still what closes M1.

Lead with Ask 1. It is also the cheapest route to settling **open decision 9** (how SDG&E
composes the CARE discount for a CCA customer), where two of SDG&E's own documents point
opposite ways and the answer is worth ~$170–210/yr to that household.

---

## Honesty constraints on every word below

Non-negotiable, and the reason the drafts read the way they do:

1. **No dollar figure, savings estimate, or payback number for any SDG&E household**, in a
   post, a DM, or a reply, until an SDG&E bill reconciles within ±$2. Not hedged, not
   "roughly", not "typically". Invariant 1.
2. **The one number we may lead with is the PG&E result**, because it is a measured artifact:
   11 of 11 real statements within ±$2, worst +$0.22, table in the README, regenerated from
   the test suite. Say "PG&E" every time it is said.
3. **Say plainly that SDG&E is not at that standard yet.** This is the pitch, not a weakness
   to bury — it is why we are asking, and it is the thing installer-side tools never say.
4. **Never promise a verdict in exchange for data.** The offer is participation in a
   validation, plus a full analysis *afterwards, if and only if the reconciliation passes*.
5. **A failed reconciliation is a deliverable, not an embarrassment.** If the engine misses
   their bill, they get the miss and the diagnosis. Say so in advance; it is what makes the
   ±$2 claim mean anything.
6. **Nothing is for sale.** M5's DoD includes a written go/no-go on charging, but that is a
   conclusion drawn from these conversations, not an offer made during them. Do not quote a
   price. If asked, say the project is free now and the question of whether it should ever
   cost anything is literally what this stage is for.
7. **Do not imply utility, CCA, CPUC or installer affiliation**, and do not use a utility
   logo. See docs/terms.html.

### Contact decision — settle before posting

Every template says `[CONTACT]`. Options, with the tradeoffs:

- **A dedicated address** (e.g. a new alias used only for this) — *recommended*. Keeps
  bill PDFs out of a personal inbox's search history and lets the channel be shut off cleanly
  after M5.
- **Reddit DM only** — lowest friction to start, but Reddit is a poor place to receive a file,
  and it puts an account name on the conversation.
- **A personal email address** — works, but it goes into a public repository the moment this
  file is pushed and gets scraped.
- **GitHub issues** — *wrong for this*. Issues are public; a stranger's rate schedule, CARE
  status and consumption would be published. Keep issues for what privacy.html already says
  they are: bug reports and privacy complaints.

Whatever is chosen, say in the post that files come **as an attachment to a plain email**, and
never ask anyone to upload to a third-party service.

---

## 1. Post — r/SanDiego

> **Operator notes before posting.** Check the subreddit's current rules on self-promotion and
> data solicitation and, if there is any doubt, message the mods first with a link to the repo
> — being pre-cleared is cheap and being removed as a scraper is expensive. Post from an
> account with history. Expect the top comment to be "what's the catch"; answer it in the
> post, not in replies. Do not crosspost the identical body to r/solar the same day.

**Title:** I wrote an open-source bill engine for SDG&E rates and need real bills to check it against — nothing for sale

---

I've been building an independent engine that recomputes a California electricity bill from
the customer's own meter data. It's open source (AGPL), there's no company behind it, no
account to make, and nothing for sale. I'm posting because it has a gap only San Diego can
fill.

**What I can back up:** on PG&E it reproduces **11 of 11** real monthly statements to within
$2 of the printed total — worst case 22 cents — computed from that household's own hourly
interval data. The comparison table and the code that generates it are public.

**What I can't back up yet:** the SDG&E side. TOU-DR1, TOU-DR2 and EV-TOU-5, the climate-zone
baseline allowances, the non-bypassable charges, the vintaged PCIA, and both San Diego CCAs
(San Diego Community Power and Clean Energy Alliance — including the fact that SDCP publishes
two different rate sheets depending on which jurisdiction enrolled you) are all implemented
from the published tariff sheets. **None of it has ever met a real SDG&E bill.** Until one
does, I will not send anyone in San Diego a dollar figure. That's a rule the project is built
around, not modesty — the whole point is that the arithmetic is checkable against a real
statement before anyone acts on it.

So, two asks. The first is small.

### Ask 1 — one bill, about five minutes

An SDG&E TOU bill prints both kWh **and** dollars for each time-of-use period. That means the
bill on its own tests almost the entire charge stack — the rate math, the baseline credit, the
non-bypassable charges, the PCIA vintage, the CCA layering — **without any usage file at all.**
No interval data means no picture of when you're home, which I think makes this an easy thing
to say yes to.

Send one recent itemised bill with your name, address and account number blacked out. What you
get back is a line-by-line comparison of what my engine computed against what you were actually
billed, with an explanation of every line. That is a test result, not advice, and not a savings
estimate. If it doesn't match your bill you get the mismatch, and I go fix the engine.

**One case is worth more than the rest:** a **CARE customer on SDCP or CEA**. There's an open
question about how SDG&E composes the CARE discount when your generation comes from a CCA, and
two of SDG&E's own published documents imply opposite answers. One real bill settles it, and it
matters to the household's actual total. If that's you, I'd particularly like to hear from you.

### Ask 2 — the full validation household

A 13-month Green Button interval export plus three itemised bills. This is the one that closes
the gap: it tests the file parser and the interval pipeline as well as the charges. It's a
bigger ask and a real privacy conversation, so I've written out below what I do and don't do
with it, and I'll answer anything on that before you send anything.

If the reconciliation passes on your bills, that household gets the full run, free: every rate
schedule you're eligible for re-simulated against your actual intervals and ranked, with the
usage conditions under which the ranking flips — and if you have solar or are considering it,
the NEM 3.0 export and battery analysis, reported as ranges rather than a single confident
number. The engine is equally willing to output "don't buy the battery"; it does that
regularly, and it shows you the conditions under which the answer would change.

If the reconciliation *fails*, you get that instead, in writing, and I have work to do.

### What I do with the file

Short version: it stays on my machine. Real exports and real bills are excluded from the
repository by configuration, not by memory. Nothing identifying is published — only anonymised
fixtures, and only with your say-so. Say the word and I delete it. Longer version in the repo.

### You can also just use it right now, without talking to me

There's a browser tool that reads your Green Button export **entirely inside your own browser**
— no upload, no server, no account — and shows you the shape of your own usage. It deliberately
shows you **no dollar figures**, for exactly the reason above. Links to the tool, the
methodology writeup and the full source are in my comment below.

*Not affiliated with SDG&E, SDCP, CEA, or any installer. Not financial or engineering advice.*

---

## 2. Variant — r/solar

> **Operator notes.** Different audience: people here already know NEM 3.0, will have opinions
> about ACC tables, and can smell an installer funnel instantly — so the "nothing for sale, not
> an installer" line has to be near the top and be true. Check the sub's self-promotion rules.
> The lock-in finding below is a genuine result from our own committed data (SDG&E's NBT25 /
> NBT26 / NBT00 export tables are byte-identical across every overlapping year) and is the
> strongest honest hook available; state it as a finding about SDG&E and do not generalise it
> to PG&E, whose tables we have not imported.

**Title:** In SDG&E territory the NEM 3.0 "lock in your vintage before rates drop" pitch appears to be worth nothing — here's the data, and what I need to finish checking it

---

I'm building an open-source, independent bill and NEM 3.0 engine for California — no company,
no leads collected, nothing for sale, not an installer and not affiliated with one. Posting a
finding and an ask.

**The finding.** ACC export rates lock for nine years by PTO vintage year, which is the basis
of the "install before the rates step down" urgency you'll hear from sales. I loaded SDG&E's
published export tables and compared them: **SDG&E's NBT25, NBT26 and NBT00 tables are
byte-identical for every overlapping year.** In SDG&E territory the nine-year lock-in
currently confers exactly zero dollar advantage, and the vintage-timing pitch is empty. That
is a statement about SDG&E only — I have not imported PG&E's per-vintage tables yet, and the
PG&E vintage story may well be different. This is the kind of thing an installer's tool has no
incentive to tell you.

A second one, same flavour: **EV-TOU-5 collapses its super-off-peak distribution charge but
not its non-bypassable charges**, so roughly 45% of the delivery charge in that window is
non-bypassable versus about 6.5% elsewhere. Any calculator netting exports against the
headline rate overstates load-shifting value there by something close to 2×.

**Where I actually stand.** On PG&E the bill engine reproduces **11 of 11** real monthly
statements within $2 of the printed total, worst case 22 cents, from real hourly interval data.
On **SDG&E it has never been run against a single real bill**, even though the tariff specs,
the CCA overlays and the ACC tables are all implemented. So I won't put a payback number or a
savings figure in front of an SDG&E household until one reconciles. That gate is the whole
product; the ACC math sitting on top of an unvalidated bill engine would be a confident-looking
guess, which is the failure mode I'm trying to avoid being.

Hence two asks, both San Diego / SDG&E.

**Ask 1 — one bill, five minutes.** An SDG&E TOU bill prints kWh *and* dollars per TOU period,
so the bill by itself validates the charge stack — rate math, baseline credit, NBCs, PCIA
vintage, CCA layering — with **no interval data and therefore no load shape**. Black out name,
address and account number. You get back the engine's line-by-line reconstruction against what
you were actually billed, including wherever it's wrong.

**Ask 2 — a full validation household:** 13-month Green Button export plus three itemised
bills. **If you have solar, your export register is the single most valuable file in this
project** — the NEM 3.0 module has never seen real export intervals, only synthetic ones, and
that's the other DoD I can't close alone.

Once the reconciliation passes, that household gets the whole analysis free: solar-only,
solar+battery and battery-only payback as **distributions** over rate escalation, panel
degradation and load drift rather than a point estimate, both a greedy TOU-arbitrage dispatch
and a cvxpy LP optimum (always both, so you can see the gap between a realistic controller and
the theoretical ceiling), the non-bypassable-charge bill floor on imports, and the vintage
timing comparison. It will tell you not to buy the battery if that's what the numbers say —
there's no funnel for it to feed.

Also honest: **CCA export terms.** By default the netting excludes the CCA generation credit
per Schedule NBT, so a CCA customer's result is a lower bound until I have their actual export
terms in hand. Flagged in the output, not buried.

Source, methodology writeup, and a browser tool that parses your export locally and uploads
nothing (and shows no dollar figures, deliberately) are linked in my comment. Contact for the
asks is [CONTACT].

---

## 3. Reply / DM template — after someone volunteers

Keep it short; the long version is in this file and can be sent as a link.

> Thanks — genuinely useful either way.
>
> **If you'd rather start small:** one recent itemised SDG&E bill, name/address/account number
> blacked out, as a PDF or clear photos of every page of the electric detail. Nothing else. I
> need the statement period dates, the total, and the per-TOU-period kWh and dollars, plus a
> few identifiers listed below so I load the right tariff versions.
>
> **If you're up for the full thing:** that plus a 13-month Green Button export — instructions
> below, about ten minutes in SDG&E My Account.
>
> Before you send anything: [what we do and don't do with it — section 5]. Short version, it
> stays on my machine, it's excluded from the public repository by configuration, nothing
> identifying is ever published, and you can have it deleted by asking.
>
> Two things I want to be straight about. I can't give you a dollar figure or a savings number
> yet — the engine has never been checked against a real SDG&E bill, which is the entire reason
> I'm asking, and I'm not willing to hand out numbers from an unchecked engine. And if it turns
> out my engine can't reproduce your bill, what you'll get from me is that failure and what
> caused it. That's the honest version of the deal.
>
> — [CONTACT]

---

## 4. Intake instructions

### 4a. Bill only (Ask 1)

1. **SDG&E My Account → Billing / Bill history →** download a recent statement as PDF. Any
   month works; a **summer** month (June–October) exercises the on-peak rates hardest and is
   the more useful one if you're only sending one.
2. **Include every page of the electric detail**, not just the summary page. The identifiers in
   section 6 — climate zone, CARE, PCIA vintage, CCA name — live on the detail pages, and the
   summary page alone is not enough to reconcile anything.
3. **Redact:** name, service and mailing address, account number, and the payment-stub /
   bank-detail region. A black box drawn over them is fine; so are photos with those areas
   covered. **Do not redact or round anything numeric** — dates, kWh, rates, dollar amounts and
   the schedule name must survive exactly, or there is nothing to reconcile against.
4. **Send** as an attachment to `[CONTACT]`. Not to a file-sharing service, not to a public
   GitHub issue.
5. Tell us the **city** of the service address — just the city, or "unincorporated county".
   Not the street address. This is the only way to determine the SDCP cohort (section 6).

Photos are acceptable if downloading the PDF is a hassle. Legible beats tidy.

### 4b. Green Button interval export (Ask 2)

The portal's wording changes; these are the landmarks, not a guaranteed click-path. **If the
labels don't match what you see, describe what's on screen and we'll work it out** — do not
guess and export something different.

1. Sign in at **sdge.com** → **My Account**.
2. Find the energy-use section — typically **My Energy / Energy Use** or an energy-usage
   dashboard reached from the account overview.
3. Look for **Green Button / Download My Data**, usually a green button-shaped control or a
   "download my data" link near the usage chart.
4. Choose:
   - **Format: CSV.** Not XML, not PDF, not the "Excel" summary.
   - **Range: as far back as it will go — target 13 months.** If the portal caps a single
     download to a shorter window (a month, a quarter, a year), take consecutive chunks that
     together cover 13 months and send all of them. Overlaps are fine; gaps are not.
   - **The most granular interval offered** (15-minute if available, otherwise hourly).
5. **Do not open the CSV in Excel and re-save it.** Excel silently rewrites dates and can
   truncate the file. Send the download exactly as it arrived.

**What the file should look like.** SDG&E emits at least one shape whose header block begins
with `Name,` / `Title,CSV Export Electric Meter(s)` / `Resource,Electric` and whose data rows
are `Meter Number,Date,Start Time,Duration,Consumption,Generation,Net`. A different shape is
not a problem — it is *information*, since the parser has only ever been tested against
documentation and one public sample. Send it as-is and say what you got.

**If you have solar**, the export must include the generation/export register — that column is
the part the NEM 3.0 module has never seen. Also say whether you're on **NEM 2.0 or the Net
Billing Tariff (NEM 3.0)**, and your **PTO year**; they lead to completely different math.

**Redaction, before sending:**

- In the header block, replace the values on the `Name`, `Address` and `Account Number` rows
  with `REDACTED`. Leave the row labels in place.
- The `Meter Number` appears in the header and again in the first column of every data row.
  Blanking it is welcome but optional — a find-and-replace to `00000000` in a plain text editor
  does it in one step.
- **Change nothing else.** Do not shift dates, round consumption, delete rows, sort, or "clean
  up" the file. Any of those breaks the reconciliation and wastes the exercise. The
  `Total Usage` line in the header is a free checksum against the summed series, so an edited
  file is detectable rather than silently wrong.

The parser discards identifying fields when it reads the file regardless — the redaction is so
that the identifying fields never reach a human inbox in the first place.

6. **Also send three itemised bills**, redacted per section 4a, ideally the three covering
   periods inside the export's date range. Three is the DoD; more is better.

---

## 5. What we do and don't do with the data

Consistent with `docs/privacy.html`, with one distinction that page does not cover and that
must be stated explicitly:

> **The website's "nothing is uploaded" promise does not apply to email.** The browser tool
> genuinely uploads nothing — there is no server. **Sending a file to a human being is a
> different act**, and it is governed by what is written here, not by that page. Do not blur
> the two when recruiting; anyone who later notices the difference is right to be annoyed.

**What happens to it:**

- Files stay on a local machine. `data/`, `tests/golden_bills/raw/` and all `*.pdf` are
  excluded from the public repository by `.gitignore` — configuration, not memory.
- Nothing identifying is published. What can end up in the public repo is an **anonymised
  fixture**: bucketed kWh and dollar amounts with no name, address, account number or meter
  number, and dates shifted if the household wants. Nothing goes public without the
  household's explicit say-so, and they can see it first.
- The reconciliation result may be published as a row in the accuracy table — utility,
  schedule, period, actual $, modeled $, delta. If that is too much, say so and it stays out;
  the validation still helps.
- No accounts, no mailing list, no analytics, no sharing with anyone, no sale of anything to
  anyone. There is no third party in this pipeline.
- Deletion on request, no questions, at any time.
- Utility portal credentials are never asked for and must never be accepted. The customer
  exports their own file. If someone offers a login, refuse it.

**Say this before receiving a file, not after.**

---

## 6. What a bill must tell us

From HANDOFF.md next action 0. Each of these changes which spec loads or how much money moves;
several are things a generic calculator silently gets wrong. If a bill can't answer one, ask —
don't infer it.

| # | What we need | Why it matters | Where to look |
|---|---|---|---|
| 1 | **Rate schedule** — TOU-DR1, TOU-DR2, EV-TOU-5, TOU-DR-P, DR | Selects the spec. **TOU-DR-P is deliberately not implemented** (its RYU event adder is $1.16/kWh on event days and event-contingent, and defaulting it to zero events would be a lie). A TOU-DR-P household can't be reconciled today — say so immediately rather than after they send a file. | Usually on the electric detail page, near the top: "Your rate" / "Rate schedule". |
| 2 | **Climate zone / baseline region** — coastal, inland, mountain or desert | Sets the baseline allowance, hence the baseline credit. Wrong zone = wrong credit on every bill. The engine **raises** if territory is omitted rather than guessing. | On or adjacent to the baseline allowance line, often as a zone name or code. |
| 3 | **CARE status** (and whether it's **FERA** instead) | CARE is ~35% off and composes differently by layer — this is the crux of open decision 9. **FERA is not modelable today**: the rate schema carries only `standard` and `care`. A FERA household must be told up front that we can't reconcile their bill yet. | A discount line in the charges, e.g. "CARE discount". |
| 4 | **Bundled vs CCA** — is generation from SDG&E (EECC) or a Community Choice Aggregator? | Decides whether the bundled generation layer or a CCA overlay loads, and whether a PCIA applies at all. | Generation charges appear under a supplier's name; a CCA bill shows SDG&E delivery *and* a separate generation supplier. |
| 5 | **Which CCA** — San Diego Community Power or Clean Energy Alliance | Both are authored, and **CEA is not uniformly cheaper or dearer than SDG&E — it is seasonally opposite** (+59% summer on-peak, −56% winter off-peak), so which one wins depends on that household's shape. Also note **which product**: only SDCP's default **PowerOn** is authored; Power100 is not. | Named on the generation charges section of the bill. |
| 6 | **Which SDCP cohort** | SDCP publishes **two rate sheets by enrolment cohort** (+$0.00559/kWh for National City and the unincorporated county). It is invisible on SDCP's marketing pages and **not electable**, so the loader cannot guess — the two cohorts are separate providers in the engine. | **Not printed on the bill.** Derive from the service-address jurisdiction — ask for the **city only**, or "unincorporated county". |
| 7 | **PCIA vintage** — the year on the exit-fee line | **Moves more money than the choice of CCA does.** SDCP undercuts SDG&E in every period, but a 2018-vintage exit fee flips exactly summer super-off-peak — the battery-charging window — and a 2024 vintage flips five of six. The engine **raises if the vintage is omitted** rather than defaulting. | On the delivery charges of a CCA customer's bill: a "PCIA" or "Cost Responsibility Surcharge" line, usually with a year on it. Photograph this line specifically. |

**Also needed, and easy to forget:**

- **Statement period dates** (both ends) and the **total amount due** — the reconciliation
  target.
- **Per-TOU-period kWh *and* dollars** — the whole reason a bill alone is worth having. If the
  bill shows only a single total kWh with no TOU breakdown, say so; it is a much weaker input
  and the household should be steered to Ask 2.
- **Any California Climate Credit line** in the period. SDG&E files it semi-annually under
  Schedule GHG-ARR; it is currently modeled as an observed per-bill line, so an unexpected one
  will show up as a large clean delta.
- **Whether a minimum-bill charge appears.** The SDG&E minimum bill in the engine
  ($0.329/day, CARE $0.164) comes from a 2018 sheet that no 2026 table restates. A real bill
  where the floor binds would confirm it.
- **Solar / export:** NEM 2.0 vs NBT, and the PTO year.

---

## 7. Running the pipeline once data arrives

1. `PYTHONPATH=src python scripts/inspect_export.py FILE.csv` **before anything tries to price
   it.** It auto-detects the utility and reports interval length, coverage, gaps, DST handling
   and any export register.
2. **Expect the parser to be wrong.** `src/greenbutton/sdge.py` was written to the documented
   format and session 13 confirmed it rejects the one real SDG&E file we've seen. Budget a
   session for parser reality-checking *before* trusting any reconciliation number. If it
   refuses the file, **fix the parser, not the file.**
3. If the household is **CARE and on a CCA**, work open decision 9 first — that bill is the
   tiebreak between two conflicting SDG&E sources and the most valuable thing in the file.
4. Reconcile, then update the README table and M1's DoD. Only after it passes ±$2 may any
   dollar figure go back to that household or to anyone else in SDG&E territory.

## 8. M5 bookkeeping

The DoD is **5 delivered reports, notes on each conversation, and a written go/no-go on
charging** (price point, objections, repeat-question patterns) — so the conversations are a
deliverable, not overhead. For each contact record: which ask they came in on, what they asked
before sending anything, what confused them in the output, what they assumed the tool was for,
whether they'd pay and what for, and every objection in their own words. Append to
SESSION_NOTES.md as they happen; a summary written from memory at the end is worth much less.
