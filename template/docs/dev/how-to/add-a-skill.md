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
3. Write the body as concrete numbered steps with the exact commands. Keep it under 500 lines (under about 5,000 tokens). Move long material into `references/` files one level deep, and scripts into `scripts/`.
4. Regenerate and verify: `python3 tools/sync_indexes.py && python3 tools/sync_agents.py && python3 tools/check.py`. The check validates the name (and that it is unique), the description and the size.
5. Test it: start a fresh session and give it a task the description should match. If it does not load, sharpen the description.

## Examples

| Skill | Lane | Why |
|---|---|---|
| `write-doc` | `agents/skills/` | any role that owns a docs folder uses it |
| `write-handoff` | `agents/skills/` | any role holding an item uses it |
| `merge-work` | `agents/skills/` | whoever holds the owner's merge grant uses it; owner-invoked (`disable-model-invocation: true`) because merging changes the shared branch |
| `verify-work` | `agents/roles/reviewer/skills/` | only the reviewer verifies work |
| `record-decision` | `agents/roles/architect/skills/` | only the architect records ADRs |

Skills are procedures, not knowledge. If the content describes how things are (not how to do something), it belongs in `docs/` instead.
