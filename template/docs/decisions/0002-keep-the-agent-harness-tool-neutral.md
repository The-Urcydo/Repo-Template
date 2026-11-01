---
title: Keep the agent harness tool-neutral in agents/
type: decision
status: accepted
summary: agents/ is the source of truth for roles, protocols and skills; tool-specific files such as .claude/ are generated from it.
date: 2026-11-01
decision_makers: human
supersedes: []
---
# 0002: Keep the agent harness tool-neutral in agents/

## Context and problem statement

The human works with Claude, DeepSeek and other agents. Tools look for agent definitions in their own locations (`.claude/agents`, `.claude/skills`). Where should the canonical roles, protocols and skills live?

## Decision drivers

- Work with several agent products, not one
- Humans should see and review the harness (not hidden in a dotfolder)
- Switching or adding a tool must not mean migrating the harness
- Claude Code should work immediately after clone

## Considered options

- Canonical in `.claude/` (simplest for Claude Code, tool-locked and hidden)
- Canonical in `agents/` with generated adapters
- Duplicate by hand into each tool's folder

## Decision outcome

Chosen option: "Canonical in `agents/` with generated adapters", because it keeps one visible source of truth any agent can read as plain Markdown, while `tools/sync_agents.py` generates `.claude/agents`, `.claude/skills` and `CLAUDE.md` shims so Claude Code works out of the box. Skills follow the open Agent Skills format, so they port as-is.

### Consequences

- Good: no lock-in; adding a tool is a small change to the adapter config and sync tool; drift is caught by `check.py`.
- Bad: an extra generation step; adapters can lag if a tool changes where it looks for files (the adapter layer isolates that change).
- Neutral: copying `agents/` into `.claude/` by hand also works; set the claude target to `enabled: false` first.

### Confirmation

`python3 tools/sync_agents.py --check` (run inside `check.py`) fails on drift between `agents/` and generated files.

## More information

`agents/adapters/README.md`.
