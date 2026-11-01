---
title: Decisions
type: index
status: active
summary: Architecture decision records (MADR format), numbered and immutable once accepted; binding for every agent.
owner_role: architect
---
# docs/decisions/

One file per significant decision, named `NNNN-kebab-title.md`, in [MADR](https://adr.github.io/madr/) format.

- Create with `python3 tools/new_adr.py "Title"`. The number is allocated under a lock so parallel agents never collide.
- Statuses: `proposed`, `accepted`, `rejected`, `deprecated`, `superseded`. Only the human accepts significant ADRs.
- **Accepted ADRs are binding.** Never edit an accepted decision's outcome; write a new ADR with `--supersedes NNNN`, which marks the old one `superseded` and links both.
- Write for a reader six months from now: context, options with pros and cons, the decision and why, consequences.
- Small reversible choices do not need an ADR; note them in the work item's handoff.

How-to: `docs/how-to/write-an-adr.md`.
