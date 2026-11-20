# Tool tests (template repo only)

These two files are the unit tests for the tools in `template/tools/`. They live here, at the
repository root, so **generated projects do not ship them**. `tests/test_template.py` copies them
into a throwaway generated project as `tools/tests/` before running the one canonical execution
and before counting cases with `unittest.TestLoader`.

To run them by hand, generate a project and copy the files into it:

```bash
copier copy --defaults --trust --vcs-ref HEAD --data project_name=Probe . /tmp/probe
mkdir -p /tmp/probe/tools/tests
cp tool-tests/*.py /tmp/probe/tools/tests/
(cd /tmp/probe && python3 -m unittest discover -s tools/tests -q)
```

The eval-harness file is copied only for profiles with the `evals` module; for a lean project copy
just `test_tools.py`. The root suite also runs `python -m pytest tests -q`, which includes the
canonical execution; see `docs/maintainers/test-performance.md` for the measured cost.
