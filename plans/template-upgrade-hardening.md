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
| A-1 | `conflict-marker` rule in `check.py` | - | planned | judges (`tools/`, tests) |
| A-2 | `_migrations` docs-layout migration, upgrade test, ADR 0008, update how-to | - | planned (spike first) | judges; ADR needs owner acceptance |
| B | `.githooks/pre-commit` + `just hooks` | - | planned | judges (tools tests) |
| C | Shipped CI hardening (`cooldown`, `concurrency`, `timeout-minutes`, `merge_group`, workflow-lint job) | - | planned | CI files: owner approval |
| D | Ruleset JSON + repo-settings how-to | - | planned | owner dry-run of the import |
| E | `tools/template_status.py` + weekly notifier workflow | - | planned | CI file + `tools/`: owner approval |
| F | Issue forms, `.github/release.yml`, real `SECURITY.md` default | - | later | - |
| R1-R4 | Root-repo items (section 5) | - | after template batches | owner approval (harness) |

Status values: `planned`, `building`, `in-review`, `approved`, `merged`, `done`, `dropped`. Open PR #35 (security routing, by `shiniroku`) touches `commands.md`, `modules.json` and `tools/tests/test_tools.py`: branch after it merges, or merge `main` into your branch before you push.

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

- **Spike first (scratch only, log the result):** does a `before`-stage migration that moves `docs/<type>/*` to `docs/dev/<type>/` make Copier's 3-way merge line up? Open questions: (1) a `before` command runs in the project but the new template's scripts are not there yet, so it must be inline (`python3 -c`) or a one-liner; (2) whether the moves must be staged for Copier's `git write-tree`; (3) a `version: "v0.3.0"` entry fires only when the update crosses that version (`from < 0.3.0 <= to`), so it must ship in a tag after `v0.3.0`; (4) a hand-edited `README.md` hunk next to a changed link still conflicts, which only A-1 can flag. **Fallback:** an `after`-stage `tools/migrate.py` (shipped, tested) that moves leftover old-layout docs, deletes conflicted generated files and reruns both sync tools.
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

## 10. Next steps

1. Builder: A-1 (section 5), then the A-2 spike. The session that opened this PR starts there; check section 9 before taking either.
2. Reviewer: when a batch PR exists, review it against its spec here (root rule 4), comment on it and add a log line.
3. Planner: keep section 3 true; after each batch merges, mark it `merged`; when everything is `done` or `dropped`, tell the owner this PR can be closed.
