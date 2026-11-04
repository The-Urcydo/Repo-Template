---
title: Harness evals
type: meta
status: active
summary: Optional module of golden tasks that test whether roles, skills and AGENTS.md actually change agent behavior for the better.
owner_role: reviewer
---
# agents/evals/

Module `evals`. Research suggests instruction files can add cost without helping (`docs/explanation/context-budget.md`). So the harness is tested, not assumed.

## What a golden task is

A short scenario with a prompt, the behavior expected, behavior that must not happen, and how to score it. Files in `tasks/`:

| Task | Tests |
|---|---|
| `find-the-right-doc.md` | Navigation: uses the index and the ADR tool instead of guessing |
| `respect-ownership.md` | Staying in lane: hands off instead of editing another role's files |
| `handoff-roundtrip.md` | Continuity: re-verifies a stale handoff before trusting it |
| `escalation-discipline.md` | Judgment: asks the human only when required, and asks well |
| `role-skill-discovery.md` | Discovery: the reviewer finds and follows its own skill from its role bundle, and changes nothing outside the review |

## How to run an eval

Use `tools/eval_harness.py` to seed isolated throwaway sandboxes and grade the results automatically:

```
python3 tools/eval_harness.py --list
python3 tools/eval_harness.py --verify-fixtures
python3 tools/eval_harness.py --cmd "your-agent-cli --role {role} --prompt {prompt}"
```

Or run a task manually:
1. Make a clean copy of the repo (a scratch branch or worktree).
2. Start a fresh agent session. Give it the role and the task prompt only.
3. Let it finish. Compare what it did with `Expected` and `Must not` in the task.
4. Score it pass or fail, with a one-line reason. Append a row to `results/README.md`.
5. Run the same task with each agent product you use. Differences point at instructions that are unclear or unnecessary.

## When to run them

Before and after changing `AGENTS.md`, a role, a skill or a protocol. If a change does not move the results, question whether it should exist. Keep the set small and cheap; add a task whenever an agent makes a real mistake the harness should have prevented.

Cut this module with `python3 tools/remove_module.py evals`.
