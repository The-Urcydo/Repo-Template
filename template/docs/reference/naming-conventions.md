---
title: Naming conventions
type: reference
status: active
summary: File, folder, id, branch and commit naming rules used across the repo.
---
# Naming conventions

| Thing | Convention | Example |
|---|---|---|
| Files and folders | lowercase kebab-case | `how-to/cut-a-module.md` |
| Folder README | `README.md`, exact case | `docs/tutorials/README.md` |
| Work item id | `YYYY-MM-DD-kebab-slug` | `2026-11-01-add-login` |
| Work item folder | the id | `work/items/2026-11-01-add-login/` |
| Light item | the id plus `.md` | `work/items/2026-11-01-fix-typo.md` |
| ADR | `NNNN-kebab-title.md`, four digits, from `0000` | `0007-use-postgresql.md` |
| Human question id | `Q-NNNN` | `Q-0012` |
| Git branch | `item/<item-id>` | `item/2026-11-01-add-login` |
| Skill | folder equals `name`; lowercase, digits, single hyphens; unique across all skills | `agents/roles/reviewer/skills/verify-work/` or `agents/skills/write-handoff/` |
| Role | lowercase single word; folder equals `role`; charter is `ROLE.md` | `agents/roles/builder/ROLE.md` |
| Dates | ISO 8601 | `2026-11-01` |
| Commit message | imperative mood, one logical change, mention the item id | `Add login form (2026-11-01-add-login)` |

Folders starting with `_` (such as `_templates`) are excluded from the docs checks and indexes. Generated files carry `status: generated` and a banner; never edit them by hand.
