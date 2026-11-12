# Coordination plan: template upgrade safety and hardening

Owner: Shinkir6u. Opened 2026-11-11 by a Claude session (plan, evidence, first builds). **This file is the shared plan and log for every agent that works on it (planner, builder, reviewer). Read section 0 first.**

## 0. How to use this PR

- **This PR is never merged.** It is a draft that carries the plan and the log. Nobody approves it, nobody merges it. The owner closes it when every batch in section 3 is `done` or `dropped`.
- **One batch = one separate PR**, branched from `main`, not stacked (root `AGENTS.md` rule 2). The batch PR links here by number. This file never lands on `main`, so batch PRs must not rely on it being there.
- **Log, do not rewrite.** Append a dated line to section 9 and update the status board in section 3, by committing to this branch (`plan/template-upgrade-hardening`). Never edit an earlier log line. If the plan is wrong, add a dated correction in section 9 and change the spec.
- **Roles.**
  - *Planner*: amends sections 3 to 5, records decisions, keeps the board true.
  - *Builder*: takes one batch, tests first, opens its PR, stops for review, logs it.
  - *Reviewer*: a session that did not write the batch PR (root rule 4). Runs the suite, checks the PR against its spec here and against its own description, reports in a comment on the batch PR, adds one log line here.
- **Do not touch** `template/agents/`, `.claude/`, `template/AGENTS.md.jinja` (owner instruction 2026-11-11: `agents/` is being worked by another agent). Root `AGENTS.md` hard rules still apply: never push to `main`, owner approval and `owner-approval/review` before any merge, merge commit pinned with `-f sha=<head>`, go-ahead recorded as a PR comment, a push after approval makes it stale.
- **Judges gate.** Any batch that changes `tools/`, existing tests, or CI files must say so in its PR description and needs the owner's specific approval. Changes under `template/.github/` are treated like harness changes (decision 8) even though the `owner-approval` check does not cover that path.
- **Token budget rule.** Generated projects load `AGENTS.md`, `docs/INDEX.md`, `agents/README.md` and `work/ACTIVE.md` at session start (about 4k tokens today). Nothing here may grow the always-loaded files. Each new doc adds one `INDEX.md` line, so ship at most 3 new docs across all batches.

## 1. Goal and definition of done

Owner's request (2026-11-11): find what the template is missing (workflow, CI/CD, tools, anything else), including things this repo has and the template does not, and add what is worth adding. Do not touch `agents/`.

Before calling any batch or the whole effort done, answer honestly: *As an ambitious owner, does it meet expectations? What would a top 0.01% maintainer do? Is it easy for agents (to think, to reason, to avoid wasting time and tokens)? Is it modern, logical, relatable, professional, and excellent for the long term?* Section 8 lists what to verify.

Escalation: stop and ask the owner before anything irreversible, high-risk or ambiguous.

## 2. Owner decisions (2026-11-11 18:45 local: "approved", all eight recommendations)

1. Scope and order: A, B, C, D, E; F later; no devcontainer.
2. Write ADR 0008: pre-1.0 releases may break layout only if they ship a migration and an upgrade test. Status stays `proposed` until the owner accepts it.
3. Ship the `v0.2.0` to `v0.3.0` docs-layout migration in the next tag (`v0.2.0` was public).
4. Shipped ruleset default: 0 required approvals plus a required `check` status, with a documented stricter variant (1 approval and code-owner review needs two accounts, or a solo owner deadlocks).
5. Third-party linters (zizmor, actionlint) in shipped CI, pinned to full SHAs looked up at build time.
6. The template-update notifier opens an issue, never a PR.
7. The pre-commit hook ships in core for all profiles and is never auto-activated.
8. `template/.github/` changes get harness-level treatment (explicit approval, judges-gate note).

## 3. Status board

