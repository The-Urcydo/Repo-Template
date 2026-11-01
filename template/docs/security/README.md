---
title: Security docs
type: index
status: active
summary: Optional module with the threat model and security practices, used by the security role when reviewing changes.
owner_role: security
---
# docs/security/

Module `security`. Includes the `security` role (`agents/roles/security.md`) and the root `SECURITY.md` vulnerability-reporting policy.

| Page | Holds |
|---|---|
| `threat-model.md` | What is protected, who might attack it, the trust boundaries, and the mitigations |

Rules that apply everywhere, module or not: never commit secrets, never paste one into a handoff or chat, and escalate immediately if one is found (`agents/protocols/escalation.md`).

Cut this module with `python3 tools/remove_module.py security`. Doing so also removes the security role and `SECURITY.md`.
