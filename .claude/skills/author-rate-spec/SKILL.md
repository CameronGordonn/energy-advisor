---
name: author-rate-spec
description: Author a CANDIDATE tariff spec YAML for one (provider × utility schedule) layer, transcribed from that layer's published rate sheet. Output is never authoritative — a human diffs it against the source before it is committed. Explicit invocation only.
disable-model-invocation: true
argument-hint: <source-layout-txt> <schedule-id> <provider>
arguments: source schedule provider
allowed-tools:
  - Read
  - Edit(build/candidates/**)
model: inherit
# effort: deliberately unset — the caller passes --effort so phase D can sweep it.
---

# Author a candidate rate spec

Transcribe **one layer** of **one schedule** from **one document** into this repo's tariff
spec form.

- Source: `$source` — a `pdftotext -layout` rendering of the published rate sheet.
- Schedule: `$schedule` — the utility's own schedule id.
- Provider: `$provider` — who supplies this layer.

You are a transcriber, not an analyst. Every number you emit must be visible in that file.

## The one rule that matters

**Never supply a value the source does not state.** Not from a sibling schedule, not from
another document, not from what you know about California tariffs, not by arithmetic.

This is the only unrecoverable error here. A missing field fails loudly at load time. A
*plausible wrong rate* passes JSON Schema, passes pydantic, passes the loader, and survives
until it meets a real utility bill — by which time it is inside a dollar figure someone was
given. The schema's bounds catch a decimal shift and nothing finer; a wrong-but-ordinary rate
is invisible to every automated check in this pipeline.

So when the sheet is silent, ambiguous, or you cannot find the row: **add an entry to
`unverified`** naming the field and why. That outcome is a success. Guessing is not.

Corollaries:
- Do not derive a CARE rate from a discount percentage. Emit `care` only if the sheet prints
  it, or if the sheet states the supplier bills one rate regardless of class — say which in
  `notes`.
- Do not compute a total, a blended rate, or a rate net of anything.
- Do not carry a value forward from a previous effective date.
- If the document contradicts itself, transcribe neither value; record both in `unverified`.

## Read only the source

`Read` the file at `$source` and nothing else. Do not fetch the PDF, the utility's website, or
any other file in the repo.

The driver greps **this same text** to check your evidence spans. If you read different bytes
than it greps, every span check fails and the run teaches nothing. The `-layout` rendering is
the contract: it is the only form that keeps each rate on a row with its schedule, period and
season-column labels attached.

A sheet usually prices several schedules. Find the rows for **`$schedule`** and ignore the
rest. If `$schedule` does not appear in the document, stop and say so — do not substitute the
closest match.

## Evidence

Every rate, charge and credit carries two provenance fields, and they do different jobs.

- **`citation`** — prose, in the style of the repo's committed specs: publisher, document
  title, effective date, the named table and row, URL, retrieval date. For a human.
- **`evidence`** — `{span, locator}`. `span` is copied **character for character** from the
  source, including its internal spacing. For the driver, which asserts the span occurs
  verbatim in the file and that your number occurs inside it.

**Quote the whole `-layout` row, never the bare number.** The row is what binds a value to its
schedule, period and season. A span of `$0.55397` is true and proves nothing:

```
TOU-DR-1    On-Peak    $0.55397    $0.19791
```

That one row grounds two cells — summer and winter on-peak — and names the schedule. Some
sheets carry the season months and TOU hours inline in the same block; when they do, quote the
block and you have grounded the rate, its season and its hours together.

Never reflow, re-space, summarise, de-hyphenate or fix a typo inside a span. If the source
prints a column misaligned, quote it misaligned.

## What goes in which layer

`$provider` and the source decide this; do not mix them.

- **`delivery`** — the utility's distribution/transmission (UDC) plus non-bypassable charges,
  the fixed daily charge, the baseline allowance and credit, and any vintaged PCIA. Priced for
  bundled and unbundled customers alike, which is why PCIA-style lines carry
  `applies_to: cca` rather than living in a second copy of the spec.
- **`generation`** — the commodity only, whether utility-bundled or from a CCA. A CCA sheet
  normally prints generation net of delivery and says so in its header; if it does, do not add
  delivery components to it.

A generation layer must classify every hour **identically** to the delivery layer it rides on,
because the two price the same kWh. So transcribe the CCA's own published TOU table; if it
disagrees with the utility schedule it maps to, that disagreement is a finding for `notes`,
not something to reconcile yourself.

## Fields that have caught people out

- **`schedule_id`** — the utility's own id, transcribed: `TOU-DR1`, `E-TOU-C`, `EV-TOU-5`.
  **Never namespace it with the supplier** (`CEA-TOU-DR1` is wrong). The supplier goes in
  `provider`. A namespaced id is a string you would have to invent, and it is the one field
  with nothing to check it against.
- **`effective_date`** — the date the *sheet* says the rates take effect. Not today, not the
  retrieval date, not the date of the board resolution adopting them.
- **`month_to_season`** — all twelve months, each independently. Read the boundary off the
  sheet ("Summer June 1 – October 31") and expand it. Do not assume June–September.
- **TOU `hours`** — half-open windows on a 24-hour clock. "4 p.m. to 9 p.m." is `[16, 21]`.
  A window that wraps midnight must be split. Do not write a rule for the default period.
- **`months` on a TOU rule** — only when the sheet restricts a window to certain months, e.g.
  a super-off-peak block "in March and April". This is easy to miss and changes the bill.
- **Sign** — a credit is negative. A per-kWh credit line that you transcribe as positive turns
  a discount into a charge.
- **Zero and negative rates are legitimate in exactly one place**: `non_bypassable.components`,
  where utilities really do print `0.00000` and small negative adjustments. Transcribe them as
  printed. Anywhere else, a zero is a signal you have read the wrong column.
- **`included_in_energy_rate`** — true when the non-bypassable components are already inside
  the energy rate and are itemised only for reporting, which is how SDG&E prints them. Getting
  this wrong double-charges them.
- **Every digit.** If the sheet prints `0.11900`, emit `0.119` only because they are the same
  number — never round, never truncate, never pad.

## Products and options

A sheet often prices a default product plus opt-ups, bundles or programs. Transcribe **the
default product only** — the one a customer is enrolled in without acting — and list what you
skipped in `notes`. Defaulting anyone into a premium overstates their bill.

## Output

Two artifacts, and they must agree.

**1. The structured object.** Conforms to `.claude/skills/author-rate-spec/extraction-schema.json`.
Its field descriptions are part of your instructions; read them.

**2. A candidate YAML** at:

```
build/candidates/<source-basename-without-.layout.txt>__<schedule>__<provider>.yaml
```

Write it with `Edit`. It is the repo's spec form — the same shape as the files in
`src/tariffs/specs/` — so it carries `citation` but **not** `evidence`, which exists only for
the driver's gate. Convert `month_to_season` into `summer_months` / `winter_months`, and the
per-period energy object into the repo's `<season>_<period>` keys.

Open the YAML with a comment block covering: what this layer is, what it deliberately does not
model, anything in `unverified`, and any discrepancy you found in the source. That header is
what the human reviewer reads first.

If a required value is unverified, write the literal `UNVERIFIED` in its place. The loader
refuses such a file by design — that is the correct outcome, not a failure to work around.

## This output is a candidate

Nothing you produce goes near a customer's bill. A human diffs it against the source before it
is committed, and the reconciliation gate — real bills, real interval data, ±$2/month — is what
decides whether a spec is right. Your job is to make that diff fast and honest: correct where
you were sure, and explicitly marked where you were not.
