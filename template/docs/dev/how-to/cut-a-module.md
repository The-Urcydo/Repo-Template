---
title: Cut a module
type: how-to
status: active
summary: Remove an optional module (docs, infra, evals, CI...) cleanly, and make sure template updates do not bring it back.
---
# Cut a module

Goal: remove a part of the repo you do not need without leaving dangling references.

## Steps

1. List modules and what is installed: `python3 tools/remove_module.py`.
2. Preview the cut (a dry run, changes nothing): `python3 tools/remove_module.py <name>`. It prints every path it would remove and any removal note.
3. Apply it: `python3 tools/remove_module.py <name> --apply`. The tool then:
   - deletes the module's paths,
   - regenerates the indexes and adapters,
   - sets `profile: custom` in `.copier-answers.yml` with the remaining modules, so `copier update` will not resurrect the module,
   - runs `python3 tools/check.py` and reports problems.
4. Fix anything `check.py` reports (usually a stray mention in a file you wrote), then commit.

## If something goes wrong

- Another module requires it: the tool refuses and names the dependants; cut those first.
- Cut the wrong module: `git restore` the paths, or `git revert` the commit, and re-run `python3 tools/sync_indexes.py`. Also restore `.copier-answers.yml`.
- `module-coupling` errors from `check.py` mean a core file links into a module. Replace the link with a backticked path (core must not depend on optional modules).

Which modules exist and their paths: `python3 tools/remove_module.py`, or the generated `docs/dev/reference/modules.md`.
