---
title: Release docs
type: index
status: active
summary: Optional module describing how the project is versioned, released and rolled back.
owner_role: builder
---
# docs/release/

Module `release`. Fill it once the project has something to ship; until then the root `CHANGELOG.md` is enough.

| Page | Holds |
|---|---|
| `release-process.md` | Versioning scheme, the release checklist, and rollback |

Record the versioning scheme as an ADR when you first release (`python3 tools/new_adr.py "Choose a versioning scheme"`). Cut this module with `python3 tools/remove_module.py release` if the project is never released.
