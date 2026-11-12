---
title: Tools
type: meta
status: active
summary: Standard-library Python scripts that create, move and verify everything else in the repo; the command surface for humans and agents.
owner_role: builder
---
# tools/

Plain `python3 tools/<name>.py`, no installs. Run any tool with `--help`. Command reference: `docs/dev/reference/commands.md`.

| Tool | What it does |
|---|---|
| `check.py` | Health check: front matter, links, ownership, workspace boundaries, state machine, generated-file drift. Run before every handoff |
| `sync_indexes.py` | Regenerates `docs/INDEX.md`, `work/ACTIVE.md`, `agents/ROSTER.md`, repo map, module registry |
| `sync_agents.py` | Regenerates the enabled adapters (`.claude/` and `CLAUDE.md` shims; optional Cursor, Copilot and Gemini files) from `agents/` |
| `new_item.py` | Creates a work item (full or `--light`, optionally with `--worktree`) |
| `item_file.py` | Adds a role-owned file (plan, tasks, review, research, design, security-review) to an item from its template |
| `transition.py` | Moves an item through the lifecycle, enforcing evidence, `--by` attribution and independent-review rules |
| `archive_item.py` | Archives `done` or `canceled` items; `--sweep` also flags idle ones as `stale` |
| `worktree.py` | Creates, lists and removes isolated sibling git worktrees (`../<repo>-<item-id>`) for parallel work items |
| `new_adr.py` | Creates the next numbered ADR (lock-protected) |
| `new_doc.py` | Creates a doc from its template |
| `question.py` | Adds to or answers the human decision queue |
| `template_status.py` | Says whether a newer release of the template this repo came from exists (`--check` exits 1 when behind); the weekly `template-update` workflow uses it |
| `remove_module.py` | Cuts an optional module out cleanly |
| `eval_harness.py` | Seeds throwaway sandboxes for golden tasks in `agents/evals/tasks/`, runs reference or agent commands, and grades post-conditions |
| `modules.json` | Registry of optional modules and their paths |
| `_lib.py` | Shared helpers (front matter, locks, ownership, state machine) |
| `tests/` | Unit tests: `python3 -m unittest discover -s tools/tests` |

Rules for changing tools: `tools/AGENTS.md`.
