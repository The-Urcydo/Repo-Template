<!-- Rules for this repo: AGENTS.md. One topic per PR, branched from main, not stacked (rule 2). -->
## Summary
<!-- One topic, one short paragraph: what changed and why, plus the base commit on main. -->

## What changed
<!-- Files and behavior changed, whether template/ is touched (rule 5), and any intentional out-of-scope / follow-ups. -->

## Evidence
<!-- Commands and exact results. Always run `python -m pytest tests/test_repo_governance.py -q` and `python -m pytest tests -q`. If template/ changed, include generated-project checks (`check.py --strict`, `sync_indexes.py --check`, `sync_agents.py --check`, `eval_harness.py --verify-fixtures`, `unittest`). -->

## Decisions only the owner can make
<!-- Numbered choices or trade-offs needing owner sign-off. Write "None." if there are none. -->
1.

## Checklist
- [ ] Harness & judges check (rule 3): list any protected harness/CI files or existing test/grader files touched, or write `none`:
- [ ] Independent review done by (a reviewer session that did not write this PR, rule 4):
- [ ] This description matches the final head (`<short-sha>`)
