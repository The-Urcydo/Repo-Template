---
title: Definition of done
type: reference
status: active
summary: The checklist every work item must satisfy before it can be marked verified or done.
owner_role: architect
---
# Definition of done

An item is done only when all of these are true. The tools check the mechanical ones; roles check the rest.

## For every item

- [ ] Every acceptance criterion in `brief.md` is met, and each has evidence (a command run, a file, a link).
- [ ] `python3 tools/check.py` passes with no errors.
- [ ] The tests the project defines pass; new behavior has tests.
- [ ] The handoff is current: status, `next_action`, `evidence`, decisions and dead ends.
- [ ] Status changes used `transition.py --by <role>`, and `built_by`/`verified_by` are different roles.
- [ ] No file was changed outside the role's ownership without the owner's handoff.
- [ ] No accepted ADR was contradicted. If one had to change, a superseding ADR exists.
- [ ] The `Docs for the scribe:` routing is settled: the reviewer checked the builder's line against the diff, or a missing line sent the item to the scribe.

The builder writes the line at the end of Current state (a full item) or in the light item's `## Docs for the scribe` section. A missing line is a builder miss, not a blocked item: the reviewer sends the item to the scribe.

## For items that change behavior, or whose builder listed docs

- [ ] Affected docs are updated (the scribe's job) and `CHANGELOG.md` has a line under `[Unreleased]`.
- [ ] Generated files are in sync: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py`.

An item whose builder wrote `Docs for the scribe: none, behavior unchanged.` and whose review agreed skips the scribe: it needs no docs and no changelog line, and the orchestrator marks it `done` (`agents/protocols/handoff.md`). A light item's line in its `## Docs for the scribe` section has the same effect.

## For full items

- [ ] `review.md` exists, written by a role other than the builder, with a verdict and per-criterion evidence.
- [ ] No blocker or major finding is left open.

A light item has no `review.md`: the reviewer writes the verdict and evidence in its `## Review` section.

## Not done if

- You cannot show evidence for a claim.
- A check was skipped "because it is unrelated".
- Placeholders or `TODO` markers were introduced and not tracked in a new item.
