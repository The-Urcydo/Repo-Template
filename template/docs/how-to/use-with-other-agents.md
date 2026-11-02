---
title: Use the repo with other agent tools
type: how-to
status: active
summary: Run DeepSeek-based agents, Codex, Cursor, Gemini CLI or Claude Code against the same harness, and add native adapters if a tool needs them.
---
# Use the repo with other agent tools

Goal: any agent, from any vendor, follows the same roles and protocols.

## The universal way (works with every tool)

1. Point the agent at `AGENTS.md`. Most coding tools read it automatically; for the rest, put "read AGENTS.md first" in the system prompt.
2. Tell it its role: "You are the builder. Read `agents/roles/builder.md`."
3. Give it the work item: "Your item is `<id>`; start from its `handoff.md`."
4. Make sure it can run shell commands, because every action goes through `python3 tools/...`.

Roles, protocols and skills are plain Markdown, so no tool-specific format is required.

## Claude Code

Works out of the box: `tools/sync_agents.py` generates `.claude/agents/<role>.md` (subagents), `.claude/skills/` (skills) and a `CLAUDE.md` shim next to every `AGENTS.md`. Claude Code reads `CLAUDE.md` instead of `AGENTS.md` when both exist, so the shim imports the real file with `@AGENTS.md`.

Prefer to manage `.claude/` yourself? Set `"enabled": false` for `claude` in `agents/adapters/targets.json`, run `python3 tools/sync_agents.py` (it removes what it generated), then copy `agents/roles/*.md` and `agents/skills/*` as you like.

## Cursor and GitHub Copilot

Built-in adapters are shipped disabled by default in `agents/adapters/targets.json`. Set `"enabled": true` under `"cursor"` (generates `.cursor/rules/*.mdc`) or `"copilot"` (generates `.github/copilot-instructions.md`) and run `python3 tools/sync_agents.py`.

## Another tool with its own folder format

1. Add a target in `agents/adapters/targets.json`.
2. Extend `expected_outputs()` in `tools/sync_agents.py` to render that tool's files from `agents/roles/` and `agents/skills/`.
3. Add a unit test and an ADR. Steps in `agents/adapters/README.md`.

## Tips for weaker or smaller models

- Give one role and one item per session; do not load the whole repo.
- Quote the exact command to run; the tools print the rule they enforce when they refuse.
- Always run `python3 tools/check.py` at the end and paste its last line into the handoff as evidence.
