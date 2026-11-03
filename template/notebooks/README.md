---
title: Notebooks
type: meta
status: placeholder
summary: Exploratory notebooks and experiments; promote reusable code into src/ and durable findings into docs/.
owner_role: researcher
---
# notebooks/

Placeholder (`data-ml` layout). Put exploratory Jupyter/Marimo notebooks and experiment scripts here.

Rules worth keeping from the start:
- Name notebooks with a number or date prefix (`01-explore-latency.ipynb`) so their order is clear.
- Never import from a notebook into production code; promote reusable functions into `src/` (via a builder handoff) and durable conclusions into `docs/`.
- Notebooks may read `data/`, but schema, pipeline and data-contract changes go through the builder who owns that folder.
- Strip large output cells or credentials before committing. When the first notebook lands, set this file's `status` to `active`.