| Batch | Topic | PR | Status | Gate |
|---|---|---|---|---|
| A-1 | `conflict-marker` rule in `check.py` | #39 | in-review | judges (`tools/`, tests) |
| A-2 | `_migrations` docs-layout migration, upgrade test, ADR 0008, update how-to | #40 | in-review | judges; ADR needs owner acceptance |
| B | `.githooks/pre-commit` + `just hooks` | #41 | in-review | judges (tools tests) |
| C | Shipped CI hardening (`cooldown`, `concurrency`, `timeout-minutes`, `merge_group`, workflow-lint job) | - | planned | CI files: owner approval |
| D | Ruleset JSON + repo-settings how-to | - | planned | owner dry-run of the import |
| E | `tools/template_status.py` + weekly notifier workflow | - | planned | CI file + `tools/`: owner approval |
| F | Issue forms, `.github/release.yml`, real `SECURITY.md` default | - | later | - |
| R1-R4 | Root-repo items (section 5) | - | after template batches | owner approval (harness) |

Status values: `planned`, `building`, `in-review`, `approved`, `merged`, `done`, `dropped`. PRs #35, #37 and #38 (security routing and its follow-ups) were merged on 2026-11-11 and `main` is now `e889c9f`; they touched `commands.md`, `modules.json`, `eval_harness.py`, `transition.py` and `tools/tests/test_tools.py`, so branch from the current `main` and merge it into any older batch branch before you push.

## 4. Evidence (measured 2026-11-11 on `main` `78b7a68`; reproduce before relying on it)

**Upgrade trial (the reason for batch A).** Recipe:

```
git fetch --depth=1 origin tag v0.2.0 tag v0.3.0          # tags are not in a shallow clone
copier copy --defaults --trust -q --data project_name=Old --data profile=full --vcs-ref v0.2.0 . <scratch>/old
cd <scratch>/old && git init -q && git add -A && git commit -qm init
sed -i "s#^_src_path: .*#_src_path: <absolute path of the clone>#" .copier-answers.yml   # "." cannot be updated from
# realistic local edits: fill the TODO line in AGENTS.md, append a line to README.md,
# add docs/how-to/deploy-to-staging.md and docs/explanation/why-postgres.md, run both sync tools, commit
copier update --defaults --trust --vcs-ref v0.3.0 -q      # HEAD is untagged: Copier calls it a downgrade and refuses
python3 tools/check.py --strict
```

Result today: update exits 0, then `check.py --strict` reports **19 errors** (`broken-link`, `docs-layout`, `generated-drift`, `adapter-drift`). Line-start conflict markers sit in `README.md` and `docs/INDEX.md`. The project's own docs stay in `docs/how-to/` and `docs/explanation/` and fail `docs-layout`. `check.py` has no conflict-marker rule (`grep` for `<<<<<<<` in `tools/check.py` and `tools/_lib.py` finds nothing). The existing `test_copier_update_merges_improvements_and_respects_cuts` only covers additive changes.

**Copier 9.19.1** (installed; `_min_copier_version` is 9.4.0): `_migrations` entries take `version`, `command`, `when`, `working_directory`; they run only on `update`; stage `before` runs on the project's tree before the 3-way merge, stage `after` (the default) after it; variables `_stage`, `_version_from`, `_version_to`, `_version_pep440_*`. Source: `copier/_template.py` `migration_tasks` and `copier/_main.py`. The template has no `_migrations` today.

**Speed.** In a generated full-profile project: `check.py` 0.11 s, `check.py --strict` 0.11 s, `sync_indexes.py --check` 0.06 s, `sync_agents.py --check` 0.06 s, `eval_harness.py --verify-fixtures` 1.35 s. Shipped unit tests: 177 tests, about 80 s (35 s in `EvalHarnessTests`), run on every PR by the shipped `check.yml`. Left alone on purpose.

**Session-start context** (about 4 chars per token): `AGENTS.md` 4.5 kB, `docs/INDEX.md` 7.2 kB, `agents/README.md` 2.9 kB, `work/ACTIVE.md` 0.5 kB, about 4k tokens in all.

**Linters.** `actionlint` 1.7.12 passes on all three workflows. `zizmor` 1.32.0 (`--offline`) reports only 3 medium `dependabot-cooldown` findings: root `.github/dependabot.yml` (github-actions and pip) and `template/.github/dependabot.yml`. Its auto-fix shows the exact YAML to use.

**Other facts.** `template/.github/workflows/check.yml` has no `merge_group` trigger, `concurrency` or `timeout-minutes`; `template/agents/skills/merge-work/references/github.md` line 20 tells owners to add `merge_group:` by hand when they use a merge queue. The only ruleset is `protect-main` (branch); `v*` tags are unprotected, although Copier builds projects from the latest tag. Copier preserves mode 755 on shipped files (tested). The live `protect-main` ruleset is the model for batch D: `gh api repos/The-Urcydo/Repo-Template/rulesets/26596185`.

