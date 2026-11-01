---
title: Add an agent role
type: how-to
status: active
summary: Create a new role (for example a data analyst or release manager), give it ownership, and regenerate the adapters.
---
# Add an agent role

Goal: a new role that agents can adopt, with clear ownership and no overlap with existing roles.

## Steps

1. Create `agents/roles/<role>.md`. Copy an existing role file as a starting point. Required front matter: `role` (equals the filename), `mission`, `reads`, `never`, `done_when`, `escalate_when`. Optional: `item_files` (files in a work item this role exclusively writes) and `writes_files` (root files it exclusively writes).
2. Give it ownership. In the `README.md` of each folder the role owns, set `owner_role: <role>` in the front matter. The nearest ancestor README wins, so a role can own a subfolder of another role's area.
3. Keep ownership exclusive. `check.py` fails if two roles claim the same item file or root file.
4. If the role should be a step in the lifecycle, update the dispatch table in `agents/README.md` and `DEFAULT_OWNER` in `tools/_lib.py` together, plus `agents/protocols/handoff.md`.
5. Regenerate and verify: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py && python3 tools/check.py`.
6. Harness changes need the human's approval. If the `evals` module is installed, add a golden task that exercises the new role and run it.

If the role only makes sense with an optional module, put its role file in that module's paths in `tools/modules.json`, so cutting the module removes the role.
