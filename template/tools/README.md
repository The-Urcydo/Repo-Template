---
title: Tools
type: meta
status: active
summary: Standard-library Python scripts that create, move and verify everything else in the repo; the command surface for humans and agents.
owner_role: builder
---
# tools/

Plain `python3 tools/<name>.py`, no installs. Run any tool with `--help`. Command reference: `docs/reference/commands.md`.

| Tool | What it does |
|---|---|
| `check.py` | Health check: front matter, links, ownership, state machine, generated-file drift. Run before every handoff |
| `sync_indexes.py` | Regenerates `docs/INDEX.md`, `work/ACTIVE.md`, `agents/ROSTER.md`, repo map, module registry |
| `sync_agents.py` | Regenerates `.claude/` adapters, `CLAUDE.md` shims, and optional Cursor/Copilot files from `agents/` |
| `new_item.py` | Creates a work item (full or `--light`) |
| `item_file.py` | Adds a role-owned file (plan, tasks, review, research, design, security-review) to an item from its template |
| `transition.py` | Moves an item through the lifecycle, enforcing the rules |
| `archive_item.py` | Archives `done` or `canceled` items; `--sweep` also flags idle ones as `stale` |
| `new_adr.py` | Creates the next numbered ADR (lock-protected) |
| `new_doc.py` | Creates a doc from its template |
| `question.py` | Adds to or answers the human decision queue |
| `remove_module.py` | Cuts an optional module out cleanly |
| `modules.json` | Registry of optional modules and their paths |
| `_lib.py` | Shared helpers (front matter, locks, ownership, state machine) |
| `tests/` | Unit tests: `python3 -m unittest discover -s tools/tests` |

Rules for changing tools: `tools/AGENTS.md`.
