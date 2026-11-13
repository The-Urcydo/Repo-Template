---
title: Front matter schema
type: reference
status: active
summary: The required and optional front matter keys for docs, ADRs, handoffs, roles, skills and folder READMEs.
related_code: [tools/_lib.py, tools/check.py, tools/sync_agents.py]
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
| `audience` | no | `dev` `user` `product` `ops` `security`. Overrides the audience the folder implies, so the generated index lists the doc under that audience; the file stays where it is |

In the type folders `tutorials/`, `how-to/`, `reference/` and `explanation/` (under `docs/dev/` or `docs/user/`) and in `docs/decisions/`, `type` must match the folder unless it is `index` or `meta`. A type folder directly under `docs/` is an error (`docs-layout`).

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
| `built_by` `verified_by` | yes for `verified`/`done` | Roles recorded when `--by` is passed to `transition.py`; `built_by` is set once, and `verified_by` must not equal `built_by` |
| `created` `updated` | yes | ISO dates |

## Role (`agents/roles/<role>/ROLE.md`)

Required: `role` (equals the folder name), `mission`, `reads`, `never`, `done_when`, `escalate_when`. Optional: `item_files`, `writes_files`, `access`, `use_when`.

- `access`: `full` (the default when the key is absent) or `read-only`. `read-only` means the role changes only the item files it declares in `item_files` and the files in the folders it owns (a folder's `README.md` names it as `owner_role`); it changes nothing else. It is a tool-neutral hint: an adapter may turn it into a tool limit (Claude Code adds `disallowedTools: Edit, NotebookEdit`, see `agents/adapters/README.md`). That limit is coarser than the rule (it blocks in-place edits everywhere, so a read-only role writes owned files whole) and guards against accidents, not a determined session. Any other value fails `check.py`.
- `use_when`: a short phrase that completes "Use when ...", shown in the generated subagent and Cursor rule descriptions. Leave it out for a role that is handed items: its description then says "Use when a work item's handoff owner_role is `<role>`". Set it for a role that is called and never owns an item, such as the researcher.

## Skill (`agents/roles/<role>/skills/<name>/SKILL.md` or `agents/skills/<name>/SKILL.md`)

Per the Agent Skills specification: `name` (1-64 chars, lowercase letters, digits and single hyphens, equals the folder), `description` (1-1024 chars, what it does and when to use it). A skill only one role uses lives under that role; a skill several roles use lives in `agents/skills/`. The name is unique across both places. For Claude Code, `tools/sync_agents.py` lists a role's own skills in its subagent's `skills:` line; there is nothing to set (`agents/adapters/README.md`).

## Folder README (top-level folders, workspace components, and any folder that owns something)

Required for top-level folders: `summary`, `owner_role`. Required for subfolders of `apps/` and `packages/`: `summary`. Optional elsewhere: `owner_role` (nearest ancestor README wins), `status: placeholder` (marks an unfilled folder), and `depends_on` (list of packages in `packages/` that a workspace app or package depends on; `check.py` verifies that neither apps nor packages depend on apps and that no cycles exist).
