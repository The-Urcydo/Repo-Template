---
title: Use MADR for decision records
type: decision
status: accepted
summary: Record significant decisions as numbered Markdown ADRs in docs/decisions using the MADR template.
date: 2026-11-01
decision_makers: human
supersedes: []
---
# 0000: Use MADR for decision records

## Context and problem statement

Many agents and one human make decisions that outlive any session. Without a durable record, agents re-litigate settled choices or undo them unknowingly. What format should decision records follow?

## Decision drivers

- Plain Markdown, version-controlled, readable by any agent
- Short decisions stay short; weighty ones can carry trade-off analysis
- Sortable, discoverable file names; tooling for numbering

## Considered options

- MADR (Markdown Architectural Decision Records)
- Nygard's original ADR template
- No formal records (decisions live in chat and commit messages)

## Decision outcome

Chosen option: "MADR", because its optional sections keep small decisions small, it captures trade-offs when they matter, and it is plain Markdown with an established naming convention (`NNNN-kebab-title.md`).

### Consequences

- Good: agents can read why a choice was made and respect it; superseding is explicit and linked both ways.
- Bad: writing an ADR costs a few minutes; the architect must judge which decisions deserve one.

### Confirmation

`python3 tools/check.py` validates names, numbers, statuses and supersede links. `python3 tools/new_adr.py` allocates numbers under a lock.

## More information

MADR: https://adr.github.io/madr/. Process: `docs/dev/how-to/write-an-adr.md`.
