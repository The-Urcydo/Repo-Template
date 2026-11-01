---
title: Product docs
type: index
status: active
summary: Optional module holding the product vision, requirements and roadmap that planners and architects work from.
owner_role: planner
---
# docs/product/

Module `product`. The "what and why" of the product, kept separate from how it is built. Planners read it to write briefs; architects read it to judge trade-offs.

| Page | Holds |
|---|---|
| `vision.md` | Who it is for, the problem, what success looks like |
| `requirements.md` | What the product must do and the limits it must respect |
| `roadmap.md` | What is planned, in what order, and what is deliberately not planned |

Cut this module with `python3 tools/remove_module.py product` if the project has no product framing.
