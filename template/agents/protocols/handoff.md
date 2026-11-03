---
title: Handoff protocol
type: reference
status: active
summary: The work-item state machine, what each transition requires, and the handoff.md format that carries state between sessions and roles.
owner_role: architect
---
# Handoff protocol

A session ends and a fresh one starts with no memory. The handoff file is the memory. `tools/transition.py` enforces everything below.

## States and allowed moves

| From | Can move to |
|---|---|
| `draft` | `planned`, `blocked`, `canceled` |
| `planned` | `in-progress`, `blocked`, `draft`, `canceled` |
| `in-progress` | `in-review`, `blocked`, `planned`, `canceled` |
| `in-review` | `verified`, `in-progress`, `blocked`, `draft`, `canceled` |
| `verified` | `done`, `in-progress`, `canceled` |
| `blocked` | `draft`, `planned`, `in-progress`, `canceled` |
| `stale` | `draft`, `planned`, `in-progress`, `in-review`, `canceled` |
| `done` | (final; archive it) |
| `canceled` | (final; archive it) |

`stale` is set only by `python3 tools/archive_item.py --sweep` (no update for 14 days); `check.py` re-warns after 30 days in `stale`. A stale handoff is untrusted: re-verify its claims before acting on it. `canceled` is for work that is dropped or rejected without shipping; pass `--next "<reason it was canceled>"` and archive it with `archive_item.py`.

## Rules enforced on every move

1. Every status except `done` needs `--next`: one sentence saying what the next role does (or why the item was `blocked` or `canceled`). If several roles must act, name the first here and list the rest under Current state.
2. `in-review`, `verified` and `done` need evidence in the handoff (commands run, links), not assertions.
3. `verified` and `done` need `review.md` in the item folder (full items), written by a different role than the builder. Pass `--by <role>` to `python3 tools/transition.py` to record `built_by` and `verified_by` and mechanically block self-review.
4. The next owner defaults to the role in the dispatch table in `agents/README.md`. Override with `--owner`.

## handoff.md format

Front matter (machine-read) plus a short body (human-read, under about 60 lines):

```yaml
id: 2026-11-01-add-login        # must equal the folder name
title: Add login
status: in-review
owner_role: reviewer            # who must act next
next_action: Verify criteria 1-4 against branch item/2026-11-01-add-login
do_not: [re-open ADR-0007, touch infra/]
evidence: [python3 tools/check.py, python3 -m unittest]
created: 2026-11-01
updated: 2026-11-02
```

Body sections: **Current state** (one paragraph), **Decisions made** (so nobody re-litigates), **Dead ends already tried**. It is current state, not a diary; history lives in git. `do_not` binds the next role: replace it with your own list when you hand on.

## Who writes what

`handoff.md` is the one item file every role edits: whoever holds the item keeps its body current by hand and changes its front matter through `transition.py`. Every other item file belongs to the roles that list it in `item_files`.

To change only the next step, owner or evidence without moving the status: `python3 tools/transition.py <id> --next "..." [--owner ROLE] [--evidence "..."]` (or pass the current status name).

## Asking another role for a change

Need a file you do not own changed? If it belongs to the same work, name the owner and the change in this item's handoff. If it does not, create a light item for the owner: `python3 tools/new_item.py <slug> --light --status planned --owner <role>`.

## Light items

A task under about an hour can be a single file, `work/items/<id>.md`, with the same front matter and a short body. It skips `review.md` but not the evidence rule. Create one with `python3 tools/new_item.py <slug> --light`.

## Starting a session

1. Read `AGENTS.md`, then find your item on `work/ACTIVE.md`.
2. Read its `handoff.md`. Respect `do_not`. If `status` is `stale`, re-verify before trusting it.
3. Do the `next_action`. Update the handoff as you go; move the status when done.
