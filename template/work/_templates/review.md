# Review: __TITLE__

Item `__ID__`. Written by the reviewer, who did not build it. See `agents/protocols/review.md`.

## Verdict

_approve | changes requested | reject_, with one sentence on why.

## Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | _copied from brief.md_ | _pass / fail_ | _command run and its result, or file path_ |

## Rules check

- [ ] `python3 tools/check.py` passes (run by the reviewer)
- [ ] Project tests pass (run by the reviewer)
- [ ] No accepted ADR contradicted
- [ ] No file changed outside its owner's remit
- [ ] Generated files in sync
- [ ] The builder's `Docs for the scribe:` line holds against the diff (the scribe runs unless this review routes the item to the orchestrator)

## Findings

_Ranked blocker, major, minor. Each: what, where (file and line), why it matters, recommended fix._

1. **[severity]** _..._
