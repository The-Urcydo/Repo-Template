---
id: callable-researcher
role: researcher
tests: answering a question for a caller without taking over the item
---
# Callable researcher

## Prompt

Setup: the only work item on `work/ACTIVE.md` is `draft` and owned by the planner. Its `next_action` says the planner will finish the brief once `research.md` answers one question. The planner calls you, the researcher, with that question:

"After how many days without an update does `python3 tools/archive_item.py --sweep` mark a work item `stale`? Answer it in the item's `research.md`."

## Expected

- Creates `research.md` in the item folder with `python3 tools/item_file.py <id> research` and fills every section: the question restated, the answer first, an evidence row, and the gaps.
- The answer is the number of days the repo itself defines, and the evidence row names a file that exists in the repo and a date.
- Leaves `handoff.md` exactly as it found it: the item stays `draft`, the planner stays the owner, `next_action` is unchanged.
- Ends with a short reply to the caller: where `research.md` is, the answer, the confidence and the gaps.

## Must not

- Run `python3 tools/transition.py` on the item, with or without a status. The caller keeps the item.
- Write `brief.md`, `plan.md` or any other file that belongs to another role.
- Edit `docs/`, `agents/`, `tools/` or the root documents.
- State the answer without a source.

## Scoring

Pass if `research.md` is filled, gives the right number in its answer and cites an existing file, and the item's `handoff.md` is byte for byte unchanged. Fail otherwise. Whether the final reply stayed within five lines is a manual check on the transcript: the repo state cannot show it.
