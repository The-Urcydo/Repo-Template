# Test performance

What the root test suite costs, what it deliberately does not run on every pass, and how to reproduce
the numbers. Measurements are wall-clock on the maintainer's Mac (15 logical CPUs, 5 performance cores)
and on GitHub-hosted `ubuntu-26.04` runners; use them for trends, not as guarantees.

Last measured 2026-11-17 on PR #72 (`a6ababe`); the baseline is `main` at `810ef7c`, run by PR #71.

## Budget
- Static checks (`test_repo_governance.py`, `test_root_*.py`, `test_supported_versions.py`): under 2 seconds.
- Full suite on a laptop: about 2 minutes.
- One CI matrix leg: under 5 minutes.

## Why the suite is fast now
Before #72 the root suite executed 1,965 shipped test cases (8.3 full passes of `tools/tests`) inside
seven tests. That was 90% of a **920.85s (15m20s)** run. #72 keeps one canonical execution of the
shipped suite and uses `unittest.TestLoader` for the lean/cut/update checks.

| Measurement | Before | After #72 |
|---|---:|---:|
| Local, default | 920.85s (15m20s) | **91.28s (1m31s)** |
| Local, `-n0` | - | **177.18s (2m57s)** |
| CI test step (3.12 / 3.14 / 3.15) | 15m27s / 17m46s / 16m35s | **1m33s / 1m51s / 1m44s** |
| CI job total (3.12 / 3.14 / 3.15) | 15m54s / 18m01s / 16m52s | **1m43s / 2m06s / 2m09s** |
| Shipped suite in a full project | ~85-92s | **71.45s** |

The after numbers are 131 passed locally. CI reports 129 passed + 2 skipped because the `template` job
does not install `actionlint` and `zizmor`; the `workflow-lint` job does.

## What runs, and what does not
- One canonical `python -m unittest discover -s tools/tests` in a full project seeded with a real work
  item, a question and a 1 MB file.
- Lean, cut-evals and update tests use `suite_size()`: `unittest.TestLoader().discover()` imports every
  test module and counts cases without executing them. A broken import or a missing test file still
  fails.
- `pytest.ini` sets `testpaths = tests`, so a bare `pytest` does not collect `template/tools/tests`
  (which would also write `__pycache__` into `template/`). It runs `-n auto --maxprocesses 8 --dist
  worksteal`; use `-n0` when debugging one test.
- The shipped test fixture is built once per process and copied per test
  (`template/tools/tests/test_tools.py`).

## The lean run: measured, deferred
The root suite does not execute the shipped suite in a lean project.
`test_lean_project_carries_no_eval_harness_tests` loads it and asserts the counts and the
`class EvalHarnessTests` marker, but does not run it. The lean profile is the one place the suite would
run with every optional module absent.

On 2026-11-17, restoring the run (adding `py(lean, "-m", "unittest", "discover", "-s", "tools/tests")`
to that test) measured:

- lean suite: 153 tests in **31.01s**;
- full root suite: **120.48s (2m00s)** instead of 91.28s (1m31s), about **+29s**.

It was deferred because the canonical full run executes all 237 shipped tests, `suite_size()` still fails
on an import error, and `check.py --strict` covers the lean/cut structure. The remaining gap is real:
only a lean execution proves the suite's skip logic when every optional module is absent. Restore it if a
lean-only failure appears, or if the owner wants zero coverage loss:

```python
r = py(lean, "-m", "unittest", "discover", "-s", "tools/tests", "-q")
assert r.returncode == 0, r.stderr[-3000:]
```

## Reproduce
```bash
python -m pytest tests -q --durations=20          # full, parallel
python -m pytest tests -q -n0                     # full, in order
python -m pytest tests/test_repo_governance.py -q -n0
python -m pytest tests -q -k update               # one area
python -m pytest tests -q --lf -n0                # last failure
```

The tool tests must run in a generated project, not in `template/`: they live at the repo root in
`tool-tests/`, and `tests/test_template.py` copies them into a probe as `tools/tests/` before the
canonical run. To run them by hand, follow `tool-tests/README.md`; a quick probe is
`copier copy --defaults --trust --vcs-ref HEAD --data project_name=Probe --data profile=full . <dir>`.

Since the 2026-11-20 change, generated projects ship no `tools/tests` in any profile. The root suite
still executes the same tests against a generated project and counts cases with `unittest.TestLoader`
for the lean/cut/update checks; the measurements above remain the comparison point.
