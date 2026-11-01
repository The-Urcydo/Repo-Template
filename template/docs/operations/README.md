---
title: Operations docs
type: index
status: active
summary: Optional module with runbooks for running the system and postmortems for learning from incidents.
owner_role: builder
---
# docs/operations/

Module `operations`. For anything that runs somewhere and can break.

| Folder | Holds | Create with |
|---|---|---|
| `runbooks/` | Step-by-step procedures for operating and recovering the system (how-to style) | `python3 tools/new_doc.py runbook "Title"` |
| `postmortems/` | Blameless write-ups of incidents: what happened, why, what changes (explanation style) | `python3 tools/new_doc.py postmortem "Title"` |
| `_templates/` | The runbook and postmortem templates | edit to taste |

Every incident should end with at least one change: a fix, a check, a runbook, or an ADR.

Cut this module with `python3 tools/remove_module.py operations` for projects that are not operated (libraries, one-off scripts).
