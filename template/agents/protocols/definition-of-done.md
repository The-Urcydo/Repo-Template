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

## For items that change behavior

- [ ] Affected docs are updated (the scribe's job) and `CHANGELOG.md` has a line under `[Unreleased]`.
- [ ] Generated files are in sync: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py`.

## For full items

- [ ] `review.md` exists, written by a role other than the builder, with a verdict and per-criterion evidence.
- [ ] No blocker or major finding is left open.

## Not done if

- You cannot show evidence for a claim.
- A check was skipped "because it is unrelated".
- Placeholders or `TODO` markers were introduced and not tracked in a new item.
