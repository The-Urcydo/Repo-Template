---
title: Command reference
type: reference
status: active
summary: Every tool in tools/ with its arguments, what it changes, and its exit behavior.
related_code: [tools/check.py, tools/new_item.py, tools/transition.py, tools/item_file.py, tools/archive_item.py, tools/new_adr.py, tools/new_doc.py, tools/question.py, tools/remove_module.py, tools/sync_indexes.py, tools/sync_agents.py]
---
# Command reference

All tools are `python3 tools/<name>.py`, standard library only. Every tool supports `--help`. Exit code 0 is success; non-zero is failure (usage errors exit 2, check failures exit 1).

| Command | Changes | Notes |
|---|---|---|
| `check.py` | nothing | Health check. `--strict` makes warnings fail; `--json` machine output; `--stubs` lists placeholders (exit 0) |
| `sync_indexes.py` | generated indexes | Rebuilds `docs/INDEX.md`, `work/ACTIVE.md`, `agents/ROSTER.md`, `docs/reference/repo-map.md`, `docs/reference/modules.md`. `--check` only reports drift |
| `sync_agents.py` | `.claude/`, `CLAUDE.md` shims, optional `.cursor/rules/` and `.github/copilot-instructions.md`, `agents/adapters/manifest.json` | Generates the adapters enabled in `agents/adapters/targets.json` from `agents/`. `--check` only reports drift. Refuses to overwrite files it did not generate |
| `new_item.py <slug> [--title T] [--light] [--owner ROLE] [--status S]` | `work/items/` | Id is `<date>-<slug>`; duplicates get `-2`, `-3`. Full item creates `handoff.md` and `brief.md` |
| `item_file.py <id> <kind>` | `work/items/<id>/` | Kinds: `brief plan tasks review research design security-review`. Refuses to overwrite |
| `transition.py <id> [<status>] --next "..." [--owner ROLE] [--evidence "..."]` | the item's `handoff.md`, board | `--evidence` may repeat. Leave the status out (or repeat current status) to change only next step, owner or evidence. Rules: see `agents/protocols/handoff.md` |
| `archive_item.py <id>` / `--sweep [--dry-run]` | `work/items/`, `work/archive/` | Only `done` or `canceled` items archive. Sweep also marks active items idle for 14 days as `stale` |
| `new_adr.py "Title" [--status proposed\|accepted] [--supersedes NNNN] [--decider NAME]` | `docs/decisions/` | Number allocated under a lock; `--supersedes` accepts `3`, `0003`, or `ADR-0003` |
| `new_doc.py <type> "Title" [--summary S]` | `docs/` | Types: `tutorial how-to reference explanation runbook postmortem` (last two need the `operations` module) |
| `question.py ask ...` / `answer Q-0001 "text"` / `list` | `work/HUMAN.md` | `ask` needs `--asked-by` (a known role) `--recommended --if-no-answer --cost`; optional `--options --item` |
| `remove_module.py [name] [--apply]` | module paths, `.copier-answers.yml` | Without a name lists modules; without `--apply` is a dry run |

Tools that create or move things also regenerate the indexes, so `docs/INDEX.md`, `work/ACTIVE.md` and `agents/ROSTER.md` may change as a side effect.

## Check codes

`check.py` prints `LEVEL code where message`. Levels: **error** (fails), **warn** (fails with `--strict`), **info** (placeholders; never fails).

| Code | Level | Meaning |
|---|---|---|
| `front-matter` `doc-type` `doc-status` `summary-length` `diataxis` | error | A doc under `docs/` breaks the schema (see `front-matter.md`) |
| `adr-name` `adr-number` `adr-status` `adr-date` `adr-supersede` | error | An ADR breaks naming, numbering or status rules |
| `broken-link` `link-outside-repo` | error | A relative Markdown link does not resolve |
| `module-coupling` | error | A core file links into an optional module (or one module links into another) |
| `agents-md` `agents-md-size` | error | Missing root `AGENTS.md`, or over budget (root 100 lines, nested 60) |
| `role` `ownership` `folder-readme` | error | Role charter incomplete, ownership claimed twice or by an unknown role, folder README missing |
| `skill` | error | Skill name, folder match or description invalid |
| `item` `item-id` `handoff` | error | A work item breaks the handoff rules |
| `human-queue` | error / warn | Malformed question, or one waiting more than 7 days (warn) |
| `generated-drift` `adapter-drift` | error | A generated file differs from its source: run the sync tools |
| `module-partial` | warn | A module is partly present |
| `module-requires` | error | A module requires another module that is not installed |
| `adapters` | error | `agents/adapters/targets.json` is not valid JSON |
| `related-code` | error | A doc's `related_code` path does not exist |
| `doc-stale` `doc-size` `skill-size` `item-stale` `item-archive` `agents-md-tree` | warn | Needs attention but does not break anything |
| `placeholder` | info | Unfilled placeholder or `TODO`; fill or delete |
