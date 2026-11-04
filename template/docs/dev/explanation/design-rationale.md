---
title: Why the repo is organized this way
type: explanation
status: active
summary: The reasoning behind splitting the repo by volatility, keeping the harness tool-neutral, generating indexes, and making parts cuttable.
---
# Why the repo is organized this way

This repo is worked by one human and many AI agents in different roles, over many fresh sessions. That setting breaks the usual assumptions about repositories, so the structure is built around four problems.

## 1. Things that change at different speeds rot each other

Plans, handoffs and scratch research change daily. Architecture, reference and decisions must stay true for months. When they share folders, agents trust stale notes, docs drift, and nobody dares to prune because nothing is clearly disposable. So the repo is split by **volatility**: `docs/` is durable knowledge, `work/` is volatile state, `agents/` is the harness that defines how work happens. Each folder has one lifecycle, one reader intent and one owner. Decision: `docs/decisions/0001-split-the-repo-by-volatility.md`.

## 2. Context is a budget, not a free resource

An agent pays for everything it loads in every session, and long instruction files reduce how well they are followed (see `context-budget.md`). So the design loads in tiers: a short `AGENTS.md` always; one-line-per-doc indexes when needed; the content itself only when a task requires it. Every doc carries a one-sentence `summary` so agents can decide what to open without opening it. Paths are predictable, so agents never have to search.

## 3. Parallel writers need structure, not luck

Many agents write at once. Collisions are prevented by single-writer ownership (a folder's README names its owner role; roles list the item files they exclusively write), one git worktree per agent, and tools that take a lock when allocating shared state such as ADR numbers. The state of every work item lives in a handoff file that a fresh session can trust, guarded by a state machine that refuses unsafe moves (no `done` without independent review and evidence). Details: `ownership-and-handoffs.md`.

## 4. Optional parts must be cuttable

The skeleton ships detailed placeholders so nobody researches the structure again, but a project rarely needs all of them. Optional parts are **modules** with declared paths. Core never links into a module (`check.py` fails if it does), so cutting a module cannot break core. `tools/remove_module.py` deletes the paths, regenerates indexes, and records the cut so template updates do not undo it. Decision: `docs/decisions/0004-deliver-with-copier-and-cuttable-modules.md`.

## What was deliberately not done

- **No tool-specific source of truth.** The harness lives in `agents/` as plain Markdown, with `.claude/` generated from it, because the human uses more than one agent product. Decision: `docs/decisions/0002-keep-the-agent-harness-tool-neutral.md`.
- **No hidden state.** Everything an agent needs is a file in the repo; nothing depends on chat history.
- **No dependencies in the tools.** Standard-library Python only, so any agent can run them anywhere.
- **No directory tree in `AGENTS.md`.** Agents discover structure themselves; the file holds only what they cannot discover.

## Trade-offs accepted

More concepts to learn on day one; a small cost per task for creating a work item (light items reduce it); generated files that must be regenerated; a Python dependency for Copier when creating or updating (not when using) the repo. These are recorded in the ADRs so they can be revisited with evidence.
