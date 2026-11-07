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
1. Never push to `main`, never force-push. Merge a PR only when an owner account has approved its latest commit (an APPROVED review from `nguyenquocduyloc` or `NguyenLoc231`) and the status `owner-approval/review` is green on it. Use a merge commit (no squash, no rebase). If either is missing, leave the merge to the owner.
2. One topic per PR, branched from `main`, not stacked. The description lists what changed, the evidence (commands and results) and the decisions only the owner can make.
3. Changes to the agent harness need the owner's explicit approval: `template/agents/`, `template/AGENTS.md.jinja`, this file, `CLAUDE.md`, `.github/CODEOWNERS`, `.github/workflows/` (all workflows, `owner-approval.yml` included) and `.github/dependabot.yml`.
   - Approval is as defined in rule 1. `.github/CODEOWNERS` lists the owner accounts.
   - `shiniroku` and `shinkir6u` are agent accounts. An agent never approves.
   - A push after the approval makes it stale: say so on the PR before you push to an approved PR.
   - `owner-approval/review` stays red on a PR that touches these paths until an owner has approved the latest commit, and is green otherwise. The ruleset `protect-main` requires it on every PR to `main`, together with Code Owner review.
4. Any other PR gets an independent review first: a reviewer that did not write it runs the tests and checks the PR against its description. Then the owner approves it (rule 1) and it can be merged.
5. Everything under `template/` ships to every generated project: keep this repo's own notes out of it. ADRs there ship too: take the next number from `main` and check open PRs for the same number first.
6. New workflows set `permissions` and pin actions to commit SHAs.

## Gotchas
- Do not trust a check that ends in a counting pipe (`grep -c`, `wc -l`): if the first command fails it still prints 0. Use a command with an exit code.
