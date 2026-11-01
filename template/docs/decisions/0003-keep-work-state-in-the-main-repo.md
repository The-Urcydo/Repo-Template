---
title: Keep work state in the main repo
type: decision
status: accepted
summary: Work items, the human queue and research notes are committed in the main repo under work/, not on a separate branch or repository.
date: 2026-11-01
decision_makers: human
supersedes: []
---
# 0003: Keep work state in the main repo

## Context and problem statement

Agents write plans, handoffs and research continuously. Should that state live beside the code, or on a separate branch or repository to keep code history clean?

## Decision drivers

- One checkout is enough for an agent to understand the project
- Link code changes to the reasoning behind them
- Simplicity for a single human
- Acceptable commit noise

## Considered options

- `work/` in the main repo
- `work/` on a separate branch or repo

## Decision outcome

Chosen option: "`work/` in the main repo", because one checkout gives agents everything and the reasoning sits next to the change. Starting simple is cheap: moving `work/` out later is a small change because every tool path is relative to the repo root.

### Consequences

- Good: single checkout; handoffs and code can be reviewed together.
- Bad: noisier commit history; possible merge conflicts when many agents write at once (mitigated by one folder per item, single-writer files and locked tools); internal notes ship with the repo if it is ever made public (git-ignore scratch files, review before publishing).

### Confirmation

Revisit if `git log` on code becomes hard to read or conflicts in `work/` become frequent.

## More information

`work/README.md`, `agents/protocols/parallel-work.md`.
