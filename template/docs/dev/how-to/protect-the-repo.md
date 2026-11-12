---
title: Protect the repository
type: how-to
status: active
summary: Apply the shipped branch and tag rulesets on GitHub and turn on the security settings that no file in the repo can set.
---
# Protect the repository

Goal: the default branch cannot be deleted, rewritten or merged without a pull request and a green `check`, release tags stay put, and the security features GitHub keeps outside the repo are on.

Before you start: the repo is on GitHub, you are an admin of it, and you kept the `github` module (it ships the files below). `check.yml` has run at least once, so GitHub knows the status `check`.

## Apply the shipped rulesets

`.github/rulesets/` holds two rulesets in the format GitHub imports. Nothing applies them for you.

1. Open the repository **Settings**, then under "Code, planning, and automation" click **Rulesets** and **Rulesets** again.
2. Open the **New ruleset** dropdown, choose **Import a ruleset**, pick `.github/rulesets/protect-default-branch.json`, review it and click **Create**.
3. Repeat with `.github/rulesets/protect-release-tags.json`.
4. From a command line instead: `gh api repos/<owner>/<repo>/rulesets --input .github/rulesets/protect-default-branch.json`, then the same for the tag file.

| Ruleset | Does |
|---|---|
| `protect-default-branch.json` | The default branch cannot be deleted or force-pushed; changes arrive by pull request, merged with a merge commit; a push to the pull request dismisses stale approvals; the status `check` must pass. **0 approvals required** |
| `protect-release-tags.json` | Tags matching `v*` cannot be moved or deleted. Creating one is still allowed |

Neither ruleset names a bypass actor: nobody can skip the rules, you included. To cut a release tag you do not need a bypass. To fix a wrong tag, set the ruleset to **Disabled**, fix it, set it back to **Active**.

Why 0 approvals: a repository with one human cannot approve its own pull request, so a required approval would block every merge. The required `check` is the gate, plus the review your process asks for (`docs/dev/how-to/update-from-template.md` and the review rules in `AGENTS.md`).

### A stricter variant

For a team (at least two accounts that can approve), edit the imported ruleset, or the JSON before importing, in the `pull_request` rule:

- `required_approving_review_count`: `1`
- `require_code_owner_review`: `true` (needs real owners in `.github/CODEOWNERS`)
- `require_last_push_approval`: `true` (the approval must come after the last push, so nobody approves and then adds code)
- `required_review_thread_resolution`: `true`

Keep `dismiss_stale_reviews_on_push` on. If you add more required checks, use the job names from `.github/workflows/`.

## Settings no file can set

Do each once per repository (or once per organization, where GitHub offers that). The path is how GitHub's documentation names it; GitHub moves these pages around, so if a label is missing, search the settings page for the feature name.

| Setting | Where | Status |
|---|---|---|
| Secret scanning and push protection | **Settings**, **Advanced Security** (GitHub's Enterprise Server 3.20 documentation: enable "Secret Protection" if shown, then "Secret scanning", then push protection) | Verified against the Enterprise Server 3.20 docs; labels on github.com may differ |
| Private vulnerability reporting | **Settings**, under security | **Not verified:** GitHub's own sources give two different paths. Search the settings for "private vulnerability reporting". It is what the security policy tells reporters to use |
| Dependabot alerts and security updates | **Settings**, **Advanced Security**: alerts are on for public repos; click **Enable** next to "Dependabot security updates" | Verified against the Enterprise Server 3.20 docs |
| Code scanning | **Settings**, **Advanced Security**, next to "CodeQL analysis" choose **Set up**, then **Default**, then **Enable CodeQL** | Verified against the Enterprise Server 3.20 docs |
| Workflow permissions read-only | **Settings**, **Actions**, **General**, under "Workflow permissions" choose "Read repository contents permission", **Save** | Verified for the organization page; the repository page is assumed to match. Every workflow here also sets `permissions:` itself |
| Release immutability | **Settings**, in the "Releases" section, select **Enable release immutability** | Verified. Applies only to releases published after you enable it |

Turn release immutability on once the project publishes releases: a release's tag and assets can then never be changed, which is the same promise `protect-release-tags.json` makes for the tag alone.

## If something goes wrong

- The import fails: open the JSON in the importer's error message; a field GitHub does not know is rejected. Compare with a ruleset exported from another repository.
- The `check` status is not offered or never turns green: the ruleset waits for a status called `check`. Run the workflow once on a pull request, and keep the job id `check` in `.github/workflows/check.yml`.
- You are locked out of merging: change the ruleset's enforcement to **Disabled** while you fix it. Do not leave it disabled.
- These files were never imported on GitHub by the template's authors: they follow the shape of a live ruleset, but the first import is yours. Tell the template if it fails.
