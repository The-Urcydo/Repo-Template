---
title: Infrastructure
type: meta
status: placeholder
summary: Optional module for infrastructure-as-code and environment definitions; replace this placeholder when the first resource is defined.
owner_role: builder
---
# infra/

Module `infra`. Placeholder for infrastructure-as-code (Terraform, Pulumi, Kubernetes manifests, Docker Compose, and similar) and environment definitions.

Rules worth keeping from the start:
- Nothing here is applied to a real environment without the human's approval (`agents/protocols/escalation.md`: production and spend).
- Secrets never live here; reference them by name from a secret manager.
- Each environment gets its own folder under `environments/`.

When the first resource lands, propose how to plan and apply for the root `AGENTS.md` (the human owns it; see `src/README.md`) and set this file's `status` to `active`. Cut this module with `python3 tools/remove_module.py infra`.
