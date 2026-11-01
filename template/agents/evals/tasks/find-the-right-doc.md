---
id: find-the-right-doc
role: architect
tests: navigation and the ADR tool
---
# Find the right doc

## Prompt

"We chose SQLite over PostgreSQL last week for the prototype. Make sure that is recorded where future agents will find it."

## Expected

- Reads `AGENTS.md`, then `docs/INDEX.md`; does not scan the whole repo.
- Checks the Decisions section for related ADRs before writing.
- Creates the record with `python3 tools/new_adr.py` (number allocated by the tool).
- Fills context, at least two options, the outcome and consequences; writes a one-sentence summary.
- Runs `python3 tools/check.py` at the end.

## Must not

- Create a decision file by hand or guess an ADR number.
- Put the decision in a place that is not `docs/decisions/` (a README, a comment, a work item).
- Edit an existing accepted ADR's outcome.

## Scoring

Pass if the ADR exists with a valid number, front matter and options, and `check.py` passes. Fail otherwise.
