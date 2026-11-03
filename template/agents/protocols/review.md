---
title: Review protocol
type: reference
status: active
summary: How the reviewer verifies a work item independently and how findings are reported and ranked.
owner_role: architect
---
# Review protocol

Independent review is the main quality gate in a repo with no human in the loop for every change.

## Independence

- The reviewer is never the role that built the item. With a single model playing both roles, use a fresh session with no memory of the build, and read the brief before the builder's summary.
- The reviewer does not fix findings. Fixing makes the reviewer a second builder and removes the second pair of eyes.

## Procedure

1. Read `brief.md`, then `handoff.md`, then the diff. Note anything the diff changes that the brief did not ask for.
2. Run the checks yourself: `python3 tools/check.py` and the project's tests.
3. For each acceptance criterion: verify it, and record the evidence. "Looks right" is not evidence.
4. Check the rules: ADRs respected, ownership respected, generated files in sync, docs updated.
5. Write `review.md` (template: `work/_templates/review.md`).

## Findings

| Severity | Meaning | Effect |
|---|---|---|
| blocker | Wrong, unsafe, or breaks a rule or ADR | Must fix before verified |
| major | Meets the letter but misses the intent, or is fragile | Must fix or be accepted by the human |
| minor | Style, naming, small improvements | Fix now or log a new item |

Each finding states: what, where (file and line), why it matters, and a recommended fix.

## Verdicts

- **approve**: move to `verified` with evidence.
- **changes requested**: move back to `in-progress` with the builder as owner and `--next "fix findings in review.md"`.
- **reject**: the approach is wrong; move to `blocked`, `draft` (to re-plan), or `canceled` (to drop it) with an explanation in `--next`.

A second review is needed after changes requested if any blocker was found.
