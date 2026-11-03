---
title: Front matter schema
type: reference
status: active
summary: The required and optional front matter keys for docs, ADRs, handoffs, roles, skills and folder READMEs.
related_code: [tools/_lib.py, tools/check.py]
---
# Front matter schema

Front matter is a small YAML subset at the top of a Markdown file between `---` lines: `key: value` scalars, inline lists `[a, b]`, and block lists (`- a`). No nesting, no multi-line values. Quote values that contain `: ` or ` #`.

## Docs (`docs/**`, except folders starting with `_`)

| Key | Required | Values |
|---|---|---|
| `title` | yes | Human title |
| `type` | yes | `tutorial` `how-to` `reference` `explanation` `decision` `index` `meta` |
| `status` | yes | `placeholder` `draft` `active` `deprecated` `generated`; ADRs also `proposed` `accepted` `rejected` `superseded` |
| `summary` | yes | One sentence, at most 240 characters; the index is built from it |
| `related_code` | no | List of repo paths the doc describes; each must exist |
| `last_verified` | no | ISO date the doc was last checked against its code; a warning fires if a related path changed after it |

In `docs/tutorials/`, `how-to/`, `reference/`, `explanation/` and `decisions/`, `type` must match the folder unless it is `index` or `meta`.

## ADRs (`docs/decisions/NNNN-title.md`)

Docs keys plus: `date` (required once `accepted`), `decision_makers`, `supersedes` (list of numbers), `superseded_by` (required when `superseded`).

## Handoff (`work/items/<id>/handoff.md` or `<id>.md`)

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Equals the folder or file name: `YYYY-MM-DD-kebab-slug` |
| `title` | yes | Human title |
| `status` | yes | `draft` `planned` `in-progress` `in-review` `verified` `done` `blocked` `stale` `canceled` |
| `owner_role` | yes | The role that must act next; must exist in `agents/roles/` |
| `next_action` | yes unless `done` | One sentence for the next role (or reason when `blocked` / `canceled`) |
| `do_not` | no | List of things to avoid |
| `evidence` | required from `in-review` on | List of commands run or links |
| `created` `updated` | yes | ISO dates |

## Role (`agents/roles/<role>.md`)

Required: `role` (equals filename), `mission`, `reads`, `never`, `done_when`, `escalate_when`. Optional: `item_files`, `writes_files`.

## Skill (`agents/skills/<name>/SKILL.md`)

Per the Agent Skills specification: `name` (1-64 chars, lowercase letters, digits and single hyphens, equals the folder), `description` (1-1024 chars, what it does and when to use it).

## Folder README (top-level folders, and any folder that owns something)

Required for top-level folders: `summary`, `owner_role`. Optional elsewhere. `owner_role` names the role that exclusively writes that folder; the nearest ancestor README wins. `status: placeholder` marks an unfilled folder.
