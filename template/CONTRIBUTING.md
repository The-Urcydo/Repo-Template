# Contributing

One workflow for humans and agents.

## The loop

1. **Intake.** A request lands in `work/inbox/` or is stated directly. The orchestrator turns it into a work item:
   `python3 tools/new_item.py <slug>`.
2. **Plan.** The planner writes `brief.md` (goal, acceptance criteria) and, if needed, `plan.md` and `tasks.md`.
3. **Build.** The builder implements on a branch named `item/<item-id>`, in small commits.
4. **Review.** A different role runs `python3 tools/check.py`, verifies each acceptance criterion, and writes `review.md`.
5. **Close.** If the builder's handoff lists docs to update or says behavior changed, the scribe updates docs and `CHANGELOG.md` and the item reaches `done`; if it says `Docs for the scribe: none, behavior unchanged.` and the review agreed, the reviewer hands the verified item to the orchestrator, who marks it `done`. The orchestrator later archives it.

Every status change goes through `python3 tools/transition.py`, which enforces the rules in
`agents/protocols/handoff.md`. Small tasks (under about an hour) use a single-file item: `new_item.py --light`.

## Git

- Branch per work item: `item/<item-id>`, created when building starts. Parallel agents each use their own `git worktree`
  (see `agents/protocols/parallel-work.md`).
- Commit messages: imperative mood, one logical change, mention the item id.
- Never commit secrets. `.env` files are ignored; keep real values out of the repo.
- Merge only after the item is `verified`.

## Before you hand off

```
python3 tools/sync_indexes.py && python3 tools/sync_agents.py
python3 tools/check.py
python3 -m unittest discover -s tools/tests    # when you changed tools/
```

## Changing the harness itself

Edits anywhere under `agents/` — roles, skills, protocols, adapters — and to `AGENTS.md` change how every agent behaves.
They need the human's approval (the human owns `AGENTS.md`; agents propose changes with `question.py ask`), and if the `evals` module is installed, a before/after run of its golden tasks.
