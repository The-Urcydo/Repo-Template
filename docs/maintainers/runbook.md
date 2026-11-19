# Maintainer runbook

How to work on this repository. The rules and decisions behind it are in [decisions.md](decisions.md); the hard
rules are in [AGENTS.md](../../AGENTS.md). Commands use `gh api` (the REST API) so they work from any shell.

## Set up and test
```
python3 -m venv .venv && . .venv/bin/activate     # Python 3.12 or newer
pip install -r requirements-dev.txt
python -m pytest tests/test_repo_governance.py -q  # under a second; run it first
python -m pytest tests -q                          # about two minutes: generates real projects
```
`pytest.ini` runs the suite with `pytest-xdist` (`-n auto`, capped at 8 workers) and limits a bare `pytest` to
`tests/`, so the shipped suite under `template/tools/tests` is not collected twice. While working on one area:
```
python -m pytest tests/test_repo_governance.py tests/test_root_*.py tests/test_supported_versions.py -q -n0  # <2s
python -m pytest tests -q -k update                # one area, still parallel
python -m pytest tests -q --lf -n0                 # the last failure, in order
python -m pytest tests -q --durations=20           # the slowest tests
```
Try a branch by hand, always with `--vcs-ref HEAD` (without it Copier builds from the newest release tag):
```
copier copy --defaults --trust --vcs-ref HEAD --data project_name=Probe . <folder outside the repo>
```
In the probe: `python3 tools/check.py --strict`, `python3 tools/sync_indexes.py --check`,
`python3 tools/sync_agents.py --check`, `python3 -m unittest discover -s tools/tests`,
`python3 tools/eval_harness.py --verify-fixtures`. Use `--data profile=full` to get every module.

## Gotchas
- **Commit before you test.** The suite and `--vcs-ref HEAD` generate from the committed `HEAD`, so uncommitted
  changes are not tested. Do not switch branch, amend or rebase while the full suite runs.
- **Keep scratch files out of the repo:** the venv, probe projects and notes live in a folder outside it.
  Optional: `PYTHONDONTWRITEBYTECODE=1` keeps `__pycache__` folders out of probe projects. They are git-ignored, so
  nothing breaks without it (checked 2026-11-15).
- **Do not trust a check that ends in a counting pipe** (`grep -c`, `wc -l`): if the first command fails it still
  prints 0. Use a command with an exit code (`git diff --quiet ... && echo ok`).
- **CI goes stale when `main` moves.** The `pull_request` run tests the merge with the `main` of that moment. For
  an approved PR, test the merged result in a throwaway worktree (merge `origin/main`, then the PR head, by full
  commit hash) instead of pushing: a push dismisses the approval.
- **`mergeable_state` reads `unknown` or null for a while** after `main` moves, and is null in the list endpoint.
  Read the single PR (`pulls/<N>`) and poll every 10 seconds, up to about 2 minutes.
- **Last-push friction.** The ruleset needs the most recent push approved by someone other than the pusher. If an
  owner pushed the last commit with one account, the other owner account must approve the same head. Find who
  pushed with `gh api 'repos/The-Urcydo/Repo-Template/activity?ref=refs/heads/<branch>&per_page=10'`; the commit
  author is only a hint.
- **A push dismisses an approval.** Say so on the PR first; a PR comment or a description edit does not dismiss it.
- **Reading Dependabot PR failures:** `gh api repos/The-Urcydo/Repo-Template/actions/jobs/<job id>/logs` shows
  the log of a failed job. A floor above the Python floor shows up as a `pip install` failure.

## Change a CI job name or the matrix
A required check cannot be renamed or removed in the PR that needs it to merge: the PR would wait for a check that
never appears. The matrix is safe to change because the ruleset requires `ci-gate`, not the matrix names.
1. Change the matrix freely; `ci-gate` keeps its name. Update `EXPECTED_CI_CHECKS` in
   `tests/test_repo_governance.py` in the same PR (it lists every name `test.yml` produces).
2. To rename `ci-gate` or add another required check: add the new job first in one PR and merge it; the owner then
   edits the ruleset in the GitHub UI; only then change or remove the old job.
3. To change the Python floor: edit the matrix, the README (badge, Quick start, Tooling row), `CONTRIBUTING.md`
   and `template/.github/workflows/check.yml` together; `tests/test_supported_versions.py` fails if one is missed.
   Release as a breaking change.

## Edit the protected paths
Adding or removing a harness path is a two-place edit in one PR, because the governance test compares them:
1. the path lines of `.github/CODEOWNERS` (a directory needs a directory line, for example `/.github/workflows/`,
   and no separate line for a file inside it);
2. the first line of `AGENTS.md` rule 3 (keep the list on that one line; do not wrap it).

The PR is a harness PR: an owner must approve its latest commit before it merges.

## Review a PR
Use a separate worktree, not your working folder.
1. Read `AGENTS.md`, then the PR description. List the files with
   `gh api repos/The-Urcydo/Repo-Template/pulls/<N>/files --jq '.[].filename'`; they must match the description.
2. Check the head out in a worktree, run the governance test and the full suite there, and, if `template/`
   changed, the probe checks above.
3. Confirm no protected path changed outside the plan, and that the description's numbers match (recount them).
4. Report what passed, what is missing and the decisions only the owner can make. Do not approve or merge.

## Review habits
Each of these found a real defect in an earlier PR.
- **Recount before you write.** Re-measure every number (files, lines, tests, sizes) before it goes into a PR body,
  commit message or note. Compare removed lines with `git diff --shortstat`: `grep -E '^-[^-]'` hides removed bullets.
- **Tests first, and watch them fail** on unchanged code for the right reason. A test that asserts something is
  absent passes trivially; say so.