## 5. Batch specs

### A-1: `conflict-marker` rule (`check.py`)

- **Why:** an update or an agent merge can leave `<<<<<<<` markers; today nothing says so except a human search (`update-from-template.md` step 3).
- **Change:** new rule `conflict-marker`, level `error`, message like `ERROR conflict-marker <path>:<line> unresolved merge conflict: resolve it and remove the markers`. A file fails when a line starts with `<<<<<<< ` and a later line starts with `>>>>>>> `. Do not match a bare `=======` (it is a Markdown heading underline). Ignore fenced code blocks in Markdown, so docs that show markers pass. Scan text files only (skip `SKIP_DIRS`, undecodable files, files over about 1 MB); measure the cost on a project with thousands of files and keep `check.py` near its current 0.11 s.
- **Files:** `template/tools/check.py`, `template/tools/tests/test_tools.py` (`HealthTests`), `template/docs/dev/reference/commands.md` (check-code table), `template/docs/dev/how-to/update-from-template.md` (step 3 mentions the new rule).
- **Acceptance:** a clean generated project passes; a seeded file with both markers fails with path and line; markers inside a fenced example, and a `=======` heading underline, pass; the trial in section 4 now reports `conflict-marker` for `README.md` and `docs/INDEX.md`. Tests are written first and shown failing for the right reason.
- **Gate:** judges (`tools/` and an existing test file are extended).

### A-2: migration, upgrade test, ADR 0008

- **Spike: done 2026-11-12, result GO (section 9 has the evidence). Build exactly this:**
  - `migrations/docs_layout.py` in the template repo root (not under `template/`, so it is never shipped; stdlib only, Python 3.9 grammar). It runs in the project root: moves the project's own files from `docs/{explanation,how-to,reference,tutorials}/` to `docs/dev/...` with `git mv`, skips the 19 names the old template shipped (embed the list in the script) and every file whose first 300 bytes contain `GENERATED by tools/`, never overwrites an existing target, rewrites relative Markdown links in the moved files by path rule (a target under a moved folder gets the `dev/` prefix, then the link is recomputed relative to the new location), stages everything, prints one `migrate: old -> new` line per file.
  - `copier.yml` `_migrations`: (1) `version: "v0.3.0"`, `when: '{{ _stage == "before" }}'`, `command: "{{ _copier_python }} {{ _copier_conf.src_path }}/migrations/docs_layout.py ."`; (2) and (3) the same `version` with the default (`after`) stage running `tools/sync_indexes.py` and `tools/sync_agents.py`, because `_tasks` run on the new tree before the project's diff is applied. It ships in the first tag after `v0.3.0`.
  - Known limit, state it in the how-to: a project's own edit next to a line the template changed (the README link to `update-from-template.md`) still conflicts in a 3-way merge. `check.py` now reports it as `conflict-marker` with the line.
- **Change:** `_migrations` in `copier.yml`; an upgrade test in `tests/test_template.py` that generates at the previous release tag, applies realistic local edits, updates to the current tree (tag the throwaway copy so Copier does not see a downgrade) and asserts `check.py --strict` passes and the user's docs moved. The test `pytest.skip`s when the tag is not available (shallow clone) and runs in CI once R3 lands. ADR 0008 (take the number from `main`, check open PRs), status `proposed`: what counts as breaking, that a break ships a migration plus an upgrade test, and that releases carry notes. `update-from-template.md` gets the real recovery path.
- **Test on the declared minimum:** run the migration on Copier 9.4.0 as well as the current version.
- **Gate:** judges (new test, `copier.yml`); ADR acceptance is the owner's.

### B: fast feedback hook

- **Change:** `template/.githooks/pre-commit` (`#!/bin/sh`, mode 755, `eol=lf` already enforced) runs `python3 tools/check.py` and both sync `--check` commands (about 0.3 s in total) and prints the one-line fixes. A `just hooks` recipe runs `git config core.hooksPath .githooks`; one how-to line (bootstrap or `CONTRIBUTING.md`) explains it. Never auto-activated, and `--no-verify` stays possible: CI is the enforcement.
- **Why it works in worktrees:** `core.hooksPath` is shared and `.githooks/` exists in every worktree.
- **Tests:** the file is executable after generation; in a generated git repo with the hook set, a drifted generated file blocks `git commit`, a clean tree commits. Document the hook in `tools/README.md` and `commands.md` if the existing documented-commands test requires it.
- **Gate:** judges (tests).

