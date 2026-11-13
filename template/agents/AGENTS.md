# agents/ rules

- `agents/` is the tool-neutral source of truth for how agents work. Adapter outputs (`.claude/`, `.cursor/rules/`, `CLAUDE.md` shims, `.github/copilot-instructions.md`, `.gemini/settings.json`) and `ROSTER.md` are generated from it: edit here, then run `python3 tools/sync_indexes.py && python3 tools/sync_agents.py`.
- Changes anywhere under `agents/` change every agent's behavior. They need the human's approval before merging.
- A role is a folder `agents/roles/<role>/`. Its charter is `ROLE.md`: mission, reads, item files, never, done_when, escalate_when, and optionally `access` and `use_when` (`docs/dev/reference/front-matter.md`); `role:` equals the folder name. Folder ownership is declared in each folder's `README.md` (`owner_role`), not in the charter.
- A skill is a folder `<name>/SKILL.md` following the open Agent Skills format: `name` equals the folder, `description` says what it does and when to use it. Keep `SKILL.md` under 500 lines; put detail in `references/`.
- Charter and method (ADR 0009): `ROLE.md` holds the routing (every command that changes who owns an item or its status, with its condition) and the limits. A skill holds the method (read order, checks, templates, commands that do not move the item). A fact lives in one of them, never both. A role that is mostly routing needs no skill; a role with a method of its own gets one. The Claude adapter preloads a role's own skills into its subagent.
- Where a skill lives: only one role uses it, `agents/roles/<role>/skills/<name>/`; several roles or anyone use it, `agents/skills/<name>/`. A skill name is unique across both places (`.claude/skills/` is flat). A role with no skill keeps an empty `skills/` folder holding a `.gitkeep`; delete the `.gitkeep` when its first skill arrives.
- Keep every instruction concrete and testable. Delete anything an agent could discover by reading the repo.
- Never put secrets or personal paths in anything under `agents/`.
