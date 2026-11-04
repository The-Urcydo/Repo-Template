# tools/ rules

- Standard library only (Python 3.9+). No installs: an agent must always be able to run `python3 tools/<x>.py`.
- Quiet on success, one line per problem, non-zero exit code on failure. Output is read by agents: keep it short and actionable.
- Functions take `root` explicitly so tests can run against temporary trees; CLIs read `REPO_ROOT` or default to the repo that contains `tools/`.
- Anything that writes shared state (items, ADR numbers, the human queue) must hold `file_lock` from `_lib.py`.
- Every tool gets a unit test in `tools/tests/`. Run them with `python3 -m unittest discover -s tools/tests`.
- When you change how front matter, statuses or generated files work, update `docs/dev/reference/` in the same change.
