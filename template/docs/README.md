---
title: Docs
type: meta
status: active
summary: How the documentation is organized (Diataxis plus decision records), who owns it, and how agents and humans find things.
owner_role: scribe
---
# docs/

Docs describe what is true **now**. History belongs in ADRs, work items and git.

Start at `INDEX.md` (generated, one line per doc). Open only what the task needs.

| Folder | Reader's need | Write it like |
|---|---|---|
| `tutorials/` | "Teach me": learn by doing | A lesson: guaranteed to work, no digressions |
| `how-to/` | "Help me do X" | A recipe: goal, steps, done |
| `reference/` | "What exactly is Y?" | A fact sheet: accurate, complete, no opinions |
| `explanation/` | "Why is it this way?" | A discussion: context, trade-offs |
| `decisions/` | "Why did we decide that?" | An ADR: one decision, its options and consequences |

Optional module folders may sit beside these (product, operations, security, release); see `reference/modules.md`.

## Rules

- One page, one type. A page that needs two becomes two pages that link.
- Every page has front matter with a one-sentence `summary` (schema: `reference/front-matter.md`). The index is built from it.
- `_templates/` holds the starting point for each type; `python3 tools/new_doc.py` uses them.
- Placeholders (`status: placeholder`) are deliberate gaps. Fill them or delete them; `python3 tools/check.py --stubs` lists them.
- The scribe owns this folder except `decisions/`, which the architect owns. Details: `docs/AGENTS.md`.
