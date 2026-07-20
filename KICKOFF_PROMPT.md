# Kickoff prompt — paste into Claude Code (Opus) for session 1

Read CLAUDE.md and ROADMAP.md in full before writing any code. We are starting milestone M0 only.

Scaffold the repository per the architecture in CLAUDE.md: package layout under src/, pytest config, ruff config, .gitignore (must exclude data/ and tests/golden_bills/raw/), and a README stub whose first section is a placeholder for the bill-reconciliation accuracy table.

Then implement, in this order, stopping for my review after each:

1. `greenbutton`: a parser for PG&E Green Button CSV exports producing a canonical interval series (pydantic model: timestamps tz-aware America/Los_Angeles, kWh per interval, interval length validated, gaps and DST transitions handled explicitly and tested). I will provide a real export; write the parser against the documented format first and we'll adjust to the file's quirks.
2. `tariffs`: the tariff spec schema (YAML, effective-dated, citation field mandatory, loader raises on any UNVERIFIED field) and the pure billing function (interval series + spec + billing period -> itemized bill). Structure specs as delivery/generation layers now, even for PG&E, so the SDG&E + CCA milestone doesn't force a refactor.
3. A reconciliation harness: given a bill's period and expected line items, print a side-by-side comparison and assert within tolerance. This becomes the golden-bill test fixture format.

Constraints, non-negotiable: never invent a rate value — leave UNVERIFIED markers for me to fill from the tariff sheet; no network calls anywhere in the tariff engine; every module lands with tests; flag any billing-mechanics decision with dollar impact (netting order, baseline allowance handling, proration at rate changes mid-period) as an explicit decision point for me instead of choosing silently.

Differentiation check, ongoing: CLAUDE.md lists the invariants that distinguish this product from SDG&E's free tool, nem3calculator.com, and installer software. If any implementation choice would make us more generic relative to those invariants, or you see an opportunity to make the product more distinctive (an output, a check, a transparency artifact competitors lack), raise it in the moment rather than deferring.

Work in small increments and keep a running SESSION_NOTES.md of decisions made and decisions pending.
