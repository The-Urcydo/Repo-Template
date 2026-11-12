---
name: verify-work
description: Independently verifies a finished work item against its brief and writes review.md with evidence. Use when acting as the reviewer, or when asked to review, verify, or sign off on work someone else built.
---
# Verify work

**Role:** reviewer.

You must not be the role that built the item. If you were, stop and hand it to a fresh session.

1. Read `work/items/<id>/brief.md` first, then `handoff.md`, then the diff. Do not start from the builder's summary.
2. Read the brief's Security review section before any verdict. `required`, the item is a full item (a folder), `agents/roles/security/` exists and no `security-review.md` yet: hand the item to the security role and stop (it runs in a separate session):
   ```
   python3 tools/transition.py <id> --owner security --next "Security: review the diff, write security-review.md, hand back to the reviewer"
   ```
   When it comes back, read `security-review.md` first: a blocker or major finding means `changes requested`. `not needed`, or no such section: carry on. If the role is not installed or the item is light (no folder for `security-review.md`), do not hand over: follow step 2 of the reviewer's `ROLE.md`.
3. Run the checks yourself:
   ```
   python3 tools/check.py
   <the project's test command>
   ```
4. For each acceptance criterion: verify it and record the evidence (command, output, file path). Also check that nothing outside the brief changed, accepted ADRs are respected, and file ownership was respected.
5. Create `review.md` with `python3 tools/item_file.py <id> review`, then fill it: a verdict (approve / changes requested / reject), per-criterion results, and findings ranked blocker, major, minor. Each finding says what, where, why it matters and a recommended fix.
6. Move the item. Approved: choose who acts after `verified` from the last line of the builder's Current state in `handoff.md`.
   - `Docs for the scribe: none, behavior unchanged.` and the diff agrees (it changes no behavior, and for each changed path `git grep -n -F "<path>" -- docs` finds no page that describes it): skip the scribe.
     ```
     python3 tools/transition.py <id> verified --by reviewer --owner orchestrator --evidence "<what you ran>" --next "Orchestrator: mark done; no docs or changelog change"
     ```
   - Anything else (the line is missing, lists docs, says behavior changed, or the diff contradicts a `none`): leave the default, the scribe runs. When the diff contradicts a `none`, say what it contradicts in `review.md` and in `--next`. Never rewrite the builder's line.
     ```
     python3 tools/transition.py <id> verified --by reviewer --evidence "<what you ran>" --next "update docs and changelog"
     ```
   - Changes requested:
     ```
     python3 tools/transition.py <id> in-progress --owner builder --by reviewer --next "fix findings in review.md"
     ```
7. Do not fix findings yourself.

Details and severity definitions: `agents/protocols/review.md`.