- **Attack new validation with odd inputs** (list, boolean, number, empty, wrong type), and run the same input on
  untouched `main` before calling a crash yours.
- **Attack a grader** that reads a path an agent controls with an absolute path and `../`; attack one that checks a
  cited file "states the number" with a file that only contains the digits.
- **A rule must hold in the consumer too.** When `check.py` rejects an input, run the same input through the tool
  that consumes it (for example `sync_agents.py`).
- **Mutation-test new rules:** remove one at a time, expect a test to fail, and check the unmutated baseline passes
  first. A guard that generates from the committed `HEAD` cannot see a working-tree mutation: use a copy.
- **Run new tests with an optional module cut** (`remove_module.py <module> --apply`).
- **Do not state a source more strongly than it says:** re-read the sentence in the docs before it goes into an ADR,
  a test comment or a commit message.
- **Charter text has exceptions:** re-read `never`, `done_when` and `escalate_when` against the steps.

## Merge
The owner approves on GitHub. An agent then merges only through the guard (ADR 0011); when the guard refuses or
does not apply, the owner merges. Never approve for him. The guard reads the live PR, reviews and checks itself:
```
gh api --paginate repos/The-Urcydo/Repo-Template/pulls/<N>/files --jq '.[].filename' | sort > /tmp/reviewed-files.txt
.github/scripts/merge_guarded.sh <N> <reviewed head sha> /tmp/reviewed-files.txt
```
Run it from a checkout of this repository: it fetches `origin/main` and reads the owner handles from
`origin/main:.github/CODEOWNERS`, so a PR cannot add an owner and a stale checkout cannot hide a change on main. The
files file must list exactly the changed files the reviewer saw; the guard refuses a file name containing a newline
or carriage return, which a line-per-file list cannot represent. Exit codes:
- **0:** merged and verified: two parents, branch deleted, `ci-gate` green on `main`.
- **2:** refused; the `REFUSE:` line says why. Nothing was merged: the guard either refused before calling merge,
  or GitHub declined the merge. Fix the cause, get a new approval if the head moved, or leave it to the owner.
- **1:** a GitHub read or call failed. Read the PR before retrying; a failed merge call may or may not have merged.
- **3:** merged, but a post-merge check failed. Do not retry or force anything: check the branch and `main` CI by
  hand and tell the owner.

The guard checks, in order: the PR is open, not a draft and on a branch of this repository; base `main`; head equals
the reviewed commit; the changed-file list equals the reviewed list (fewer than 3000 entries, no name containing a
newline or carriage return); an owner's latest decisive review is APPROVED on that head and no owner has a current
change request; it also refuses when the approving login is the credential running the guard
(case-insensitively), while an App token whose user lookup returns `Resource not accessible by
integration` is allowed because it has no user login; `mergeable_state` is clean; and the latest run of
every check is completed success, neutral or skipped. Then it merges with `merge_method=merge`, pins `sha=<head>`, appends `Delegated-under: ADR-0011`, and
verifies the result. The guard pins the end date (2027-02-17) and refuses a delegated merge after it; the owner can audit
it from ADR 0011 and the merge history.

Without the guard, the owner merges in the UI. For the manual API path, right before merging re-read the live PR:
```
gh api repos/The-Urcydo/Repo-Template/pulls/<N> --jq '{state,base:.base.ref,head:.head.sha,mergeable_state}'
gh api --paginate repos/The-Urcydo/Repo-Template/pulls/<N>/reviews \
  --jq '.[] | {login:.user.login,state,sha:.commit_id,at:.submitted_at}'
gh api --paginate repos/The-Urcydo/Repo-Template/commits/<head>/check-runs --jq '.check_runs[] | [.name,.conclusion] | @tsv'
```
Merge only if all of this holds: the PR is open on `main`; its head is the one you reviewed and the file list is
unchanged; an owner's latest decisive review is APPROVED on that head and no owner has a current change request;
`mergeable_state` is `clean`; the latest run of every check is completed green, neutral or skipped. Then merge with a
merge commit pinned to the head, so the call fails if anything was pushed after the approval:
```
gh api -X PUT repos/The-Urcydo/Repo-Template/pulls/<N>/merge -f merge_method=merge -f sha=<head>
```
To record the owner's decisions, add `-F commit_message=@<file>`. Afterwards check that the branch was deleted
(`git ls-remote --exit-code --heads origin <branch>` exits 2) and that the `test` workflow on `main` succeeded.

## Dependabot PRs
Read the PR before approving. Check the changed file, `template (3.12)` and the package's `Requires-Python`
against the floor. To close one the owner does not want: comment why (and that `@dependabot reopen` brings it
back), then `gh api -X PATCH repos/The-Urcydo/Repo-Template/pulls/<N> -f state=closed`.

## Release
1. All PRs to ship are merged and the `test` workflow on `main` succeeded.
2. Compare the pins in `template/.github/workflows/` with `.github/workflows/` and bump by hand where they differ
   (`workflow-lint` lints both sets).
3. Tag the merge commit with a short annotation: a summary line and one paragraph. A pushed tag cannot be changed
   or deleted (ruleset `protect-release-tags`), so do not put details there.
   ```
   git tag -a vX.Y.Z -m "vX.Y.Z: short summary" -m "One short paragraph: what changed for generated projects."
   git push origin vX.Y.Z
   ```
4. Publish the GitHub release with the full notes, which stay editable. `.github/release.yml` can generate a
   draft from PR labels (`gh release create vX.Y.Z --verify-tag --generate-notes`). Put breaking changes first, name
   renamed files, and say when an update needs a migration.
5. If the floor or the CI policy changed, update `CONTRIBUTING.md` and the notes in the same release.
