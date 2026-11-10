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
| `gemini` | disabled | `.gemini/settings.json` | Configures `context.fileName` to `["AGENTS.md", "GEMINI.md"]` so Gemini CLI reads `AGENTS.md` directly |

Codex and most other agent tools read `AGENTS.md` and the plain Markdown in `agents/` directly; nothing is generated for them.

## Commands

```
python3 tools/sync_agents.py            # regenerate
python3 tools/sync_agents.py --check    # fail if generated files differ from their source (CI runs this via check.py)
```

`manifest.json` records a hash of every generated file. The sync tool refuses to overwrite a file it did not generate, and removes generated files whose source disappeared.

## Claude Code: tool limits, models and descriptions

Three optional inputs shape the generated `.claude/agents/<role>.md` front matter. Cursor, Copilot and Gemini ignore the first two.

| Input | Where | Effect |
|---|---|---|
| `access: read-only` | a role's `ROLE.md` | Adds `disallowedTools` from the `claude.disallowed_tools` table in `targets.json` (shipped: `Edit` and `NotebookEdit`). No `access`, or `full`, adds nothing |
| `claude.models` | `targets.json` | Maps a role name to a model alias or id and adds `model:` for that role only. Shipped empty: every role inherits the session's model. Model names live here, never in `ROLE.md` |
| `use_when` | a role's `ROLE.md` | Completes "Use when ..." in the subagent and Cursor rule description. Without it the description says "Use when a work item's handoff owner_role is `<role>`", which fits a role that is handed items and never fits a role that is only called |

`disallowedTools` guards against accidents: it stops a read-only role from editing work it does not own in place. It is not a security boundary. These roles still need `Write` to fill the item file `tools/item_file.py` creates and to write their owned files, and a shell can change files anyway. Command-level limits belong in Claude Code permission rules or hooks, which this tool does not generate. `check.py` fails on an unknown `access` value, an unknown role in `models`, a tool name that is not a plain name such as `Edit`, and a `disallowed_tools` entry for `full` (the default level cannot restrict).

## Turn a target on or off

Set `"enabled"` to `true` or `false` for `claude`, `cursor`, `copilot` or `gemini` in `targets.json`, then run `python3 tools/sync_agents.py`. Turning a target off removes the files it generated (and any folder left empty). To manage a tool's files yourself, copy what you need from `agents/` first (for Claude Code: each `agents/roles/<role>/ROLE.md` and every skill folder, shared and per role, into `.claude/`), then set `enabled` to false so the sync tool leaves them alone. The sync tool never overwrites a file it did not generate: it reports `SKIPPED` and exits 1.

An adapter file does not make a module: `.github/copilot-instructions.md` exists without the `github` module, and cutting that module leaves it in place.

## Add another target

1. Add an entry to `targets.json` (name, `enabled`, output paths), disabled by default.
2. In `tools/sync_agents.py`, add an `_<tool>_outputs()` builder and list it in `expected_outputs()`. Reuse `_role_brief()` for role text and prefer a short pointer to `AGENTS.md` over a copy of it.
3. Add a unit test in `tools/tests/`.
4. Record why in an ADR (`python3 tools/new_adr.py "Support <tool> adapter"`).
