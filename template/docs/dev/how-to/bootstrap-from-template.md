---
title: Bootstrap a repo from the template
type: how-to
status: active
summary: Steps to take right after generating a repo from the template - fill placeholders, cut what you do not need, and make the first commit.
---
# Bootstrap a repo from the template

**Role:** the agent that sets the repo up, acting for the human. It edits harness files, so the human approves the result.

Goal: a repo with no placeholder nobody will fill and no module nobody will use. Run this once, right after generation. Before you start: the repo was generated with `copier copy --trust` and you are inside it.

## Steps

1. Create the git repo and commit the pristine state (so `copier update` and `git diff` have a baseline):
   ```
   git init && git add -A && git commit -m "Initial commit from Repo-Template"
   ```
2. Confirm it is healthy: `python3 tools/check.py` prints `ok`.
3. See what is unfilled: `python3 tools/check.py --stubs`. Every line is a placeholder to fill or delete, except the code-folder placeholders that step 8 leaves until the first code lands.
   With the `github` module, replace the commented entries in `.github/CODEOWNERS` with real users or teams. Deleting only that file leaves the module partly present, so `check.py --strict` fails on it; cut the whole `github` module (step 4) if you do not want it.
4. Cut modules you do not need: `python3 tools/remove_module.py` lists them; preview with `python3 tools/remove_module.py <name>`; apply with `--apply`. See `docs/dev/how-to/cut-a-module.md`.
5. Fill `AGENTS.md`: replace both `TODO`s — the project description and the build, test and run line. Keep the file under 100 lines and add only what an agent cannot discover from the repo.
6. Describe the project in `README.md` (one paragraph) and fill the module pages the stubs list, `docs/user/README.md` and `SECURITY.md`.
7. Record the first decision: `python3 tools/new_adr.py "Choose the tech stack"`, then fill the sections it creates and the front-matter `summary`.
8. Code-folder READMEs start as placeholders. Until the first code lands, leave them as placeholders; `--stubs` keeps listing them, which is expected. When the first code lands, fill in the code-folder READMEs your layout generated (`docs/dev/reference/repo-map.md` lists them) and set their `status` to `active`. With the `minimal` layout there are none: give every folder you add a `README.md` with `summary` and `owner_role`.
   Do not delete the README of a folder you keep: it carries the `owner_role` and `summary` the tools read. If one is gone, restore it.
9. Regenerate and verify: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py && python3 tools/check.py`.
10. Run `python3 tools/check.py --stubs` again. Treat each remaining entry as a page to fill or delete, except the code-folder placeholders from step 8.
11. Commit. From now on CI (if you kept the `github` module) runs `check.py --strict`.
12. Optional: turn on the pre-commit health check with `just hooks` (or `git config core.hooksPath .githooks`). It runs `check.py` and both sync checks before each commit, works in every worktree of the clone, and `git commit --no-verify` skips it once.

## If something goes wrong

- `check.py` reports `generated-drift`: run the sync tools; never edit generated files by hand.
- `check.py` reports `module-partial`: finish the cut with `remove_module.py <name> --apply`, or restore the missing file.
