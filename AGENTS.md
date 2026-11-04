# Repo-Template

A Copier template for agent-ready repositories (one human, several AI agents). This file is for agents working on the template itself. It is not copied into generated projects: Copier copies only `template/`, and a generated project's own root file comes from `template/AGENTS.md.jinja`.

The human owner decides. Agents propose in pull requests.

## Commands
- Set up: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt`
- Test everything before opening a PR: `python -m pytest tests -q`. It takes a few minutes: it generates real projects and runs each one's `check.py --strict`, the shipped unit tests and a `copier update`.
- Try the template by hand: `copier copy --trust --vcs-ref HEAD . <dir>`. Always pass `--vcs-ref HEAD`: without it Copier builds from the latest release tag, so you would test the tag, not your branch.

## Where things are
- `template/`: everything generated into projects. Nested rules load when you work there: `template/agents/AGENTS.md`, `template/tools/AGENTS.md`, `template/docs/AGENTS.md`, `template/work/AGENTS.md`.
- `copier.yml`: questions, exclusions, post-generation tasks. `tests/`: template-level tests. `.github/`: this repo's own CI, not copied.
- Why it is built this way: the ADRs in `template/docs/decisions/` and `README.md`.

## Hard rules
1. Never push to `main`, never force-push, never merge. The owner merges, after saying so in-session.
2. One topic per PR, branched from `main`, not stacked. The description lists what changed, the evidence (commands and results) and the decisions only the owner can make.
3. These need the owner's explicit approval: `template/agents/`, `template/AGENTS.md.jinja`, this file, `CLAUDE.md`, `.github/CODEOWNERS` and `.github/workflows/owner-approval.yml`. The `owner-approved` label is the owner's to add; agents never add it. Without it `owner-approval.yml` shows a red check. It cannot block a merge: the repo has no branch protection.
4. Any other PR gets an independent review first: a reviewer that did not write it runs the tests and checks the PR against its description. Then the owner merges.
5. Everything under `template/` ships to every generated project: keep this repo's own notes out of it. ADRs there ship too: take the next number from `main` and check open PRs for the same number first.
6. New workflows set `permissions` and pin actions to commit SHAs.
7. Do not trust a check that ends in a counting pipe (`grep -c`, `wc -l`): if the first command fails it still prints 0. Use a command with an exit code.
