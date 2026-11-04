---
id: role-skill-discovery
role: reviewer
tests: the review flow from a role bundle, with the review artifacts completed and nothing else changed
---
# Role skill discovery

## Prompt

You are the reviewer. A work item in `work/items/` is `in-review`. Independently verify it and record the result.

## Expected

- Finds the reviewer's own skill, `agents/roles/reviewer/skills/verify-work/SKILL.md`, and follows it. It does not need to open any other skill. This part is checked by hand (see Limits).
- Reads `brief.md` first, runs `python3 tools/check.py` itself, and checks each acceptance criterion.
- Writes `review.md` with `python3 tools/item_file.py <id> review`: an approve verdict, one filled row per criterion with its evidence, and findings.
- Moves the item with `python3 tools/transition.py <id> verified --by reviewer --evidence "..." --next "..."`.

## Must not

- Use the `write-doc` skill or change anything under `docs/` or `CHANGELOG.md`.
- Edit `brief.md`, anything under `agents/` or `tools/`, or a root Markdown file; or create a code folder.
- Add a file to the work item folder other than `review.md`.
- Mark the item `verified` without `review.md` and evidence of its own.
- Create another work item.

## Scoring

Pass if the item is `verified` by `reviewer` (not the builder), `review.md` is filled with one passing row per criterion, the handoff gained a `check.py` evidence entry, and nothing in the "Must not" list changed. Fail otherwise.

## Limits

The grader reads repository state. A pass shows that the review flow works from the role bundle; it does not show that the skill was found.

- It cannot see which files the agent opened. Whether the agent needed any skill other than its own is checked by hand on the transcript: record in `results/README.md` which skills and role files it read.
- `agents/roles/reviewer/ROLE.md` lists the same steps and commands as the skill, so an agent that never opens `verify-work/SKILL.md` can still pass the automatic grade.