### C: shipped CI hardening

- **Change in `template/.github/`:** Dependabot `cooldown` (use the YAML `zizmor --fix=safe` produces on a copy; `default-days: 7`); in `check.yml` add `merge_group:`, `concurrency` (cancel superseded PR runs), `timeout-minutes`, and a separate `workflow-lint` job that runs `actionlint` and `zizmor` pinned to full SHAs. **Never invent a SHA:** look it up with `gh api` and check the tag date against the commit date. Keep `permissions: contents: read` at the top level.
- **Existing tests that must keep passing:** `test_workflows_pin_actions_and_declare_permissions` (every `uses:` a full SHA, a top-level `permissions:` with `contents: read`) and `test_dependabot_configs_are_valid_and_grouped`.
- **Gate:** CI files, owner approval.

### D: settings as code

- **Change:** `template/.github/rulesets/protect-default-branch.json` (rules `deletion`, `non_fast_forward`, `pull_request` with 0 required approvals and merge-commit only, `required_status_checks` with context `check`) and `protect-release-tags.json` (target `tag`, include `refs/tags/v*`, rules `update`, `deletion`, `non_fast_forward`); register both in `tools/modules.json` under `github`. One how-to, `docs/dev/how-to/protect-the-repo.md`, with the stricter variant (1 approval, code-owner review, last-push approval, dismiss stale reviews) and a checklist of settings no file can set: secret scanning and push protection, private vulnerability reporting, Dependabot alerts and security updates, code scanning default setup, default workflow permissions read-only, immutable releases once the project releases (generally available since 2025-10-28, repo or org setting). Verify each UI path before writing it down; mark anything unverified.
- **Not tested here:** GitHub's ruleset import. The owner does a dry run and reports.
- **Gate:** owner dry-run.

### E: template-update notifier

- **Change:** `template/tools/template_status.py` (stdlib only): read `_src_path` and `_commit` from `.copier-answers.yml`, list the source's tags with `git ls-remote --tags`, compare `vMAJOR.MINOR.PATCH` tags, print `up to date` or `behind: vX.Y.Z available`; `--check` exits 1 when behind. It handles `gh:owner/repo` and `https://github.com/...` and exits 0 with a clear note for a local or unreachable source. A `just template-status` recipe. `template/.github/workflows/template-update.yml`: weekly and `workflow_dispatch`; `permissions: contents: read` plus `issues: write`; runs the tool and opens at most one issue labelled `template-update` (create the label if missing, skip if an open one exists). It never pushes code.
- **Verify at build time:** what `.copier-answers.yml` records for a project generated from `gh:The-Urcydo/Repo-Template`.
- **Docs:** tool rows in `tools/README.md` and `commands.md` (an existing test requires both).
- **Gate:** `tools/` and a CI file: owner approval.

### F: later

Issue forms (bug, feature), `.github/release.yml` release-note categories, a real `SECURITY.md` default that points to private vulnerability reporting.

### R1-R4: root repo (not `template/`; owner-approval territory, separate PRs after the template batches)

- R1: import the tag ruleset from batch D on this repo (a setting, the owner applies it).
- R2: `cooldown` in root `.github/dependabot.yml` and actionlint plus zizmor in root CI.
- R3: `fetch-depth: 0` with tags in root `test.yml` so the upgrade test from A-2 runs in CI.
- R4: `.github/release.yml` for this template's own release notes.

## 6. Order and dependencies

A-1, A-2, B, C, D, E, in that order of value. They are independent PRs (not stacked), so merge order is flexible. Collisions to watch: A-1, B and E touch `commands.md` and `tools/tests/test_tools.py`; D and E touch `tools/modules.json`; ADR 0008 needs the next free number on `main`. A-2 and R3 depend on each other only for CI coverage, not for correctness.

## 7. Standing gotchas (from earlier sessions and this one)

