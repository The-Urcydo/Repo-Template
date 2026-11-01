---
name: verify-work
description: Independently verifies a finished work item against its brief and writes review.md with evidence. Use when acting as the reviewer, or when asked to review, verify, or sign off on work someone else built.
---
# Verify work

**Role:** reviewer.

You must not be the role that built the item. If you were, stop and hand it to a fresh session.

1. Read `work/items/<id>/brief.md` first, then `handoff.md`, then the diff. Do not start from the builder's summary.
2. Run the checks yourself:
   ```
   python3 tools/check.py
   <the project's test command>
   ```
3. For each acceptance criterion: verify it and record the evidence (command, output, file path). Also check that nothing outside the brief changed, accepted ADRs are respected, and file ownership was respected.
4. Create `review.md` with `python3 tools/item_file.py <id> review`, then fill it: a verdict (approve / changes requested / reject), per-criterion results, and findings ranked blocker, major, minor. Each finding says what, where, why it matters and a recommended fix.
5. Move the item:
   ```
   python3 tools/transition.py <id> verified --evidence "<what you ran>" --next "update docs and changelog"
   python3 tools/transition.py <id> in-progress --owner builder --next "fix findings in review.md"   # if changes requested
   ```
6. Do not fix findings yourself.

Details and severity definitions: `agents/protocols/review.md`.
