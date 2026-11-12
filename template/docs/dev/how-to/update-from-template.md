---
title: Update from the template
type: how-to
status: active
summary: Pull template improvements into a repo created from it with copier update, and resolve conflicts.
---
# Update from the template

Goal: get new roles, protocols, tools and docs that the template gained since you generated the repo.

Before you start: Copier is installed (`pipx install copier` or `pip install copier`), the repo is a git repo with a clean working tree, and `.copier-answers.yml` exists.

## Steps

0. Optional: `python3 tools/template_status.py` says whether a newer release exists. With the `github` module a weekly workflow runs the same check and keeps at most one open issue when there is one; it never opens a pull request.
1. Commit or stash all local changes: `git status` must be clean.
2. Update: `copier update --trust`. Copier compares the template version you used with the latest tagged version and merges the difference. `--trust` lets it run the two sync tools as part of the update, which normally rebuild the generated files.
3. Resolve conflicts. Copier leaves normal merge-conflict markers in files you also changed. Search for `<<<<<<<`, fix, and remove the markers.
4. Verify: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py && python3 tools/check.py`. Always run this step after a template change that moves files: Copier's post-copy tasks can run before the final moves, so the generated indexes may be stale until you resync.
5. Review the diff and commit.

## If something goes wrong

- Generated files conflict: do not merge them. Delete the conflicted generated file and re-run the sync tools; they rebuild it from sources.
- A module you cut came back: `.copier-answers.yml` should say `profile: custom` and list the modules you kept. `remove_module.py --apply` writes this; fix it by hand if you cut a module manually, then cut it again.
- You want a specific template version: `copier update --trust --vcs-ref <tag>`.

Why Copier and what `--trust` is for: `docs/decisions/0004-deliver-with-copier-and-cuttable-modules.md`.
