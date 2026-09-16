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

<!-- BODY: Cameron writes this. Prompt + schema are his. -->

TODO
