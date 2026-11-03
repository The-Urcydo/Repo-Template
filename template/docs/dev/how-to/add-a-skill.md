---
title: Add an agent skill
type: how-to
status: active
summary: Create a reusable skill in the open Agent Skills format under agents/skills and generate its adapter copies.
---
# Add an agent skill

Goal: a procedure agents load only when a task matches it, so it costs almost no context otherwise.

## Steps

1. Create the folder `agents/skills/<name>/` and the file `SKILL.md` in it.
2. Front matter, per the Agent Skills specification:
   - `name`: 1 to 64 characters; lowercase letters, digits and single hyphens; no leading or trailing hyphen; **equal to the folder name**.
   - `description`: 1 to 1024 characters. Say what the skill does **and when to use it**; this is the only part loaded at startup.
3. Write the body as concrete numbered steps with the exact commands. Keep it under 500 lines (under about 5,000 tokens). Move long material into `references/` files one level deep, and scripts into `scripts/`.
4. Regenerate and verify: `python3 tools/sync_agents.py && python3 tools/check.py`. The check validates the name, the description and the size.
5. Test it: start a fresh session and give it a task the description should match. If it does not load, sharpen the description.

Skills are procedures, not knowledge. If the content describes how things are (not how to do something), it belongs in `docs/` instead.
