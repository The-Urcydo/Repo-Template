---
title: Work items
type: meta
status: active
summary: One folder per unit of work holding its handoff, brief and role-owned files; created and moved only through the tools.
owner_role: orchestrator
---
# work/items/

```
<date>-<slug>/          full item
  handoff.md            state, owner, next action (the only file every role reads)
  brief.md              planner: goal and acceptance criteria
  plan.md  tasks.md     planner: approach and checklist (when needed)
  research.md           researcher
  design.md             architect
  review.md             reviewer (required before verified or done)
  security-review.md    security (when the security module is installed)
  scratch/              git-ignored working notes
<date>-<slug>.md        light item: one file, same front matter
```

Create with `python3 tools/new_item.py <slug>`, move with `python3 tools/transition.py`. Which role writes which file is in `agents/ROSTER.md`.
