---
title: Source code
type: meta
status: placeholder
summary: Product source code lives here; replace this placeholder with the real layout when the first code lands.
owner_role: builder
---
# src/

Placeholder. Put the product's source code here (single-codebase layout).

When the first real code lands (a placeholder does not count):
1. Put the build, test and run commands in the root `AGENTS.md`. The human owns that file: unless told to edit it, propose them with `python3 tools/question.py ask` and put the commands in `--recommended`.
2. Replace this file's front matter `status` with `active` and describe the actual layout in one short paragraph.
3. Add a short `AGENTS.md` in this folder only if it has conventions an agent cannot discover from the code.

Prefer a workspace layout (`apps/`, `packages/`)? Choose it when generating the template, or move the code and update the folder READMEs.
