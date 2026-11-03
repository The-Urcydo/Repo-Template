---
title: Parallel work
type: how-to
status: active
summary: How several agents work at the same time without overwriting each other, using worktrees, ownership and locked tools.
owner_role: architect
---
# Parallel work

Many agents at once is the normal case. Collisions are prevented by structure, not by hoping.

## Three mechanisms

1. **One writer per path.** Folder ownership (`owner_role` in each folder README) and per-role `item_files` mean two roles never write the same file. If you need a change in a path you do not own, say so in the handoff for the owner.
2. **One worktree per agent.** Each building agent works in its own `git worktree` on its own branch (`item/<item-id>`), created in a sibling folder outside the repository root:
   ```
   python3 tools/worktree.py create <item-id>
   ```
   Or create the item and its worktree in one step with `python3 tools/new_item.py <slug> --worktree`. Agents never share a working directory.
3. **Locked shared tools.** Creating items, allocating ADR numbers, and editing the human queue go through `tools/`, which take a file lock under `work/.locks/` so two agents cannot allocate the same number or corrupt a file.

## What can run in parallel

- Items whose changes live in different folders or different files.
- Research and planning for different items.
- Review of one item while another is built.

## What must not

- Two items that edit the same code files, unless one is sequenced after the other: set the later one to `blocked` with `--next "wait for <item-id> to merge"`.
- Anything touching generated files by hand. They are rebuilt from sources; run the sync tools after merging.
- Two agents editing `AGENTS.md` or `agents/`. Harness changes are serialized through the architect and the human.

## Merging

- Merge only items that are `verified`.
- After merging, regenerate: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py`, then `python3 tools/check.py`. Generated files conflict often and are never merged by hand; regenerate them instead.
- Remove the sibling worktree when the item is `verified`, `done` or `canceled`: `python3 tools/worktree.py remove <item-id>`.
