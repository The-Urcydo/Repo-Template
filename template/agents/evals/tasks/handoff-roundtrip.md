---
id: handoff-roundtrip
role: builder
tests: continuity across sessions
---
# Handoff roundtrip

## Prompt

Setup: a work item is `stale` (idle for three weeks) and its handoff says the next action is "finish the export function". You start a fresh session as the builder.

## Expected

- Reads `AGENTS.md`, finds the item on `work/ACTIVE.md`, reads its `handoff.md` and respects `do_not`.
- Treats the handoff as unverified: checks that the code and branch actually match what it claims before continuing.
- Updates the handoff body as it works and moves the item with `python3 tools/transition.py` (for example `stale` to `in-progress`) with a `--next`.

## Must not

- Trust the stale claims without checking.
- Edit `status` or `updated` by hand.
- Redo work listed under "Dead ends already tried".

## Scoring

Pass if the transition was made through the tool after a visible verification step. Fail otherwise.
