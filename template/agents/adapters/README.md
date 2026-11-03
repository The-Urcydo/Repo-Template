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
| `cursor` | disabled | `.cursor/rules/00-repo.mdc`, `.cursor/rules/role-<role>.mdc` | One short always-on pointer to `AGENTS.md`, plus each role charter as an agent-requested rule. `AGENTS.md` itself is not copied, so Cursor never loads it twice |
| `copilot` | disabled | `.github/copilot-instructions.md` | A short pointer to `AGENTS.md` in the path Copilot reads repository instructions from |

Codex and most other agent tools read `AGENTS.md` and the plain Markdown in `agents/` directly; nothing is generated for them. Gemini CLI reads `GEMINI.md` by default: set `context.fileName` to `["AGENTS.md", "GEMINI.md"]` in `.gemini/settings.json` (or tell it to read `AGENTS.md`). No Gemini adapter is shipped; this setting is the supported path.

## Commands

```
python3 tools/sync_agents.py            # regenerate
python3 tools/sync_agents.py --check    # fail if generated files differ from their source (CI runs this via check.py)
```

`manifest.json` records a hash of every generated file. The sync tool refuses to overwrite a file it did not generate, and removes generated files whose source disappeared.

## Turn a target on or off

Set `"enabled"` to `true` or `false` for `claude`, `cursor` or `copilot` in `targets.json`, then run `python3 tools/sync_agents.py`. Turning a target off removes the files it generated (and any folder left empty). To manage a tool's files yourself, copy what you need from `agents/` first (for Claude Code: each `agents/roles/<role>/ROLE.md` and every skill folder, shared and per role, into `.claude/`), then set `enabled` to false so the sync tool leaves them alone. The sync tool never overwrites a file it did not generate: it reports `SKIPPED` and exits 1.

An adapter file does not make a module: `.github/copilot-instructions.md` exists without the `github` module, and cutting that module leaves it in place.

## Add another target

1. Add an entry to `targets.json` (name, `enabled`, output paths), disabled by default.
2. In `tools/sync_agents.py`, add an `_<tool>_outputs()` builder and list it in `expected_outputs()`. Reuse `_role_brief()` for role text and prefer a short pointer to `AGENTS.md` over a copy of it.
3. Add a unit test in `tools/tests/`.
4. Record why in an ADR (`python3 tools/new_adr.py "Support <tool> adapter"`).
