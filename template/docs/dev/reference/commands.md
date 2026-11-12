---
title: Command reference
type: reference
status: active
summary: Every tool in tools/ with its arguments, what it changes, and its exit behavior.
related_code: [tools/check.py, tools/new_item.py, tools/transition.py, tools/item_file.py, tools/archive_item.py, tools/new_adr.py, tools/new_doc.py, tools/question.py, tools/remove_module.py, tools/template_status.py, tools/sync_indexes.py, tools/sync_agents.py, tools/worktree.py, tools/eval_harness.py]
---
# Command reference

All tools are `python3 tools/<name>.py`, standard library only. Every tool supports `--help`. Exit code 0 is success; non-zero is failure (usage errors exit 2, check failures exit 1).

| Command | Changes | Notes |
|---|---|---|
| `check.py` | nothing | Health check. `--strict` makes warnings fail; `--json` machine output; `--stubs` lists placeholders (exit 0) |
| `sync_indexes.py` | generated indexes | Rebuilds `docs/INDEX.md`, `work/ACTIVE.md`, `agents/ROSTER.md` (roles, skills, ownership), `docs/dev/reference/repo-map.md`, `docs/dev/reference/modules.md`. `--check` only reports drift |
| `sync_agents.py` | `.claude/`, `CLAUDE.md` shims, optional `.cursor/rules/`, `.github/copilot-instructions.md` and `.gemini/settings.json`, `agents/adapters/manifest.json` | Generates the adapters enabled in `agents/adapters/targets.json` from `agents/`. `--check` only reports drift. Refuses to overwrite files it did not generate |
| `new_item.py <slug> [--title T] [--light] [--owner ROLE] [--status S] [--worktree]` | `work/items/` | Id is `<date>-<slug>`; duplicates get `-2`, `-3`. Full item creates `handoff.md` and `brief.md`; `--worktree` creates the sibling git worktree first and writes the item inside it, so commit it on the item branch |
| `item_file.py <id> <kind>` | `work/items/<id>/` | Kinds: `brief plan tasks review research design security-review`. Refuses to overwrite |
| `transition.py <id> <status> --by ROLE --next "..." [--owner ROLE] [--evidence "..."]` | the item's `handoff.md`, board | `--evidence` may repeat. `--by` is required for every status change; it records `built_by` once and `verified_by`, and blocks self-review. Leave the status out to change only next step, owner or evidence (no `--by` in that form). A `required` Security review in the brief blocks `verified` until `security-review.md` exists |
| `archive_item.py <id>` / `--sweep [--dry-run]` | `work/items/`, `work/archive/` | Only `done` or `canceled` items archive. Sweep marks active items idle for 14 days as `stale`; `check.py` re-warns after 30 days in `stale`. `verified` items are not swept |
| `worktree.py create <id> [--path DIR]` / `remove <id> [--force]` / `list` | sibling git worktrees | Creates or removes a worktree on branch `item/<item-id>`. `remove` finds custom paths by branch, and deletes the branch only when it is merged. `create` (and `new_item.py --worktree`) prints one warning, never an error, when the first worktree is created and the folder holding the clone also holds other git repos; an explicit `--path` skips it |
| `new_adr.py "Title" [--status proposed\|accepted] [--supersedes NNNN] [--decider NAME]` | `docs/decisions/` | Number allocated under a lock; `--supersedes` accepts `3`, `0003`, or `ADR-0003` |
| `new_doc.py <type> "Title" [--summary S] [--audience dev\|user]` | `docs/` | Types: `tutorial how-to reference explanation runbook postmortem` (last two need the `operations` module). The first four go to `docs/<audience>/<type folder>/`, default audience `dev`; `--audience` is refused for the last two |
| `question.py ask ...` / `answer Q-0001 "text"` / `list` | `work/HUMAN.md` | `ask` needs `--asked-by` (a known role) `--recommended --if-no-answer --cost`; optional `--options --item` |
| `template_status.py [--check]` | nothing | Reads `.copier-answers.yml` and asks the template's git remote for its newest `vX.Y.Z` tag. Prints one line (`up to date`, `behind: ...`, or `unknown: ...`); exits 0 unless `--check` and behind. A local, private or unreachable source is `unknown`, never an error |
| `remove_module.py [name] [--apply]` | module paths, `.copier-answers.yml` | Without a name lists modules; without `--apply` is a dry run |
| `eval_harness.py [--list] [--verify-fixtures] [--task ID] [--cmd "..."]` | temp sandboxes | Seeds throwaway sandboxes for golden tasks in `agents/evals/tasks/`, runs reference or external agent commands, and grades post-conditions. A task whose front matter has `needs_role: <role>` is listed only while `agents/roles/<role>/` exists |

