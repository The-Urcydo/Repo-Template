---
title: Add an agent skill
type: how-to
status: active
summary: Create a reusable skill in the open Agent Skills format, under the role that uses it or in agents/skills when shared, and generate its adapter copies.
---
# Add an agent skill

Goal: a procedure agents load only when a task matches it, so it costs almost no context otherwise.

## Steps

1. Pick where it lives. Only one role uses it: `agents/roles/<role>/skills/<name>/`. Several roles, or anyone: `agents/skills/<name>/`. Create that folder with a `SKILL.md` in it. The name must be unique across both places, because `.claude/skills/` is flat. If the role's `skills/` folder holds only a `.gitkeep`, delete the `.gitkeep`.
2. Front matter, per the Agent Skills specification:
   - `name`: 1 to 64 characters; lowercase letters, digits and single hyphens; no leading or trailing hyphen; **equal to the folder name**.
   - `description`: 1 to 1024 characters. Say what the skill does **and when to use it**; this is the only part loaded at startup.
   - Optional, Claude Code only: `disable-model-invocation: true` (not in the specification; other tools ignore it) keeps the model from starting the skill by itself, so only a person's request does. Use it for actions that change shared state, like `merge-work`.
3. Write the body as concrete numbered steps with the exact commands. Write the method, not the routing: a command that changes who owns the item or what its status is stays in the role's `ROLE.md`, and the skill points to it. Keep it under 500 lines (under about 5,000 tokens). Move long material into `references/` files one level deep, and scripts into `scripts/`.
4. In the role's `ROLE.md`, add or keep a pointer to the skill (a Procedure line, or the step that uses it), so an agent that adopts the role reads it. Do not copy the steps into the charter.
5. Regenerate and verify: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py && python3 tools/check.py`. The check validates the name (and that it is unique), the description and the size. For Claude Code the sync also lists the role's own skills in its subagent's `skills:` (`agents/adapters/README.md`).
6. Test it: start a fresh session and give it a task the description should match. If it does not load, sharpen the description.

## Examples

| Skill | Lane | Why |
|---|---|---|
| `write-doc` | `agents/skills/` | any role that owns a docs folder uses it |
| `write-handoff` | `agents/skills/` | any role holding an item uses it |
| `merge-work` | `agents/skills/` | whoever holds the owner's merge grant uses it; owner-invoked (`disable-model-invocation: true`) because merging changes the shared branch |
| `verify-work` | `agents/roles/reviewer/skills/` | only the reviewer verifies work; where the item goes next stays in the reviewer's `ROLE.md` |
| `record-decision` | `agents/roles/architect/skills/` | only the architect records ADRs |

## Charter or skill?

- Routing, limits, and when the role runs: the charter (`ROLE.md`). An agent always reads it, so put there what must never be skipped.
- The method for one task, with templates and examples: a skill. It may be long.
- A fact needed by both: state the rule in the charter and have the skill point to it. A command is written in one of the two, never both.
- A role that is mostly routing (it owns a status and runs `transition.py`) usually needs no skill. A role that produces an artifact and runs no status commands usually does.

Skills are procedures, not knowledge. If the content describes how things are (not how to do something), it belongs in `docs/` instead.
