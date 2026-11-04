---
title: Docs
type: meta
status: active
summary: How the documentation is organized (by audience, then by Diataxis type, plus decision records), who owns it, and how agents and humans find things.
owner_role: scribe
---
# docs/

Docs describe what is true **now**. History belongs in ADRs, work items and git.

Start at `INDEX.md` (generated, one line per doc, grouped by audience). Open only what the task needs.

Docs are grouped by who reads them, then by what the reader needs:

| Folder | Audience | Holds |
|---|---|---|
| `dev/` | Contributors, human or agent | How the repo works and how to change it, in the four kinds below |
| `user/` | End users of what you build | The same four kinds, written for people who use the product (a placeholder until the first user-facing feature) |
| `decisions/` | Everyone | ADRs, "Why did we decide that?": one decision, its options and consequences |

Inside `dev/` and `user/`, one folder per kind (Diataxis):

| Folder | Reader's need | Write it like |
|---|---|---|
| `tutorials/` | "Teach me": learn by doing | A lesson: guaranteed to work, no digressions |
| `how-to/` | "Help me do X" | A recipe: goal, steps, done |
| `reference/` | "What exactly is Y?" | A fact sheet: accurate, complete, no opinions |
| `explanation/` | "Why is it this way?" | A discussion: context, trade-offs |

Optional module folders sit beside these, one audience each: `product/` (product and design), `operations/` and `release/` (ops), `security/` (security). See `dev/reference/modules.md`.

## Rules

- One page, one type. A page that needs two becomes two pages that link.
- Every page has front matter with a one-sentence `summary` (schema: `dev/reference/front-matter.md`). The index is built from it.
- A folder implies its audience. To list a page under another audience, add an `audience:` key (`dev`, `user`, `product`, `ops` or `security`); the index regroups it, the file stays where it is.
- `_templates/` holds the starting point for each type; `python3 tools/new_doc.py` uses them.
- Placeholders (`status: placeholder`) are deliberate gaps. Fill them or delete them; `python3 tools/check.py --stubs` lists them.
- The scribe owns this folder except `decisions/`, which the architect owns. Details: `docs/AGENTS.md`.
