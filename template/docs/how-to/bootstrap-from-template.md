---
title: Bootstrap a repo from the template
type: how-to
status: active
summary: Steps to take right after generating a repo from the template - fill placeholders, cut what you do not need, and make the first commit.
---
# Bootstrap a repo from the template

Goal: a repo with no placeholder nobody will fill and no module nobody will use.

Before you start: the repo was generated with `copier copy --trust` and you are inside it.

## Steps

1. Create the git repo and commit the pristine state (so `copier update` and `git diff` have a baseline):
   ```
   git init && git add -A && git commit -m "Initial commit from Repo-Template"
   ```
2. Confirm it is healthy: `python3 tools/check.py` prints `ok`.
3. See what is unfilled: `python3 tools/check.py --stubs`. Every line is a placeholder to fill or delete.
4. Cut modules you do not need: `python3 tools/remove_module.py` lists them; preview with `python3 tools/remove_module.py <name>`; apply with `--apply`. See `docs/how-to/cut-a-module.md`.
5. Fill `AGENTS.md`: replace the `TODO` line with the real build, test and run commands. Keep the file under 100 lines and add only what an agent cannot discover from the repo.
6. Describe the project in `README.md` (one paragraph) and fill the READMEs of the modules you kept.
7. Record the first decision: `python3 tools/new_adr.py "Choose the tech stack"`.
8. When the first code lands, fill in the code-folder READMEs your layout generated (`docs/reference/repo-map.md` lists them) and set their `status` to `active`. With the `minimal` layout there are none: give every folder you add a `README.md` with `summary` and `owner_role`.
9. Regenerate and verify: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py && python3 tools/check.py`.
10. Commit. From now on CI (if you kept the `github` module) runs `check.py --strict`.

## If something goes wrong

- `check.py` reports `generated-drift`: run the sync tools; never edit generated files by hand.
- You deleted a folder README: restore it. The tools read `owner_role` and `summary` from folder READMEs.

An agent can do this for you: tell it to use the `tailor-template` skill (`agents/skills/tailor-template/SKILL.md`).
