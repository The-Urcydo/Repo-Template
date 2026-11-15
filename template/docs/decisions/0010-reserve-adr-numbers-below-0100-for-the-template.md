---
title: Reserve ADR numbers below 0100 for the ADRs the template ships
type: decision
status: accepted
summary: The template keeps its own ADRs in 0000-0099 and a generated project's own ADRs start at 0100, so a later template ADR can never take a number a project already used.
date: 2026-11-15
decision_makers: human
supersedes: []
---
# 0010: Reserve ADR numbers below 0100 for the ADRs the template ships

## Context and problem statement

The template ships its own ADRs into `docs/decisions/` of every generated project, and a project records its own ADRs in the same folder. `tools/new_adr.py` allocates the highest number in that folder plus one, so the first ADR a project writes is 0010 (the shipped ones end at 0009). Template releases keep adding ADRs, and the next one will also be numbered 0010.

Measured on a project generated from a template release and then updated to a release that ships its own ADR 0010, with the project's ADRs 0010 and 0011 already written:

- `copier update` exits 0 and prints no warning. Both files sit side by side, because their names differ.
- Only `tools/check.py` notices: `adr-number ... number 0010 also used by ...; renumber with the latest first`. It does not say which of the two to renumber.
- `new_adr.py --supersedes 0010` refuses, because it finds two ADRs with that number, and a reference to "ADR 0010" in the project's own text becomes ambiguous.
- The generated `docs/INDEX.md` conflicts as well, but that happens whenever both sides add an ADR, with or without equal numbers; `tools/sync_indexes.py` rebuilds it (see `docs/dev/how-to/update-from-template.md`).

Every number a project allocates is a number the template can ship later, so a project that writes ADRs and then updates will meet this again. How should the two sources of ADRs share one folder?

## Decision drivers

- A project's own ADRs are the project's: an update must not force it to renumber them by hand.
- The shipped ADRs are cited by number from other docs, tools and tests, and generated projects link to them.
- The fix should not need a migration (ADR 0008) or a change to how the tools find ADRs.
- A reader should still know from the file name which ADRs came with the template.

## Considered options

- Leave it: rely on `check.py` and on renumbering by hand.
- A prefix for shipped ADRs, such as `T-0010`.
- A separate folder for shipped ADRs.
- Reserve a block: the template uses 0000-0099 and a project starts at 0100.

## Decision outcome

Chosen option: "Reserve a block", because it removes the clash without renaming a shipped ADR or changing how ADRs are found, listed or linked.

1. **Template ADRs use 0000-0099.** A root test of the template repo fails when a shipped ADR reaches the first project number.
2. **A project's ADRs start at 0100.** `tools/new_adr.py` allocates `max(highest + 1, 0100)`, also in a folder with no ADR. A project that already wrote an ADR with a lower number is not renumbered by the tool; `check.py` reports a clash.
3. **`check.py` says whose ADR to renumber.** For a clash below 0100 it says the range is reserved for shipped ADRs and that the one you wrote goes to 0100 or higher. A clash at 0100 or above keeps the old hint.
4. No migration: files are neither moved nor renamed, so by ADR 0008 this is not a breaking change.

### Consequences

- Good: a template release can add ADRs without colliding with any project that follows the tool.
- Good: the file name tells a reader whether an ADR came with the template (below 0100) or with the project.
- Bad: numbering jumps from 0009 to 0100 in a new project.
- Bad: the template has room for 100 ADRs. Past that the boundary has to move, and a project already above it would clash again.
- Bad: a project that wrote ADRs numbered below 0100 before this rule still has to renumber them by hand.
- Neutral: the generated indexes still conflict when both sides add an ADR; the sync tools rebuild them.

### Confirmation

- A root test of the template repo reads the first project number from `tools/_lib.py` and checks that every shipped ADR is below it.
- Shipped tests check that a project's first ADRs are 0100 and 0101, also with no ADR in the folder, and that `check.py` gives the matching hint for a clash below and inside the block.

## Pros and cons of the options

### Leave it

- Good: no change.
- Bad: every project that writes ADRs and then updates across a template ADR gets a clash that nothing warns about during the update.

### A prefix for shipped ADRs

- Good: the two sets never share a number.
- Bad: ten shipped ADRs are renamed and cited from other docs, so projects need a migration (ADR 0008).
- Bad: the number pattern in `new_adr.py`, `check.py`, the supersede links and the eval harness would all change.

### A separate folder for shipped ADRs

- Good: the two sets are physically apart.
- Bad: `docs/decisions/` is the one shared decisions folder in the tools and the generated index; a second folder is a new type folder and index group.
- Bad: "ADR 0010" would still name two documents.

### Reserve a block

- Good: one constant and one line of allocation logic; nothing moves.
- Bad: numbering gaps, and a limit of 100 shipped ADRs.

## More information

Accepted by the human in a session on 2026-11-15. The measurement above came from a scratch template and project.
