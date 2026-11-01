---
title: Work
type: meta
status: active
summary: Volatile state of the project - work items, the human decision queue, inbox and raw research. Expected to be pruned; nothing here is long-term knowledge.
owner_role: orchestrator
---
# work/

Everything here answers "what is happening now?". It is state, not knowledge: when something must outlive its work item, promote it into `docs/` and delete the original.

| Path | Purpose | Lifecycle |
|---|---|---|
| `ACTIVE.md` | Generated board of in-flight items; the orchestrator dispatches from it | Rebuilt by the tools |
| `HUMAN.md` | The single queue of decisions only the human can make | Add with `question.py ask`, clear in one sitting |
| `inbox/` | Raw requests and ideas, not yet items | Triaged into items, then deleted |
| `items/` | One folder (or one file) per unit of work | Active until `done`, then archived |
| `research/` | Raw research notes before promotion | Promote or delete |
| `archive/<year>/` | Finished items, moved not deleted | Prune freely; git has history |
| `_templates/` | Starting points for item files | Edit to taste |

Rules for this folder: `work/AGENTS.md`. State machine: `agents/protocols/handoff.md`.

## If the history gets noisy

Commit churn here can bury code history. If that happens, move `work/` to its own branch or repository; every path in the tools is relative to the repo root, so the change is a few lines in `tools/_lib.py` (see `docs/decisions/0003-keep-work-state-in-the-main-repo.md` for the trade-offs).