- The suite generates from the committed tree: commit first, test with `--vcs-ref HEAD`. Full run: `python -m pytest tests -q`, about 4 minutes, give it a 10 minute timeout. Run `python -m pytest tests/test_repo_governance.py -q` on its own too (the PR template asks for it).
- Never run `py_compile` or import code inside `template/` (it leaves `__pycache__` and a test fails). Keep scratch files in the session scratchpad.
- A shallow clone breaks `copier copy` of a branch with commits: fetch with `--depth=50` before running the suite. Tags need `git fetch --depth=1 origin tag <tag>`.
- Fast loop for a shipped-test change: commit, generate a project (`copier copy --defaults --trust -q --data project_name=Demo --data profile=full --vcs-ref HEAD <repo> <dest>`), run the one test class inside it with `python3 -m unittest tools.tests.test_tools.<Class> -v`.
- Do not trust a check that ends in a pipe (`grep -c`, `wc -l`, `head`): redirect to a file and read `$?`.
- Before pushing a batch branch, guard: `main` on GitHub equals the `main` you tested, the head is still yours, the PR has 0 reviews. Record the owner's go-ahead as a PR comment, not a commit.
- Python 3.9 grammar must hold for everything under `template/tools/`: `ast.parse(src, feature_version=(3, 9))`.

## 8. Final self-check (do it before closing this PR)

| Question | Verify |
|---|---|
| Does an old project survive an update? | The section 4 trial ends with `check.py --strict` exit 0 and the user's docs in `docs/dev/`. |
| Easy for agents, no wasted time or tokens? | Always-loaded files unchanged in size; hook costs about 0.3 s; at most 3 new docs. |
| Modern? | Pinned linters in CI, `cooldown`, rulesets as code, immutable-release guidance. |
| Logical and relatable? | Each rule names its fix in its message; each new file is registered in `modules.json` or core on purpose. |
| Professional and long term? | Upgrade policy in ADR 0008, upgrade test in CI, tags protected, notifier in place. |
| Nothing broke? | Root suite and governance tests green, generated project `check.py --strict` and both sync checks ok, `--verify-fixtures` PASS, shipped unit tests OK. |

## 9. Session log (append-only)

