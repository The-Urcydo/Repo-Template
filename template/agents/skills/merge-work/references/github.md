# GitHub specifics for merge-work

Read this when the project is on GitHub. Nothing here is required elsewhere. `gh api` (REST) works where `gh pr` subcommands (GraphQL) are blocked. Replace `<o>/<r>` with owner and repo, and `<n>` with the PR number.

## Commands

- Files the PR changes: `gh api repos/<o>/<r>/pulls/<n>/files --jq '.[].filename'`
- Head commit and mergeability: `gh api repos/<o>/<r>/pulls/<n> --jq '.head.sha, .mergeable_state'`. `clean` can merge; `behind`, `blocked`, `dirty` and `unstable` cannot yet.
- Checks on that head commit: `gh api repos/<o>/<r>/commits/<sha>/check-runs --jq '.check_runs[] | [.name, .status, .conclusion] | @tsv'`, and commit statuses: `gh api repos/<o>/<r>/commits/<sha>/status --jq .state`. The `<sha>` must be the PR's current head.
- Record the owner's grant on the PR: `gh api repos/<o>/<r>/issues/<n>/comments -F body=@file`
- Merge commit: `gh api -X PUT repos/<o>/<r>/pulls/<n>/merge -f merge_method=merge -f sha=<head sha>`. With `sha` set to the head you checked, GitHub refuses the merge if the branch moved after your checks.

## Make the gate real (for the owner)

`merge-work` is instructions, and an agent can be wrong or manipulated. These settings make the repo refuse a bad merge whatever an agent does.

1. Protect the default branch: require a pull request and the `check` status.
2. Require review from code owners. Put your GitHub handle in `.github/CODEOWNERS` and uncomment its lines; the `*` line covers `tools/`, `.github/`, `agents/` and `AGENTS.md`.
3. Dismiss stale approvals when new commits are pushed.
4. Require branches to be up to date, or use a merge queue. With a queue, add `merge_group:` next to `pull_request:` in `.github/workflows/check.yml`; without it the required check never reports and merges stall.
5. Allow merge commits only, if that is the project's rule.
6. Give no agent token admin or bypass rights.
