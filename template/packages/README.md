---
title: Packages
type: meta
status: placeholder
summary: Shared libraries of the workspace, consumed by apps; one folder per package. Replace this placeholder when the first package lands.
owner_role: builder
---
# packages/

Placeholder. One folder per shared library. Packages must not depend on apps. Give each package subfolder its own `README.md` with a `summary` and optional `depends_on: [other-pkg]` in front matter so its purpose and dependency graph are checked by `check.py` and listed in `docs/reference/repo-map.md`.

When the first package lands, change this file's `status` to `active`.
