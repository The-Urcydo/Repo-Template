---
title: Apps
type: meta
status: placeholder
summary: Deployable applications of the workspace; one folder per app. Replace this placeholder when the first app lands.
owner_role: builder
---
# apps/

Placeholder. One folder per deployable application (web app, API, CLI). Shared libraries go in `packages/`. Apps may depend on packages, never on each other.

Give each app subfolder its own `README.md` with a `summary` and optional `depends_on: [pkg-name]` in front matter (`check.py` enforces this boundary and lists components in `docs/dev/reference/repo-map.md`).

When the first app lands: propose its build, test and run commands for the root `AGENTS.md` (the human owns it; propose the change with `python3 tools/question.py ask`), then change this file's `status` to `active`.
