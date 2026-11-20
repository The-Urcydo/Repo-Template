# Contributing to Repo-Template

Thanks for your interest. This repository is the Copier template; the projects it generates belong to whoever generates them. Everything under `template/` ships to every generated project, so a change here reaches a lot of repositories. Please keep that in mind.

## Before you start

- **Found a bug or have an idea?** Open an issue with the bug report or feature request form. Check the open issues first.
- **Found a security problem?** Do not open a public issue. Follow the [security policy](SECURITY.md).
- **The rules for working in this repository** apply to humans and agents alike and are written in [AGENTS.md](AGENTS.md). If this page and `AGENTS.md` ever disagree, `AGENTS.md` wins.

## Make a change

1. Branch from `main`. One topic per pull request, and do not stack pull requests on each other.
2. Set up and run the tests:

   ```
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r requirements-dev.txt
   python -m pytest tests -q
   ```

   The suite generates real projects and takes about two minutes: `pytest.ini` runs it in parallel with
   `pytest-xdist` and limits a bare `pytest` to `tests/`. Use `-n0` when debugging one test in order.
   CI runs the suite twice on Python 3.12: once with the newest Copier and once with the floor parsed from
   `requirements-dev.txt` (9.6.0). Both legs report as `template (3.12)`; `ci-gate` aggregates them, so no new
   required check or ruleset edit was needed. See the CI section of `docs/maintainers/decisions.md`.
3. To try your branch by hand, always pass `--vcs-ref HEAD`:

   ```
   copier copy --trust --vcs-ref HEAD . <dir>
   ```

   Without it Copier builds from the newest release tag, so you would test the tag, not your branch.
4. Open a pull request. The description follows the pull request template: what changed, the evidence (the commands you ran and their results), and the decisions only the owner can make.

## What happens next

A reviewer who did not write the change runs the tests and checks the pull request against its description. Then the owner approves it and it is merged with a merge commit. The owner decides; agents and contributors propose.

Changes to the agent harness need the owner's explicit approval. The list of protected paths is in rule 3 of [AGENTS.md](AGENTS.md). A push after an approval makes that approval stale, so say so on the pull request before you push.

## Supported Python versions

Two rules set the range:

- **Floor:** the oldest CPython release that still receives security fixes and has at least 18 months of support left at the time of a template release.
- **Ceiling:** the newest stable CPython release.

CI currently tests Python 3.12 and 3.14, with 3.15 informational until it has been green for two weeks; the floor today is 3.12.

A newer push to a pull request cancels that pull request's older CI run, and a test job that runs longer than 30 minutes is stopped; runs on `main` always finish.

Raising the floor is a breaking change and is announced in the release notes of the template minor that does it.

| Version | Status on 2026-11-14 | End of support |
| --- | --- | --- |
| 3.9 | end of life | 2025-10-31 |
| 3.10 | end of life | 2026-10-01 |
| 3.11 | security fixes only | 2027-10 |
| 3.12 | security fixes only | 2028-10 |
| 3.13 | security fixes only | 2029-10 |
| 3.14 | bugfix | 2030-10 |
| 3.15 | bugfix | 2031-10 |

Review this section every November, after the October Python release. Source: [Status of Python versions](https://devguide.python.org/versions/) (checked 2026-11-14).

## Releasing

Release steps are in the [Releasing section of the README](README.md#releasing).

## Conduct

Everyone who takes part, human or agent, follows the [code of conduct](CODE_OF_CONDUCT.md).
