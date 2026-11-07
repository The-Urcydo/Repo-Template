<!-- Follow AGENTS.md and agents/skills/merge-work/SKILL.md. One work item per PR. -->
## Work item

Item id: `<!-- e.g. 2026-11-01-add-login -->`

## What changed and why

<!-- Short summary of files and behavior changed. Mention the ADR if a decision was recorded, and note anything intentionally out of scope. -->

## Decisions only the human can make

<!-- Numbered open questions or trade-offs (queued in `work/HUMAN.md` via `python3 tools/question.py ask`), or write "None." -->
1.

## Evidence

<!-- Paste exact commands and results from the current head commit. -->
- [ ] `python3 tools/check.py --strict` passes
- [ ] Project tests pass (and `python3 -m unittest discover -s tools/tests` if `tools/` changed)
- [ ] Generated files in sync (`python3 tools/sync_indexes.py --check && python3 tools/sync_agents.py --check`)
- [ ] Docs and `CHANGELOG.md` updated where behavior changed

## Merge checklist

- [ ] Item is `verified` (or `done`) with independent review in `review.md` (`built_by` != `verified_by`)
- [ ] Judges & harness check (`merge-work` step 3): list any changes to existing tests, `tools/`, `.github/`, `agents/`, or `AGENTS.md` (requires explicit human approval), or write `none`:
- [ ] Description and evidence match the final head (`<short-sha>`)
