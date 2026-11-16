---
title: Split the repo by volatility
type: decision
status: accepted
summary: Separate durable knowledge (docs), volatile state (work) and the agent harness (agents) so each has one lifecycle and one owner.
date: 2026-11-01
decision_makers: human
supersedes: []
---
# 0001: Split the repo by volatility

## Context and problem statement

In a repo worked by one human and many agents, the usual failure is mixing things that change daily (plans, handoffs, scratch research) with things that must stay true (architecture, reference). Docs rot, agents trust stale notes, and pruning is risky because nothing is clearly disposable. How should the repository be organized so it stays easy to grow and easy to cut?

## Decision drivers

- Each folder should have one lifecycle, one reader intent and one owner
- Agents need a hard rule for where anything goes
- Volatile state must be prunable without touching knowledge
- Low token cost: agents should load only what a task needs

## Considered options

- Flat: `AGENTS.md`, `docs/`, `src/` only
- Everything agent-related under one tool's dotfolder (`.claude/`)
- Layered by volatility: `docs/` (durable), `work/` (volatile), `agents/` (harness), plus code

## Decision outcome

Chosen option: "Layered by volatility", because it gives agents an unambiguous placement rule and lets `work/` be archived or moved without risk to `docs/`.

### Consequences

- Good: clear ownership; prunable state; indexes per layer keep context small.
- Bad: three concept folders to learn up front; a trivial task still touches `work/` (mitigated by single-file light items).

### Confirmation

`python3 tools/check.py` enforces front matter in `docs/`, handoff rules in `work/`, and folder ownership via each folder's README.

## More information

Rationale in prose: `docs/dev/explanation/design-rationale.md`.
