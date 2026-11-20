# Handoff to Agents-Skills-Roles-Oriented

Source: Repo-Template, item 3b (2026-11-20). For the owner of
[Agents-Skills-Roles-Oriented](https://github.com/The-Urcydo/Agents-Skills-Roles-Oriented) to triage.
Repo-Template's standing rule forbids editing `template/agents/`, so these two items are handed off rather than
fixed here. This file is maintainer-only and does not ship to generated projects.

## 1. Stale line in the adapters README

`template/agents/adapters/README.md:53` in Repo-Template still says:

> 3. Add a unit test in `tools/tests/`.

Since item 4b (PR #91, 2026-11-20) generated projects no longer ship `tools/tests`: the two tool-test files live at
Repo-Template's root in `tool-tests/`, and the root suite copies them into a generated project before running them.
The "add another target" step in the adapters README should point at the owning repo's own test folder instead of a
path that no longer exists in generated projects. Suggested replacement:

> 3. Add a unit test under the repo's own test folder (`tool-tests/` in this template, `tests/` in a generated project).

Please fix it in the source repo; Repo-Template will pick it up through the usual harness sync.

## 2. Add an `.agents/skills` adapter target (idea)

Some agent tools read skills from a repository-local `.agents/skills/` folder. The harness already has adapters that
render `agents/skills/` and `agents/roles/<role>/skills/` into a tool's native layout (Claude Code, Cursor, Copilot,
Gemini CLI). An `.agents/skills` target would render the same source into `.agents/skills/` for tools that expect that
convention — as an opt-in target in `agents/adapters/targets.json`, disabled by default, with a short pointer to
`AGENTS.md` rather than copies of it. As with any new target, it needs an `expected_outputs()` builder in
`tools/sync_agents.py`, a unit test and an ADR in the owning repo.

Repo-Template cannot add it from its side because it would mean editing `template/agents/`. If the owning repo adds
the target, Repo-Template can then sync and enable it in a follow-up PR.

## Context: cross-tool claim re-verified in item 3b

The official docs were re-read before the README fix:

- Codex, *Custom instructions with AGENTS.md*: https://developers.openai.com/codex/guides/agents-md/
- OpenCode, *Instructions*: https://opencode.ai/docs/instructions/

Both tools discover `AGENTS.md` files (global, root and nested) and combine them as instructions. Neither loads an
`agents/` folder automatically. Repo-Template's README and shipped how-to now say so; `agents/` is reached through the
pointers in `AGENTS.md`.
