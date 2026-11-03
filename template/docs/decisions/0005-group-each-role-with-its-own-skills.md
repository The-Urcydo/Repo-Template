---
title: Group each role with its own skills
type: decision
status: accepted
summary: Each role is a folder holding its ROLE.md charter and the skills exclusive to that role; skills shared by several roles stay in agents/skills/.
date: 2026-11-04
decision_makers: human
supersedes: []
---
# 0005: Group each role with its own skills

## Context and problem statement

`agents/roles/` held the charters as flat files and `agents/skills/` held every skill in one folder, so nothing in the tree showed which skill belongs to which role. Two of the six skills name a single role (`record-decision`: architect, `verify-work`: reviewer). The other four are used by several roles or by anyone (`new-work-item`, `write-doc`, `write-handoff`, `tailor-template`). As skills are added the flat folder gets harder to scan, and a role cannot be read or cut as one unit. How should roles and their skills be laid out?

## Decision drivers

- A role and the skills only it uses should be found together
- Cutting an optional role (the `security` module) should mean deleting one folder
- Skills keep the open Agent Skills format, and `.claude/skills/` stays flat for Claude Code
- Still plain, tool-neutral Markdown: any agent can be told "read your `ROLE.md`"
- One rule an agent can apply without judgment

## Considered options

- Keep the flat layout and list each role's skills in its charter front matter
- Role bundles: `agents/roles/<role>/ROLE.md` plus `skills/` for skills only that role uses; shared skills stay in `agents/skills/`
- Role bundles with every skill under a role, shared ones under a pseudo-role folder

## Decision outcome

Chosen option: "Role bundles; shared skills stay in `agents/skills/`", because the folder tree shows which skills are exclusive to a role, cutting an optional module role is deleting one folder, and one rule decides where a skill goes: exactly one role uses it, it lives under that role; several roles or anyone use it, it lives in `agents/skills/`.

The charter file is `ROLE.md`. It mirrors `SKILL.md` and avoids `README.md`, which this repo uses to declare folder ownership (`owner_role`). Every role keeps a `skills/` folder, held by a `.gitkeep` until its first skill arrives. `protocols/`, `evals/` and `adapters/` stay flat: protocols are the rules between roles, and `evals` is a module that is cut as one folder.

### Consequences

- Good: the tree shows which skills are exclusive to a role; shared skills stay visible in `agents/skills/`; the generated `ROSTER.md` lists both; cutting the `security` module removes its charter and empty skills folder with one folder; the generated `.claude/` layout is unchanged, so Claude Code sees no difference.
- Bad: a skill's place must be revisited when a second role starts using it (moving it is a rename); skill names must be unique across both places because `.claude/skills/` is flat; projects that updated from `v0.1.0` see the charters and two skills move, Copier may report conflicts where they hand-edited a charter, and they must run the sync tools after the update to rebuild the generated indexes.
- Neutral: the charter path quoted inside each generated subagent file changes from `agents/roles/<role>.md` to `agents/roles/<role>/ROLE.md`.

### Confirmation

`python3 tools/check.py` fails on a role folder without `ROLE.md`, a role folder without `skills/`, a `role` that differs from its folder name, an old flat `agents/roles/<role>.md`, a skill name used twice, and a `DEFAULT_OWNER` that names a missing role. The template's own tests generate every layout and module combination, assert that every role is a bundle with a `skills/` folder, assert the generated roster lists role and shared skills, and assert that cutting `security` removes the whole role folder.

## More information

`agents/AGENTS.md` (the rule), `agents/README.md`, `docs/how-to/add-a-role.md` (including "Removing a role"), `docs/how-to/add-a-skill.md`. Related: ADR 0002 (tool-neutral `agents/`) and ADR 0004 (cuttable modules); this decision changes neither.

Revisit the folder rule when a skill changes lanes twice, or when the repo passes roughly 15-20 skills. At that point, consider an explicit `audience:`/`roles:` field in `SKILL.md` or a generated skill matrix instead of relying on folder placement alone.