## Git hook

`.githooks/pre-commit` runs `sync_indexes.py --check`, `sync_agents.py --check` and `check.py` and blocks the commit when one fails, printing the fix. It is off until you run `just hooks` (`git config core.hooksPath .githooks`); the setting is per clone and shared by its worktrees. `PYTHON=<interpreter>` picks another Python; with none found the hook says so and lets the commit through. `git commit --no-verify` skips it. With the `github` module, CI is the gate.

Tools that create or move things also regenerate the indexes, so `docs/INDEX.md`, `work/ACTIVE.md` and `agents/ROSTER.md` may change as a side effect.

## Check codes

`check.py` prints `LEVEL code where message`. Levels: **error** (fails), **warn** (fails with `--strict`), **info** (placeholders; never fails).

| Code | Level | Meaning |
|---|---|---|
| `front-matter` `doc-type` `doc-status` `summary-length` `diataxis` `doc-audience` `docs-layout` | error | A doc under `docs/` breaks the schema or the folder layout (see `front-matter.md`) |
| `adr-name` `adr-number` `adr-status` `adr-date` `adr-supersede` | error | An ADR breaks naming, numbering or status rules |
| `broken-link` `link-outside-repo` | error | A relative Markdown link does not resolve |
| `module-coupling` | error | A core file links into an optional module (or one module links into another) |
| `agents-md` `agents-md-size` | error | Missing root `AGENTS.md`, or over budget (root 100 lines, nested 60) |
| `role` `ownership` `folder-readme` | error | Role charter incomplete, not at `agents/roles/<role>/ROLE.md` or not matching its folder, role folder missing `skills/`, `DEFAULT_OWNER` or `owner_role` naming an unknown role, or a folder README missing |
| `workspace-readme` `workspace-boundary` `workspace-cycle` | error | A subfolder in `apps/` or `packages/` is missing a README `summary`, or violates `depends_on` rules (packages depending on apps, apps depending on apps, missing targets, or cycles) |
| `skill` | error | Skill name, folder match or description invalid, or the same skill name used twice (shared and per-role skills share one flat namespace) |
| `item` `item-id` `handoff` `self-review` | error | A work item breaks the handoff rules, or `verified_by` matches the builder (`built_by`) |
| `human-queue` | error / warn | Malformed question (error), or any open question waiting more than 7 days (warn). Only a question that may default can be answered with its `if_no_answer`; an irreversible decision or an ambiguous directive stays open until the human answers |
| `generated-drift` `adapter-drift` | error | A generated file differs from its source: run the sync tools |
| `conflict-marker` | error | A file still holds an unresolved merge conflict (an opening `<<<<<<<` line followed by a closing `>>>>>>>` line), usually left by `copier update` or a merge. Resolve it and remove the markers. Fenced code in Markdown, binary files, files over 1 MB and git-ignored files are not read |
| `module-partial` | warn | A module is partly present |
| `module-requires` | error | A module requires another module that is not installed |
| `adapters` | error | `agents/adapters/targets.json` is not valid JSON |
| `related-code` | error | A doc's `related_code` path does not exist |
| `doc-stale` `doc-size` `skill-size` `item-stale` `item-archive` `agents-md-tree` | warn | Needs attention but does not break anything |
| `placeholder` | info | Unfilled placeholder or `TODO`; fill or delete |
