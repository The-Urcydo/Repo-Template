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

   The suite generates real projects and takes a few minutes.
3. To try your branch by hand, always pass `--vcs-ref HEAD`:

   ```
   copier copy --trust --vcs-ref HEAD . <dir>
   ```

   Without it Copier builds from the newest release tag, so you would test the tag, not your branch.
4. Open a pull request. The description follows the pull request template: what changed, the evidence (the commands you ran and their results), and the decisions only the owner can make.

## What happens next

A reviewer who did not write the change runs the tests and checks the pull request against its description. Then the owner approves it and it is merged with a merge commit. The owner decides; agents and contributors propose.

Changes to the agent harness need the owner's explicit approval. The list of protected paths is in rule 3 of [AGENTS.md](AGENTS.md). A push after an approval makes that approval stale, so say so on the pull request before you push.

## Releasing

Release steps are in the [Releasing section of the README](README.md#releasing).

## Conduct

Everyone who takes part, human or agent, follows the [code of conduct](CODE_OF_CONDUCT.md).
