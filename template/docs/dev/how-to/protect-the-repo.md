---
title: Protect the repository
type: how-to
status: active
summary: Apply the shipped branch and tag rulesets on GitHub and turn on the security settings that no file in the repo can set.
related_code: [.github/rulesets/protect-default-branch.json, .github/rulesets/protect-release-tags.json]
---
# Protect the repository

Goal: the default branch cannot be deleted, rewritten or merged without a pull request and a green `check`, release tags stay put, and the security features GitHub keeps outside the repo are on.

Before you start: the repo is on GitHub, you are an admin of it, and you kept the `github` module (it ships the files below). `check.yml` has run at least once, so GitHub knows the status `check`. Rulesets are available on public repositories with GitHub Free; a private repository needs GitHub Pro, Team or Enterprise Cloud.

## Apply the shipped rulesets

`.github/rulesets/` holds two rulesets in the format GitHub imports. Nothing applies them for you.

1. Open the repository **Settings**, then under "Code, planning, and automation" click **Rulesets** and **Rulesets** again.
2. Open the **New ruleset** dropdown, choose **Import a ruleset**, pick `.github/rulesets/protect-default-branch.json`, review it and click **Create**.
3. Repeat with `.github/rulesets/protect-release-tags.json`.
4. From a command line instead: `gh api repos/{owner}/{repo}/rulesets --input .github/rulesets/protect-default-branch.json`, then the same for the tag file. `gh` fills in `{owner}` and `{repo}` when you run it inside the repository.

| Ruleset | Does |
|---|---|
| `protect-default-branch.json` | The default branch cannot be deleted or force-pushed; changes arrive by pull request, merged with a merge commit; a push to the pull request dismisses stale approvals; the status `check` must pass. **0 approvals required** |
| `protect-release-tags.json` | Tags matching `v*` cannot be moved or deleted. Creating one is still allowed |

Neither ruleset names a bypass actor, so while a ruleset is active even an administrator goes through it. An administrator can still edit or disable the ruleset; that is the escape hatch below. To cut a release tag you do not need a bypass. To fix a wrong tag, set the ruleset to **Disabled**, fix the tag, set it back to **Active**.

The default-branch ruleset allows merge commits only. Keep **Allow merge commits** enabled under **Settings → General → Pull Requests**. If the project squashes or rebases, change `allowed_merge_methods` in the JSON before importing, or edit the ruleset after.

Why 0 approvals: a repository with one human cannot approve its own pull request, so a required approval would block every merge. The required `check` is the gate, plus whatever review your process asks for (see `AGENTS.md`).

### A stricter variant

For a team (at least two accounts that can approve), edit the imported ruleset, or the JSON before importing, in the `pull_request` rule:

- `required_approving_review_count`: `1`
- `require_code_owner_review`: `true` (needs real owners in `.github/CODEOWNERS`)
- `require_last_push_approval`: `true` (the approval must come after the last push, so nobody approves and then adds code)
- `required_review_thread_resolution`: `true`

Keep `dismiss_stale_reviews_on_push` on. If you add more required checks, use the name GitHub reports for the job: the `name:` value if set, otherwise the job id.

## Settings no file can set

Do each once per repository (or once per organization, where GitHub offers that). Availability depends on repository visibility and plan: if a setting is missing, your plan or visibility does not include it. The path is how GitHub's documentation names it; GitHub moves these pages around, so if a label is missing, search the settings page for the feature name.

| Setting | Where | Notes |
|---|---|---|
| Secret scanning and push protection | **Settings → Security and quality → Advanced Security**: enable **Secret Protection** if it is not already on (a private repository needs a plan that includes it), then enable **Push protection** | Verified. Public repositories are scanned automatically. Push protection is not enabled by default, even for public repositories. Private repositories need a plan that includes GitHub Secret Protection; if the setting is not shown, the plan or repository type is not eligible |
| Private vulnerability reporting | **Settings → Security and quality → Advanced Security → Private vulnerability reporting → Enable** | Verified. Public repositories only |
| Dependabot alerts and security updates | **Settings → Security and quality → Advanced Security**: enable **Dependabot alerts**, then **Dependabot security updates** | Verified. Neither is enabled by default, even for public repositories; alerts need the dependency graph |
| Code scanning | **Settings → Security and quality → Advanced Security → Code Security → CodeQL analysis → Set up → Default → Enable CodeQL** | Verified. Public repositories, or private repositories covered by GitHub Code Security; if the setting is not shown, the repository type or plan is not eligible |
| Workflow permissions read-only | **Settings → Actions → General → Workflow permissions**: choose **Read repository contents and packages permissions**, then **Save** | Verified for the repository page. New personal repositories already default to read-only; organization repositories inherit the organization setting. Every workflow here also sets `permissions:` itself |
| Release immutability | **Settings**, scroll to the **Releases** section, select **Enable release immutability** | Verified. Applies only to releases published after you enable it |

Turn release immutability on once the project publishes releases: a release's tag and assets can then never be changed, which is the same promise `protect-release-tags.json` makes for the tag alone.

## If something goes wrong

- The import fails: read the importer's message. GitHub rejects a file it cannot parse or validate. Compare with a ruleset exported from a working repository.
- The `check` status is not offered or never turns green: the ruleset waits for the status `check`. Run the workflow once on a pull request, and keep the job name that GitHub reports as `check` in `.github/workflows/check.yml`; if you rename the job, update the ruleset context too.
- You are locked out of merging: change the ruleset's enforcement to **Disabled** while you fix it. Do not leave it disabled.
- These files follow the shape of a live ruleset. Import them on a scratch repository first; tell the template if the import fails.
