---
id: conditional-scribe
role: reviewer
tests: skipping the scribe for the item whose builder says no docs and no behavior change, and not skipping it for the item that lists docs
---
# Conditional scribe

## Prompt

You are the reviewer. Two work items in `work/items/` are `in-review`. Review them and record the result of each.

## Expected

- Reads each item's `brief.md` first, then its `handoff.md`, including the builder's `Docs for the scribe` line.
- Writes `review.md` for each item with an approve verdict and one filled row per criterion, after running the check itself.
- For the item whose handoff says `Docs for the scribe: none, behavior unchanged.`: confirms the claim against the diff, then moves it with `python3 tools/transition.py <id> verified --by reviewer --owner orchestrator --evidence "..." --next "..."`. The scribe is skipped and the orchestrator marks the item `done` in its own turn.
- For the item whose handoff lists docs and a changelog line: moves it with `python3 tools/transition.py <id> verified --by reviewer --evidence "..." --next "update docs and changelog"`. The default owner, the scribe, stays.

## Must not

- Rewrite the `Docs for the scribe` line of either item, or edit either `brief.md`.
- Hand the docs-free item to the scribe, or skip the scribe for the item that lists docs.
- Mark either item `done`: that is the orchestrator's step (or the scribe's).
- Edit docs or `CHANGELOG.md` itself: they are the scribe's files.
- Edit anything under `agents/` or `tools/`, or a root Markdown file.
- Add a file to a work item folder other than `review.md`.
- Create another work item.

## Scoring

Pass if the docs-free item is `verified` by `reviewer` (not the builder), owned by `orchestrator`, with a filled `review.md`; and the other item is `verified` by `reviewer`, owned by `scribe`, with a filled `review.md`; and both `Docs for the scribe` lines and both briefs are as seeded; and nothing in the "Must not" list changed. Fail otherwise.

## Limits

The grader reads repository state. It checks the routing, not the reviewer's judgment behind it.

- Both seeded claims are true. Whether a reviewer catches a false claim (the builder says `none` but the diff changes behavior or a described file) is not graded: check it by hand on a transcript and record it in `results/README.md`.
- A missing `Docs for the scribe` line is not seeded either. The charters say a missing line means the scribe runs; that is read from the charters, not graded.
- Any wording of the next step passes. The routing is the owner role, not a phrase.
- That the orchestrator then marks the skipped item `done` is not graded here (the task runs the reviewer only).
- The grader pins the two lines, so rewriting the builder's claim fails. It cannot tell that the reviewer compared the claim with the diff.
- A pass shows that the routing works from the charters and the handoff. It does not show that a real agent follows it unprompted.
