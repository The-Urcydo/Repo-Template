---
title: Add an agent role
type: how-to
status: active
summary: Create a new role (for example a data analyst or release manager), give it ownership, and regenerate the adapters.
---
# Add an agent role

Goal: a new role that agents can adopt, with clear ownership and no overlap with existing roles.

## Steps

1. Create the folder `agents/roles/<role>/` with the charter `ROLE.md` in it. Copy an existing `ROLE.md` as a starting point. Required front matter: `role` (equals the folder name), `mission`, `reads`, `never`, `done_when`, `escalate_when`. Optional: `item_files` (files in a work item this role exclusively writes) and `writes_files` (root files it exclusively writes). Also create `agents/roles/<role>/skills/.gitkeep`: skills only this role uses go there (`docs/how-to/add-a-skill.md`).
2. Give it ownership. In the `README.md` of each folder the role owns, set `owner_role: <role>` in the front matter. The nearest ancestor README wins, so a role can own a subfolder of another role's area.
3. Keep ownership exclusive. `check.py` fails if two roles claim the same item file or root file.
4. If the role should be a step in the lifecycle, update the dispatch table in `agents/README.md` and `DEFAULT_OWNER` in `tools/_lib.py` together, plus `agents/protocols/handoff.md`.
5. Regenerate and verify: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py && python3 tools/check.py`.
6. Harness changes need the human's approval. If the `evals` module is installed, add a golden task that exercises the new role and run it.

If the role only makes sense with an optional module, put its role folder (`agents/roles/<role>`) in that module's paths in `tools/modules.json` and in the `_exclude` list of `copier.yml`, so cutting the module removes the whole bundle.

## Removing a role

For an optional module role such as `security`, cut the module: `python3 tools/remove_module.py <name> --apply`. That removes the role folder and the module's other paths together.

For a lifecycle role, deleting the folder is not enough:

1. Delete `agents/roles/<role>/`.
2. Reassign or remove every `owner_role: <role>` in folder `README.md` files.
3. Remove the role from `DEFAULT_OWNER` in `tools/_lib.py`, the dispatch table in `agents/README.md`, and any mention in `agents/protocols/handoff.md`.
4. Remove references in tests, evals and docs.
5. Run `python3 tools/sync_indexes.py && python3 tools/sync_agents.py && python3 tools/check.py`.

`check.py` fails if a role folder has no `skills/` (keep `skills/.gitkeep` while it is empty) and if `DEFAULT_OWNER` names a role that does not exist.
