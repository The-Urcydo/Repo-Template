# agents/ rules

- `agents/` is the tool-neutral source of truth for how agents work. Adapter outputs (`.claude/`, `.cursor/rules/`, `CLAUDE.md` shims, `.github/copilot-instructions.md`) are generated from it: edit here, then run `python3 tools/sync_agents.py`.
- Changes to roles, skills or protocols change every agent's behavior. They need the human's approval before merging.
- A role file is a charter: mission, reads, item files, never, done_when, escalate_when. Folder ownership is declared in each folder's `README.md` (`owner_role`), not in the role file.
- A skill is a folder `agents/skills/<name>/SKILL.md` following the open Agent Skills format: `name` equals the folder, `description` says what it does and when to use it. Keep `SKILL.md` under 500 lines; put detail in `references/`.
- Keep every instruction concrete and testable. Delete anything an agent could discover by reading the repo.
- Never put secrets or personal paths in anything under `agents/`.