- 2026-11-11, Claude session (planner): audited `template/`, the shipped CI and `tools/`; ran the upgrade trial, timings, context sizing and both linters (section 4); the owner approved the plan with all eight recommendations (section 2); opened this PR (#36, draft) as the shared plan and log. No file in the repo changed before this commit. `main` was `78b7a68`; open PR: #35 only.

- 2026-11-12, Claude session (builder, A-1): `main` had moved to `e889c9f` (#35, #37, #38 merged); none of them touched `check.py`, so the plan held as written. Built batch A-1 test-first and opened **PR #39** (4 commits). Findings worth keeping: (1) `git ls-files --cached` lists a conflicted file once per index stage, so a real `git merge` conflict was reported 3 times until the file list became a set; a regression test with a real merge now covers it. (2) My first check of the trial project printed no `conflict-marker` finding: I had copied only the new `check.py` over the v0.3.0 `_lib.py` and it crashed on import. Copy the whole `tools/` folder when you reuse the trial project. (3) Evidence: root suite 89 passed (240 s), governance 49 passed, generated project `unittest discover` 202 OK, `check.py` 0.11 s clean and 0.21 s with 5,000 extra git files; the trial project now reports `README.md:36` and `docs/INDEX.md:21`, once each. Owner decision requested in the PR: Markdown fences are skipped on purpose.
- 2026-11-12, Claude session (builder, A-2 spike): **GO.** Scratch template repo with tags `v0.2.0` and `v0.3.0` exactly as published and a `v0.3.1` made of the A-1 tree plus a migration. A realistic `v0.2.0` project (filled `AGENTS.md` line, two own docs with relative links, a README line) updated with plain `copier update --defaults --trust` to the latest tag. Before the migration: 19+ errors. With it: 2 errors, both the unavoidable hand-merge of the README line beside a changed link (flagged by A-1 with its line). A project that did not touch the README ends with `check.py --strict` exit 0, 0 unmerged files and its own `AGENTS.md` edit kept. Also checked: the same clean run on Copier **9.4.0** (the declared minimum) passes; a project already on `v0.3.0` updating to `v0.3.1` runs no migration (the gate is `from < version <= to`). What the spike taught (the spec in section 5 is corrected accordingly):
  1. The script does **not** need to be inline YAML: `{{ _copier_conf.src_path }}` renders to the template clone, so a file in the template repo root (`migrations/docs_layout.py`, not under `template/`, so it is never shipped) can be run as `{{ _copier_python }} {{ _copier_conf.src_path }}/migrations/docs_layout.py .`.
  2. `before` moves must be staged (`git mv` / `git add`): Copier runs `git write-tree` on the index right after the `before` stage.
  3. Move only files the project added itself. Skip the 19 names the old template shipped in the four folders (the new template ships them at the new paths) **and every generated file** (first 300 bytes contain `GENERATED by tools/`): my first version also moved the generated `reference/modules.md` and `repo-map.md` and caused two false conflicts.
  4. Rewrite relative Markdown links in the moved files by path rule, not by plan membership (a link to `../reference/commands.md` must become `../reference/commands.md` still, a link to `../decisions/x.md` must become `../../decisions/x.md`, and `../../README.md` must become `../../../README.md`). Verified on a doc with all four kinds of link.
  5. A `before` move alone leaves 24 `broken-link`, 4 `generated-drift` and 2 `adapter-drift`, because Copier runs `_tasks` on the new tree before it applies the project's diff, so `INDEX.md` and the adapters come back stale. Add two `after`-stage migrations that rerun `sync_indexes.py` and `sync_agents.py` (same `version: "v0.3.0"` gate; the default stage is `after`).
  6. Copier records a relative `_src_path` if you generate from a relative path: use an absolute one in tests.
  7. The `version:` entry is `"v0.3.0"` and the migration ships in the next tag after `v0.3.0` (it cannot be added to a published tag).

- 2026-11-12, Claude session (builder, A-2): built exactly the corrected spec and opened **PR #40** (3 commits from `main` `e889c9f`: tests first, then script + `_migrations`, then ADR 0008 + docs). Evidence: root suite 91 passed (230 s), governance 49 passed; the two new tests also pass on Copier 9.4.0. Deviations from the spec, all small: (1) the upgrade test builds its throwaway template repo from `git archive v0.2.0` plus the current tree tagged `v99.0.0` (no clone, so it works in a shallow checkout that has the `v0.2.0` tag; it skips when the tag is missing). (2) The script skips fenced code blocks when it rewrites links, and preserves bytes (no newline translation). (3) `OWNED` was checked equal to `git ls-tree v0.2.0` (19 names). Limits measured by hand and documented in the how-to and ADR 0008: an edit to a shipped doc at its old path (a glossary row) is silently dropped by the rename (recover from git); an own ADR linking to a moved doc gets one `broken-link`. Owner questions are in the PR (ADR acceptance, whether to extend link rewriting to non-shipped files outside the four folders, ADR number collision with a project's own 0008). The shipped tag is not cut by this PR.

- 2026-11-12, Claude session (builder, B): opened **PR #41** (`feat/pre-commit-hook`, from `main` `e889c9f`). Hook measured at 0.24 s; works in a second worktree (hand-checked). Finding: the root test runner exports `REPO_ROOT`, the tools honour it, so a hook run by git inside the shipped test checked the original project, and the drift test failed in the full run while passing alone; the shipped test now drops `REPO_ROOT` from the hook's environment. Lesson for C, D, E: any shipped test that spawns a process which runs the tools must not inherit `REPO_ROOT`. Root suite 91 passed (242 s), governance 49. I wrote the tests first but did not run them red (stated in the PR).

## 10. Next steps

1. Builder: C next (own branch from `main`), then D, E in order. Check section 9 and the board before taking a batch.
2. Reviewer: PR #41 (B): enable the hook in a generated repo, try a drifted commit, a clean commit, `--no-verify`, a second worktree. PR #40 (A-2) is waiting for an independent review too: generate at `v0.2.0` by hand, update, confirm the migration output and `check.py --strict`, try Copier 9.4.0. PR #39 (A-1) is waiting for an independent review against its spec in section 5 (root rule 4): run the root suite, generate a full-profile project from the branch and run its checks, try a real conflict, and comment on the PR. Then add a log line here.
3. Planner: keep section 3 true; after each batch merges, mark it `merged`; when everything is `done` or `dropped`, tell the owner this PR can be closed.
