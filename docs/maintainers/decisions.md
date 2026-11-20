# Maintainer decisions

The standing rules and decisions for maintaining this repository, as they are in force now. It is not a diary:
history lives in git, pull request descriptions and the ADRs. How to do the work is in [runbook.md](runbook.md).
When a fact below can be read live, its source is named. If the source and this file disagree, the source wins:
fix this file. Pending work is in GitHub issues, not here.

Only `template/` ships to generated projects. Maintainer-only matters (Python floor policy, `ci-gate`, the
rulesets, Dependabot, merging, releases) belong here. This repository's own ADRs live in `docs/decisions/` and
never ship; a generated project writes its own in its `docs/decisions/`.

## Standing rules
`AGENTS.md` (hard rules 1 to 6) is the authority. This section adds what is enforced in GitHub.

- **Owners and agents.** Owner accounts are `nguyenquocduyloc` and `NguyenLoc231` (`.github/CODEOWNERS`).
  The organization context (`The-Urcydo/.github/AGENTS.md`) defines which accounts are agents. An agent never
  approves.
- **Ruleset `protect-main`** (id 26596185, active, no bypass actors, default branch). Read it with
  `gh api repos/The-Urcydo/Repo-Template/rulesets/26596185`. It blocks deletion and force pushes and requires a
  pull request with 1 approving review, Code Owner review, stale approvals dismissed on push, the most recent push
  approved by someone other than the pusher, and merge commits only. Required check: `ci-gate` (bound to one
  integration id, so only that app's check counts). The branch need not be up to date.
- **Repository settings.** Only merge commits are allowed (squash and rebase are off). Merged branches are deleted
  automatically. The repository is public.
- **Every PR needs an owner.** `CODEOWNERS` has a catch-all `*` line and the ruleset requires Code Owner review, so
  an owner must approve every PR, Dependabot's included.
- **Harness paths** (`AGENTS.md` rule 3): `AGENTS.md`, `CLAUDE.md`, `template/AGENTS.md.jinja`, `template/agents/`,
  `.github/CODEOWNERS`, `.github/scripts/merge_guarded.sh`, `.github/workflows/` (all workflows) and
  `.github/dependabot.yml`. An owner must approve a PR that touches them before it merges.
  - The list is written in two places that must agree: the path lines of `CODEOWNERS` and the first line of
    `AGENTS.md` rule 3. `tests/test_repo_governance.py` fails when they drift.
  - Not protected: `.github/actionlint.yaml` and `template/.github/workflows/` (tracked in #87).
- **One topic per PR**, branched from `main`, not stacked. The description uses the headings of
  `.github/pull_request_template.md`.
- **Review.** A harness PR needs the owner's approval. Any other PR first gets an independent reviewer (one that did
  not write it), then the owner's approval. The owner may waive the independent reviewer for one PR; a waiver
  never carries to another PR. If a review was not independent, the PR says so in a comment.
- **Merging.** The owner approves every PR's latest commit in person; agents never approve. An agent merges only
  through `.github/scripts/merge_guarded.sh` (ADR 0011), which checks the approval, the reviewed head and file
  list, `mergeable_state` and the checks, pins the merge commit to the reviewed head, and writes
  `Delegated-under: ADR-0011`. When the guard refuses or is unavailable, the owner merges. The delegation ends
  on 2027-02-17 unless a PR renews it; the owner revokes it by reverting or superseding the ADR.
- **Reserved to the owner.** Rulesets and repository or organization settings, tags and releases, `.github/CODEOWNERS`,
  ADRs, secrets, tokens and GitHub Apps, billing, repository visibility, licence choices, deleting repositories, and
  anything irreversible.
- **Approvals and pushes.** A push dismisses an approval: say so on the PR first. Do not commit an "owner
  confirmation" to an approved branch; put his decisions in the merge commit message instead.
- **Settings-type changes** (rulesets, repository settings, branch or tag rules) are made by the owner in the GitHub
  UI. An agent that is refused asks him; it does not look for a way around.

## Supported versions
Policy and the end-of-life table: `CONTRIBUTING.md`, section "Supported Python versions".
`tests/test_supported_versions.py` takes the floor from the lowest `python-version` in
`.github/workflows/test.yml` and checks the README (badge, Quick start, Tooling row), `CONTRIBUTING.md` and
`template/.github/workflows/check.yml` against it.

- **Floor 3.12** since v0.4.0. CI matrix: 3.12 and 3.14 required; 3.15 informational (`experimental: true`, so
  `continue-on-error`). A failing 3.15 leg leaves `ci-gate` green.
- **Runners.** This repository's three workflows pin `ubuntu-26.04`. The workflows shipped in `template/.github/`
  keep `ubuntu-latest`.
- **`ci-gate`** is a job in `test.yml` (`needs: [template]`, `if: always()`) that fails unless the whole matrix
  succeeded. The ruleset requires it instead of version-named checks, so the matrix can change without a ruleset
  edit. `EXPECTED_CI_CHECKS` in the governance test lists the unique job names `test.yml` produces
  (`template (3.12)`, `template (3.14)`, `template (3.15)`, `ci-gate`); GitHub reports **two** `template (3.12)`
  runs (newest Copier and the 9.6.0 floor), both covered by `ci-gate`. The ruleset requires only `ci-gate`.
- **Run control** (#71). `test.yml` cancels an older run when a pull request gets a newer push; runs on `main`
  always finish. The matrix job times out after 30 minutes and `ci-gate` after 5, so a hung test cannot hold a
  runner for the six-hour default. `.github/workflows/test.yml` is the source.
- **`.github/actionlint.yaml`** declares the `ubuntu-26.04` label because the pinned actionlint predates it.
  Re-check the label at every actionlint bump.
- **Pins**: actions/checkout v7.0.1, actions/setup-python v7.1.0, zizmor-action v0.8.1, zizmor 1.32.0,
  actionlint 1.7.12. Actions are pinned to full commit SHAs. The actionlint and zizmor versions and the pins in
  `template/.github/workflows/` are bumped by hand; Dependabot watches only the root workflows.
- **Dev tools.** `requirements-dev.txt` holds floors (`copier>=9.6`, `pytest>=8`, `pytest-xdist>=3.8`,
  `pyyaml>=6.0.3`) and a floor is the minimum that provably works, not the latest. `pytest-xdist` is a root-only
  dependency so the root suite runs in parallel; generated projects stay standard-library only. `copier.yml` sets
  `_min_copier_version: "9.6.0"` because 9.4.0 and 9.5.0 ignore templated `_exclude` entries, so every profile
  receives every module. CI now tests both: a second 3.12 matrix leg parses `copier>=9.6` from
  `requirements-dev.txt` and installs `copier==9.6.0`, alongside the newest-Copier leg (#86 item 1).
- **Dependabot.** The `github-actions` entry stays first, weekly and grouped, with a 7-day cooldown; a test checks
  this. The `pip` entry is weekly with `versioning-strategy: increase-if-necessary`, so a floor is raised only when
  the new version needs it. Before approving one, read it and check `template (3.12)` and the package's
  `Requires-Python`.
- **Migrations** (`migrations/*.py`) keep Python 3.9-compatible grammar: they run on the user's interpreter during
  `copier update`, which can be older than the floor.

## Releases
- Tags are annotated `vX.Y.Z`, made on the merge commit after the PRs to ship have merged. Steps: runbook.
- The ruleset `protect-release-tags` (id 27248881, tags `v*`, active, no bypass actors) forbids updating, deleting
  or force-moving a tag. There is no creation rule. A pushed tag is permanent, so keep its annotation to a summary
  line and one short paragraph. The details go in the release notes, which stay editable.
- `.github/release.yml` groups merged PRs by label (`breaking` first); a test checks the file. Label a PR
  `breaking` when a generated project must do something after `copier update`. Such a release also ships a
  migration and an upgrade test (ADR 0008).
- Raising the Python floor or the Copier floor is a breaking change and goes in the release notes of the minor that
  does it. Release history lives in the GitHub releases and git tags; this file records the rules, not the latest
  version.

## Decisions in force
| Date | Decision | Reason |
|---|---|---|
| 2026-11-04 | Evals stay fixture-only (`eval_harness.py --verify-fixtures`); no real-agent gate in CI | No API funding |
| 2026-11-04 | Actions pinned to SHAs, workflows set `permissions`, Dependabot for `github-actions` | Supply chain |
| 2026-11-04 | `copier update` automation deferred until a generated project exists | Nothing to update yet |
| 2026-11-04 | A `stale` item is re-warned after 30 days; final | Current behavior is enough |
| 2026-11-05 | Repo public; secret scanning, push protection, Dependabot security updates, private vulnerability reporting on | Public repo hygiene |
| 2026-11-05 | Catch-all `*` in `CODEOWNERS` | The owner approves every PR |
| 2026-11-09 | ADR 0007: tiered roster (flow, advisory, optional modules), admission test; scribe conditional; researcher callable; no QA role until baselines show test quality failing | One human plus many fresh sessions |
| 2026-11-09 | Model names live only in `agents/adapters/targets.json`, never in `ROLE.md` | Roles stay tool-neutral |
| 2026-11-13 | ADR 0009: `ROLE.md` is the charter, a skill is the method; planner, builder, orchestrator and scribe have no skills | One fact, one home |
| 2026-11-14 | Python 3.9 dropped, floor 3.12 | 3.9 and 3.10 are end of life |
| 2026-11-14 | One stable `ci-gate` required instead of version-named checks | Matrix changes need no ruleset edit |
| 2026-11-16 | ADR 0010: this repository's ADRs and design docs no longer ship; the template keeps `docs/decisions/README.md` and the ADR template, so a project's first ADR is 0000 | Agents deleted shipped ADRs, and `copier update` collided on numbers |
| 2026-11-16 | Copier floor 9.6.0; v0.5.0 is a breaking minor | 9.4.0 and 9.5.0 silently ignore templated `_exclude` entries, so cut modules still ship |
| 2026-11-16 | The 84 `EvalHarnessTests` live in `tools/tests/test_eval_harness.py`, an `evals` module path (#69) | A project without `evals` carried about 67 KB of tests for a module it cut |
| 2026-11-20 | Supersedes the #69 row: generated projects no longer ship `tools/tests` in any profile. The two test files live at the template root in `tool-tests/`, the root suite copies them into a generated project before its one canonical run, and `copier update` removes the shipped copies while keeping a project's own test under `tools/tests/` (#4b) | Every clone paid ~70s for tests that belonged to the template, not to the project; projects with their own tests under `tools/tests/` will no longer run them in shipped CI |
| 2026-11-17 | Root suite: one canonical run of the shipped suite; lean/cut/update checks load it with `unittest.TestLoader` | 8.3 full passes -> 1; a lean execution adds ~29s and is deferred ([measurements](test-performance.md)) |
| 2026-11-17 | The `find-the-right-doc` fixture seeds one real ADR, and its grader fails a run that edits or deletes it (#74) | A project starts with no ADRs, so "check the existing decisions" read nothing |
| 2026-11-17 | The bootstrap steps live only in `template/docs/dev/how-to/bootstrap-from-template.md`; the `tailor-template` skill is a pointer, guarded by a root test (#76) | The after-copy message and `docs/INDEX.md` send everyone to the how-to; no other tool is known to receive the skill |
| 2026-11-18 | ADR 0011: an agent merges through `.github/scripts/merge_guarded.sh` after the owner's in-person approval of the latest commit; every other irreversible action stays with the owner | The guard checks the approval, head, files, mergeability and checks that a per-PR chat go-ahead could not |

## Delegation and status decisions
- **Step I status: waived in writing** by the owner on 2026-11-18. Routine branch and PR work uses the owner's
  `nguyenquocduyloc` token; approval stays with `NguyenLoc231`, the other owner account. The waiver is recorded in
  the private ops notes, not in this repository. Phase 1 began after ADR 0011 merged.
- **Delegation term.** Phase 1 ends 2027-02-17 and falls back to the owner unless a PR renews it. A Phase 2 (an
  agent may approve) needs its own owner-approved PR with written evidence criteria first; ADR 0011 proposes 10
  clean Phase 1 merges and a 5-PR seeded-defect trial for the owner to edit.
- **Pending work.** Open items were moved to issues: #86 (harness and CI), #87 (docs and repository hygiene),
  #88 (evals, graders and shipped tests). Add new work there, not in this file.
