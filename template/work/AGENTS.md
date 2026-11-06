# work/ rules

- This folder is volatile state, not knowledge. Anything that must stay true belongs in `docs/` (promote it, then delete it here).
- Create and move work only with the tools: `new_item.py`, `transition.py`, `archive_item.py`. They enforce the lifecycle and refresh `ACTIVE.md`.
- One item, one folder: `items/<date>-<slug>/`. Each role writes only its own files there (see `agents/ROSTER.md`, column "Item files").
- `handoff.md` is the single source of truth for an item's state. Keep it under about 60 lines: current state, decisions, dead ends. Not a diary.
- Per-item scratch notes go in `items/<id>/scratch/`. They are git-ignored and invisible to the checks.
- Questions for the human go to `HUMAN.md` via `python3 tools/question.py ask`, never only into chat or a handoff (a one-line pointer in chat is fine). The exception is the human's own unclear directive while they are in the session: ask in chat at once and write the answer in the handoff (`agents/protocols/escalation.md`). Every queued question carries a recommendation, a default, and the cost of guessing wrong.
- Never edit `ACTIVE.md` by hand; it is generated.
