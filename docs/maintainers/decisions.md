# Maintainer decisions

The standing rules and decisions for maintaining this repository, as they are in force now. It is not a diary:
history lives in git, pull request descriptions and the ADRs. How to do the work is in [runbook.md](runbook.md).
When a fact below can be read live, its source is named. If the source and this file disagree, the source wins:
fix this file. Last verified 2026-11-16 against `main` at `34008c0`.

Only `template/` ships to generated projects. Maintainer-only matters (Python floor policy, `ci-gate`, the
rulesets, Dependabot, merging, releases) belong here. This repository's own ADRs live in `docs/decisions/` and
never ship; a generated project writes its own in its `docs/decisions/`.

## Standing rules
`AGENTS.md` (hard rules 1 to 6) is the authority. This section adds what is enforced in GitHub.

- **Owners and agents.** Owner accounts are `nguyenquocduyloc` and `NguyenLoc231` (`.github/CODEOWNERS`).
  `shiniroku` and `shinkir6u` are agent accounts. An agent never approves.
- **Ruleset `protect-main`** (id 26596185, active, no bypass actors, default branch). Read it with
  `gh api repos/The-Urcydo/Repo-Template/rulesets/26596185`. It blocks deletion and force pushes and requires a
  pull request with 1 approving review, Code Owner review, stale approvals dismissed on push, the most recent push
  approved by someone other than the pusher, and merge commits only. Required checks: `ci-gate` (bound to one
  integration id, so only that app's check counts) and `owner-approval/review`. The branch need not be up to date.
- **Repository settings.** Only merge commits are allowed (squash and rebase are off). Merged branches are deleted
  automatically. The repository is public.
- **Every PR needs an owner.** `CODEOWNERS` has a catch-all `*` line and the ruleset requires Code Owner review, so
  an owner must approve every PR, Dependabot's included.
- **Harness paths** (`AGENTS.md` rule 3): `AGENTS.md`, `CLAUDE.md`, `template/AGENTS.md.jinja`, `template/agents/`,
  `.github/CODEOWNERS`, `.github/workflows/` (all workflows) and `.github/dependabot.yml`. `owner-approval/review`
  stays red on a PR that touches them until an owner has approved its latest commit.
  - The list is written in three places that must agree: the `protected=` regex in
    `.github/workflows/owner-approval.yml`, the path lines of `CODEOWNERS`, and the first line of `AGENTS.md` rule 3.
    `tests/test_repo_governance.py` fails when they drift.
  - Not protected: `.github/actionlint.yaml` and `template/.github/workflows/` (see open items).
- **One topic per PR**, branched from `main`, not stacked. The description uses the headings of
  `.github/pull_request_template.md`.
- **Review.** A harness PR needs the owner's approval. Any other PR first gets an independent reviewer (one that did
  not write it), then the owner's approval. The owner may waive the independent reviewer for one PR; a waiver
  never carries to another PR. If a review was not independent, the PR says so in a comment.
- **Merge word.** An agent merges only when the three conditions hold (owner APPROVED on the latest commit, status
  `owner-approval/review` green, `mergeable_state` clean) and the owner has also said in the session that it may
  merge. Until the owner says otherwise, his approval on GitHub alone is not the go for an agent.
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
  `continue-on-error`) until it has been green for two weeks. A failing 3.15 leg leaves `ci-gate` green.
- **Runners.** This repository's three workflows pin `ubuntu-26.04`. The workflows shipped in `template/.github/`
  keep `ubuntu-latest`.
- **`ci-gate`** is a job in `test.yml` (`needs: [template]`, `if: always()`) that fails unless the whole matrix
  succeeded. The ruleset requires it instead of version-named checks, so the matrix can change without a ruleset
  edit. `EXPECTED_CI_CHECKS` in the governance test lists every job name `test.yml` produces
  (`template (3.12)`, `template (3.14)`, `template (3.15)`, `ci-gate`); the ruleset requires only `ci-gate`.
- **`.github/actionlint.yaml`** declares the `ubuntu-26.04` label because actionlint 1.7.12 predates it. Remove the
  entry when the pinned actionlint knows the label; re-check at every actionlint bump.
- **Pins** (checked 2026-11-14): actions/checkout v7.0.1, actions/setup-python v7.1.0, zizmor-action v0.8.1,
  zizmor 1.32.0, actionlint 1.7.12. Actions are pinned to full commit SHAs. The actionlint and zizmor versions and
  the pins in `template/.github/workflows/` are bumped by hand; Dependabot watches only the root workflows.
