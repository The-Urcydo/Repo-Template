---
title: Group docs by audience, then by type
type: decision
status: proposed
summary: Docs live under audience folders (dev, user) that hold the four Diataxis type folders; decisions stay shared and each optional module folder maps to one audience.
date: 2026-11-04
decision_makers: human
supersedes: []
---
# 0006: Group docs by audience, then by type

## Context and problem statement

`docs/` held five peer folders by Diataxis type next to up to four optional module folders by topic: nine to eleven siblings that mix two ways of sorting, and no place for documentation aimed at end users. How should docs be grouped so a reader finds their section by who they are first, without creating a grid of empty folders?

## Decision drivers

- Readers, human or agent, start from who they are, then from what they need
- A skeleton must not ship many empty folders
- ADR 0001 stays intact: `docs/`, `work/`, `agents/` and `tools/` keep their places
- The folder rules live in one place (`tools/`), so agents cannot drift from them

## Considered options

- Keep the type folders directly under `docs/` and only label the modules (no move)
- Audience folders that each hold all four type folders (an audience by type grid)
- One `diataxis/` group folder, with audience as metadata only
- Audience folders only where an audience exists: `dev/` and `user/` hold the type folders, modules stay beside them

## Decision outcome

Chosen option: "Audience folders only where an audience exists", because it groups by reader first and leaves nothing empty.

- `docs/dev/{tutorials,how-to,reference,explanation}` holds contributor docs, for humans and agents.
- `docs/user/` holds end-user docs. It ships as a placeholder; its type folders are created on demand by `new_doc.py --audience user`.
- `docs/decisions/` stays shared by every audience. `product`, `operations`, `release` and `security` stay optional modules, each implying one audience (product, ops, ops, security).
- An optional `audience:` front-matter key (`dev`, `user`, `product`, `ops`, `security`) lists a doc under another audience in the generated index without moving the file.
- There is no `diataxis/` folder: that level would add depth and no information.

### Consequences

- Good: the index and the file tree both lead with the reader; no empty audience folders; one rule set in `tools/`.
- Bad: paths are one level deeper (`docs/dev/how-to/...`); a project generated before this change cannot `copier update` across the move without conflicts (none exist yet); two ways of sorting still coexist (audience folders and module folders), now labeled.
- Neutral: an `audience:` key only regroups the generated index, so a doc in `docs/dev/` tagged `user` still sits in `docs/dev/`.

### Confirmation

`python3 tools/check.py` fails on a type folder directly under `docs/` (`docs-layout`), on a type that does not match its folder (`diataxis`) and on an unknown `audience:` value (`doc-audience`). The template's own tests generate every profile and layout and run `check.py --strict`.

## More information

`docs/README.md`, `docs/dev/reference/front-matter.md`.
