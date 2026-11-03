---
title: Run your first work item
type: tutorial
status: active
summary: Walk one small work item through the full lifecycle, from creation to archive, and see the rules the tools enforce.
---
# Run your first work item

By the end you will have created a work item, moved it through every status, been stopped by the guard rails, and archived it. It takes about ten minutes and changes only files under `work/`.

You need: Python 3.9+ and a checkout of this repo.

In this tutorial you play every role in turn. In real use each step belongs to the role that `next_action` names: the planner writes the brief, the builder builds, a different role reviews.

## 1. Confirm the repo is healthy

```
python3 tools/check.py
```

You should see a line starting with `ok`. If not, fix the reported errors first.

## 2. Create the item

```
python3 tools/new_item.py hello-world --title "Say hello"
```

The tool prints the path to the new `handoff.md`, for example `work/items/2026-11-01-hello-world/handoff.md`. Use your own item id (the folder name) wherever this tutorial says `<id>`. Look at `work/ACTIVE.md`: the item is listed as `draft`, owned by the planner.

## 3. Plan it

Open `work/items/<id>/brief.md` and replace the placeholders: a goal and at least one acceptance criterion. Then move the item:

```
python3 tools/transition.py <id> planned --next "Builder: create the greeting file and verify it exists" --by planner
```

Every status change requires `--by <role>`: it records who acted and lets the tool block self-review later.

The board now shows `planned`, owned by the builder.

## 4. Build it

```
python3 tools/transition.py <id> in-progress --next "Creating the file" --by builder
```

Do the work (for this tutorial, nothing real is needed). Then ask for review:

```
python3 tools/transition.py <id> in-review --next "Reviewer: verify criterion 1" --evidence "python3 tools/check.py" --by builder
```

## 5. Hit a guard rail

Try to skip the review:

```
python3 tools/transition.py <id> done
```

The tool refuses: an item cannot go from `in-review` to `done`. The lifecycle is enforced, not advisory. Add `--by reviewer --next x` and `verified` refuses again, because no independent `review.md` exists yet.

## 6. Review it

Create the review file and fill in a verdict and the evidence per criterion:

```
python3 tools/item_file.py <id> review
```

Now sign off, as the reviewer:

```
python3 tools/transition.py <id> verified --next "Scribe: update docs and changelog" --evidence "criterion 1 checked" --by reviewer
python3 tools/transition.py <id> done --by scribe
```

## 7. Archive it

```
python3 tools/archive_item.py <id>
python3 tools/check.py
```

The item moves to `work/archive/<year>/`, disappears from the board, and the check still passes.

## What you did

You used the same six commands every agent uses. To understand why they work this way, read `docs/explanation/ownership-and-handoffs.md`. For the rules in full, see `agents/protocols/handoff.md`. To make real work, see `docs/how-to/bootstrap-from-template.md`.