- **Dev tools.** `requirements-dev.txt` holds floors (`copier>=9.6`, `pytest>=8`, `pyyaml>=6.0.3`), tested with
  lowest-direct resolution on 3.12 on 2026-11-14. A floor is the minimum that provably works, not the latest.
  `copier.yml` sets `_min_copier_version: "9.6.0"`. The Copier floor is 9.6.0 because 9.4.0 and 9.5.0 ignore
  templated `_exclude` entries, so every profile receives every module. CI installs the newest Copier, so the floor
  is not tested until a lowest-direct job exists (see open items).
- **Dependabot.** The `github-actions` entry stays first, weekly and grouped, with a 7-day cooldown; a test checks
  this. The `pip` entry is weekly with `versioning-strategy: increase-if-necessary`, so a floor is raised only when
  the new version needs it. The `dev-tools` group has never been seen in use. No Dependabot PR has appeared since
  #22 (2026-11-08). Before approving one, read it and check `template (3.12)` and the package's `Requires-Python`.
- **Migrations** (`migrations/*.py`) keep Python 3.9-compatible grammar: they run on the user's interpreter during
  `copier update`, which can be older than the floor.
- `.github/assets/legacy/**` is an archive and is exempt from the floor (its images still say 3.9).

## Releases
- Tags are annotated `vX.Y.Z`, made on the merge commit after the PRs to ship have merged. Steps: runbook.
- The ruleset `protect-release-tags` (id 27248881, tags `v*`, active, no bypass actors) forbids updating, deleting
  or force-moving a tag. There is no creation rule. A pushed tag is permanent, so keep its annotation to a summary
  line and one short paragraph. The details go in the release notes, which stay editable.
- `.github/release.yml` groups merged PRs by label (`breaking` first); a test checks the file. Label a PR
  `breaking` when a generated project must do something after `copier update`. Such a release also ships a
  migration and an upgrade test (ADR 0008).
- Raising the Python floor is a breaking change and goes in the release notes of the minor that does it.
- Latest: `v0.4.0` (2026-11-14, on `796e6ef`): Python 3.12 or newer; no migration, because no generated project is
  known to exist.

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

## Open items and dates
- **Lowest-direct Copier job (harness PR):** add a CI job that installs the Copier floor from
  `requirements-dev.txt` (currently 9.6.0), so the floor is tested; today CI installs the newest Copier.
- **On or after 2026-11-28:** if the 3.15 leg stayed green, a small harness PR sets its `experimental` to `false`
  and updates the sentence in `CONTRIBUTING.md`. `ci-gate` then covers it; the ruleset needs no edit.
- **Protect `.github/actionlint.yaml`:** one harness PR that edits the regex, `CODEOWNERS` and `AGENTS.md` rule 3
  together.
- **Remove the `ubuntu-26.04` entry** from `.github/actionlint.yaml` once the pinned actionlint knows it.
- **November 2027 review:** by the floor rule 3.12 will then have under 18 months left, so the floor moves to 3.13.
- **Release notes flow:** the README "Releasing" steps use `--notes-from-tag`, but the `v0.4.0` notes were written
  by hand with a short tag annotation. Owner to pick one and align the README.
- **Undecided, owner's call:** retire `owner-approval.yml` (the Code Owner review is the real gate; the status is a
  convenience); commit the ruleset JSON into the repo (deferred 2026-11-07: a copy nothing can check against
  GitHub; if wanted, add `.github/rulesets/` to the protected set in all three places); protect
  `template/.github/workflows/`; point `AGENTS.md` rule 2 at the PR template.
- **Stale remote branches:** `chore/agents-role-bundles` (PR #5) and `chore/ci-hardening` (PR #9) are merged;
  `plan/template-upgrade-hardening` is PR #36, closed unmerged; `feat/adr-number-block` is PR #63, closed on
  2026-11-16. Delete them in the GitHub UI.
- **Baselines (roles part G):** the owner's manual real-agent runs on the golden tasks, recorded in
  `template/agents/evals/results/README.md` (empty today). Tracked in #7, which also lists the `security-routing`
  run and the skill-opening transcript check.
- **Unverified:** nothing has run Claude Code against the generated `.claude/agents/` files, so it is not confirmed
  that it loads the `skills:`, `disallowedTools` and `model` lines. The check plan is #59.
- **Grader hardening (H), after G:** the four known `callable-researcher` gaps and the exact-equality
  `_placeholder_free` fix are #61.
- **Small fixes:** the `sync_agents.py` crash on a non-object target, validating `claude.models` values and
  validating `needs_role` are #60.
- **Ideas, not decided:** generate `.agents/skills/` so Codex, OpenCode and Copilot see skills (needs a design note);
  fix the docs claim that OpenCode and Codex read `agents/` directly; refactor `grade_task` in `eval_harness.py`; a
  hook that limits reviewer and researcher writes to their own item files.
