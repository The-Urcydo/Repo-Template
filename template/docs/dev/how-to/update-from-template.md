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

1. Commit or stash all local changes: `git status` must be clean.
2. Update: `copier update --trust`. Copier compares the template version you used with the latest tagged version and merges the difference. `--trust` lets it run the two sync tools as part of the update, which normally rebuild the generated files.
3. Resolve conflicts. Copier leaves normal merge-conflict markers in files you also changed. `python3 tools/check.py` reports each one as `conflict-marker` with the file and line; fix it and remove the markers.
4. Verify: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py && python3 tools/check.py`. Always run this step after a template change that moves files: Copier's post-copy tasks can run before the final moves, so the generated indexes may be stale until you resync.
5. Review the diff and commit.

## If something goes wrong

- Generated files conflict: do not merge them. Delete the conflicted generated file and re-run the sync tools; they rebuild it from sources.
- A module you cut came back: `.copier-answers.yml` should say `profile: custom` and list the modules you kept. `remove_module.py --apply` writes this; fix it by hand if you cut a module manually, then cut it again.
- You want a specific template version: `copier update --trust --vcs-ref <tag>`.

## Updating across a release that moved files

A release that moves what you own ships a migration that Copier runs for you (ADR 0008, `docs/decisions/0008-ship-a-migration-and-an-upgrade-test-with-every-breaking-release.md`). It needs `--trust`, runs only when your project crosses that release, and prints one `migrate: old -> new` line per file. Read the release notes first: the tag message names the break.

From v0.2.0 to v0.3.0 the docs moved from `docs/{explanation,how-to,reference,tutorials}/` to `docs/dev/...`. The migration moves your own docs there with `git mv` and recomputes their relative links. What it cannot do:

- **Your edit next to a line the template also changed** (for example the `README.md` link to this guide) still conflicts. Resolve it by hand; `check.py` finds the markers.
- **An edit to a shipped doc at its old path** (say a row you added to `docs/reference/glossary.md`) is not carried to `docs/dev/reference/glossary.md`. Recover it from git: `git show HEAD:docs/reference/glossary.md`, then re-apply your lines.
- **Links from files that stay put** (your own ADRs, `README.md`) to a moved doc are not rewritten. `check.py` reports each as `broken-link`; edit the path to add `dev/`.
- **A file already at the new path** is never overwritten: the old copy stays and the migration says so on stderr. Compare the two and delete one.

Why Copier and what `--trust` is for: `docs/decisions/0004-deliver-with-copier-and-cuttable-modules.md`.
