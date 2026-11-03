---
title: Write an ADR
type: how-to
status: active
summary: Record a significant decision, or supersede an earlier one, with the ADR tool.
---
# Write an ADR

Goal: a decision record a future reader can trust without asking anyone.

Write one when a decision has real alternatives, is costly to reverse, or will surprise a future reader. Skip it for small reversible choices; note those in the work item's handoff.

## Steps

1. Skim `docs/INDEX.md` (section Decisions) for related ADRs. Accepted ones are binding.
2. Create it: `python3 tools/new_adr.py "Use PostgreSQL for storage"`. The file lands in `docs/decisions/` with the next number.
3. Fill the template: context and problem, decision drivers, at least two options with pros and cons, the outcome with its reason, consequences (good and bad), and a one-sentence `summary` in the front matter.
4. If the human already made the decision (in chat or in a handoff), record it as `accepted` and say where it was made. Otherwise leave it `proposed` and ask the human to accept it if it is significant, costly or irreversible: `python3 tools/question.py ask "Accept ADR NNNN: <title>?" --asked-by architect --recommended accept --if-no-answer "stays proposed; dependent work waits" --cost "medium: <what a wrong call costs>"`. When the answer is yes, set `status: accepted` in the ADR. Smaller decisions can start as `accepted`: `python3 tools/new_adr.py "Title" --status accepted`.
5. List docs the decision makes stale in the work item's handoff for the scribe, or under Consequences in the ADR when there is no item.
6. Run `python3 tools/check.py`.

## Changing a decision

Never edit an accepted ADR's outcome. Supersede it: `python3 tools/new_adr.py "Switch to SQLite" --supersedes 0007`. The old ADR becomes `superseded` and links forward; the new one links back.
