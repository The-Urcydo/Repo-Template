---
title: Adapters
type: meta
status: active
summary: How tool-specific agent files are generated from the tool-neutral harness, and how to add another tool.
owner_role: architect
---
# agents/adapters/

`agents/` is the source of truth. Some tools need files in their own locations; those are generated, never hand-edited.

| Target | Default | Generated files | Why |
|---|---|---|---|
| `claude` | enabled | `.claude/agents/<role>.md`, `.claude/skills/<name>/`, a `CLAUDE.md` containing `@AGENTS.md` beside every `AGENTS.md` | Claude Code loads subagents and skills from `.claude/`, and reads `CLAUDE.md` instead of `AGENTS.md` when both exist, so each shim imports the real file |
| `cursor` | disabled | `.cursor/rules/00-repo.mdc`, `.cursor/rules/role-<role>.mdc` | Wraps `AGENTS.md` as an always-on rule and role charters as agent-requested `.mdc` rules |
| `copilot` | disabled | `.github/copilot-instructions.md` | Mirrors `AGENTS.md` into GitHub Copilot's repository instruction path |

Other agent tools (DeepSeek-based agents, Codex, Gemini CLI) read `AGENTS.md` and the plain Markdown in `agents/` directly; nothing needs to be generated for them.

## Commands

```
python3 tools/sync_agents.py            # regenerate
python3 tools/sync_agents.py --check    # fail if generated files differ from their source (CI runs this via check.py)
```

`manifest.json` records a hash of every generated file. The sync tool refuses to overwrite a file it did not generate, and removes generated files whose source disappeared.

## Toggle an adapter on or off

Set `"enabled": true` or `false` for `claude`, `cursor`, or `copilot` in `targets.json`, then run `python3 tools/sync_agents.py`. Disabling a target cleanly removes the files it generated.

## Add another target

1. Add an entry to `targets.json` (name, output directories).
2. In `tools/sync_agents.py`, extend `expected_outputs()` to render that tool's files from `agents/roles/` and `agents/skills/`.
3. Add a unit test in `tools/tests/`.
4. Record why in an ADR (`python3 tools/new_adr.py "Support <tool> adapter"`).
