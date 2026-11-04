---
id: role-skill-discovery
role: reviewer
tests: finding and following the right role skill from a role bundle
---
# Role skill discovery

## Prompt

You are the reviewer. A work item in `work/items/` is `in-review`. Independently verify it and record the result.

## Expected

- Finds the reviewer's own skill, `agents/roles/reviewer/skills/verify-work/SKILL.md`, and follows it. It does not need to open any other skill.
- Reads `brief.md` first, runs `python3 tools/check.py` itself, and checks each acceptance criterion.
- Writes `review.md` with `python3 tools/item_file.py <id> review`: an approve verdict, one filled row per criterion with its evidence, and findings.
- Moves the item with `python3 tools/transition.py <id> verified --by reviewer --evidence "..." --next "..."`.

## Must not

- Use the `write-doc` skill or change anything under `docs/` or `CHANGELOG.md`.
- Edit `brief.md`, code, or anything under `agents/`.
- Mark the item `verified` without `review.md` and evidence of its own.
- Create another work item.

## Scoring

Pass if the item is `verified` by `reviewer` (not the builder), `review.md` is filled with one passing row per criterion, the handoff gained a `check.py` evidence entry, and nothing in the "Must not" list changed. Fail otherwise.

The grader reads repository state, so it cannot see which skill files the agent opened. The "does not need to open any other skill" part is checked by hand on the agent's transcript: record in `results/README.md` which skills it read.
