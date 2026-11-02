---
name: tailor-template
description: Makes a freshly generated repo specific to its project by filling placeholders, deleting unused ones, and cutting modules that are not needed. Use right after creating a repo from this template, or when asked to bootstrap, set up, or clean up the skeleton.
---
# Tailor the template

**Role:** whichever agent the human asks to set the repo up. It edits harness files, so the human approves the result.

Run once after generation. The goal: no placeholder left that nobody will fill, no module nobody will use.

1. List what is unfilled: `python3 tools/check.py --stubs`. Each line is a placeholder to fill or delete.
2. Fill `AGENTS.md`: replace the `TODO` build/test/run line with the real commands. Keep the file under 100 lines and add only facts an agent cannot discover from the repo.
3. Fill `README.md` description and, for each module you keep, its README (`docs/product/`, `docs/operations/`, ...).
4. Decide on the modules you do not need: `python3 tools/remove_module.py` lists them; preview a cut with `python3 tools/remove_module.py <name>`; apply with `--apply`. Cutting is cheap and reversible through git.
5. Write the first decision down: `python3 tools/new_adr.py "Choose the tech stack"` and fill it in.
6. Replace the placeholders in the code folders your layout generated (`docs/reference/repo-map.md` lists them) with real structure when the first code lands, or leave them marked as placeholders until then. With the `minimal` layout there are none: give every folder you add a `README.md` with `summary` and `owner_role`.
7. `python3 tools/sync_indexes.py && python3 tools/sync_agents.py && python3 tools/check.py`, then commit.

Do not delete the folder READMEs of folders you keep: they carry the `owner_role` and `summary` the tools rely on. Full guide: `docs/how-to/bootstrap-from-template.md`.
