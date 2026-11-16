---
title: Ship no decision records to generated projects
type: decision
status: accepted
summary: This repository's ADRs live at the root and never ship; a generated project starts with an empty decisions folder and writes its own ADRs from 0000.
date: 2026-11-16
decision_makers: human
supersedes: []
---
# 0010: Ship no decision records to generated projects

## Context and problem statement

The template shipped ADRs 0000-0009 in `docs/decisions/`. They record how this repository is maintained, yet a generated project received them as if they were its own. Three failures followed:

- Agents read the shipped records as binding, deleted them when they did not apply, or treated a maintainer rule as the project's.
- A project that wrote an ADR took the next shipped number. On `copier update`, Copier merged the old and new template trees, and the project's number collided with a record added upstream.
- Rules that only make sense for this repository, such as ADR 0008 (ship a migration and an upgrade test with every breaking release), reached projects that cannot follow them.

Which decision records should a generated project receive?

## Decision drivers

- A project's decisions are its own; this repository's decisions bind only this repository.
- `tools/new_adr.py` needs a decisions folder and the MADR template, not records.
- `copier update` must not collide with a project's ADR numbers.
- This repository's history must remain readable and numbered.

## Considered options

- Keep shipping the records and tell projects to ignore them.
- Ship an index of the records but not the files.
- Ship no records; keep the folder, its README and the ADR template.

## Decision outcome

Chosen option: "Ship no records", because a generated project cannot own this repository's decisions, and an empty folder is what the tool needs.

1. ADRs 0000-0009 move to this repository's root `docs/decisions/`, with their numbers unchanged. They no longer ship.
2. `template/docs/decisions/README.md` and `template/docs/_templates/adr.md` stay, so `tools/new_adr.py` works in a project. With no numbered record, a project's first ADR is 0000. That is expected.
3. A guard in the template's test suite fails when a shipped file cites an ADR number or a `decisions/NNNN` path.

### Consequences

- Good: a project's ADR numbers are its own; no `copier update` collision; maintainer-only rules stop reaching projects.
- Bad: a project that edited a shipped ADR loses that edit silently when it updates. The file is in the project's git history and can be restored with `git show <old-commit>:docs/decisions/<file>`.
- Neutral: a new project's first ADR is 0000, and an existing project continues from its own highest number plus one; the generated indexes are rebuilt by the migration.

### Confirmation

- The template test suite asserts that no numbered ADR ships, that a fresh project's `new_adr.py` creates 0000, and that no shipped file cites an ADR number.
- An upgrade test generates a project at v0.4.0, adds the project's own ADR 0010 and edits a shipped one, then updates: the own ADR survives, the edited shipped ADR is gone without a conflict marker, `tools/check.py --strict` exits 0, and the next ADR is 0011.
- The v0.5.0 migration rebuilds `docs/INDEX.md` after the merge, satisfying ADR 0008 for this break.

## Pros and cons of the options

### Keep shipping the records and tell projects to ignore them

- Good: no change.
- Bad: agents still read them as binding; numbers still collide on update.

### Ship an index of the records but not the files

- Good: a project can find the rationale upstream.
- Bad: the links point at files the project does not have; the index still goes stale on update.

### Ship no records

- Good: each repository owns its decisions; the tool still works.
- Bad: a project that wants the rationale must read the template repository.

## More information

Accepted by the owner in chat on 2026-11-16. Related: ADR 0008, `docs/maintainers/decisions.md`. The template's own records are in this repository's `docs/decisions/`.
