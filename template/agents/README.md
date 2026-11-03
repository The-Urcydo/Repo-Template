---
title: Agents
type: meta
status: active
summary: The tool-neutral agent harness (roles, protocols and skills) and the dispatch table that routes work items to roles.
owner_role: architect
---
# agents/

The harness that tells any AI agent how to work in this repo. It is plain Markdown, so agents built on Claude, DeepSeek, Codex, Cursor or anything else can follow it.

| Folder | What it is |
|---|---|
| `roles/` | One charter per role: mission, what it reads, which item files it writes, what it must never do |
| `protocols/` | The rules between roles: handoff state machine, escalation, definition of done, review, parallel work |
| `skills/` | Reusable procedures in the open Agent Skills format (`SKILL.md` per folder) |
| `adapters/` | Config for generating tool-specific files (Claude Code; optional Cursor and Copilot) from the above |
| `ROSTER.md` | Generated table of roles and what each owns |

## Dispatch table

The orchestrator reads `work/ACTIVE.md` and routes each item by status. `tools/transition.py` sets the default owner shown here; override it with `--owner`.

| Status | Meaning | Default next owner | What that role does |
|---|---|---|---|
| `draft` | Request captured, no plan yet | planner | Write `brief.md` (goal, acceptance criteria) and a plan if needed |
| `planned` | Brief and plan exist | builder | Implement; or architect first if the brief calls for a design or ADR |
| `in-progress` | Being built | builder | Build, test, keep the handoff current |
| `in-review` | Built, awaiting verification | reviewer | Verify against the acceptance criteria, write `review.md` |
| `verified` | Reviewer signed off | scribe | Update docs and `CHANGELOG.md`, then hand to orchestrator |
| `done` | Finished | orchestrator | Archive with `tools/archive_item.py` |
| `blocked` | Waiting on something | orchestrator | Resolve it, or raise a question to the human |
| `stale` | Idle too long | orchestrator | Re-triage: continue, re-plan, or drop |

Full rules for each transition: `protocols/handoff.md`.

## Working with non-Claude agents

Any agent that can read files and run shell commands can use this harness: point it at `AGENTS.md`, tell it which role it plays, and have it read `roles/<role>.md`. Claude Code additionally gets generated subagents and skills under `.claude/` (see `adapters/README.md`). Cursor and GitHub Copilot adapters can be switched on in `adapters/targets.json`; for any other tool's native format, add a target there and extend `tools/sync_agents.py`.
