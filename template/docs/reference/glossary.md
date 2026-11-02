---
title: Glossary
type: reference
status: active
summary: Definitions of the terms this repo uses - work item, handoff, role, skill, module, adapter, generated file and more.
---
# Glossary

| Term | Meaning |
|---|---|
| **ADR** | Architecture decision record: one numbered file in `docs/decisions/` capturing a decision, its options and consequences |
| **Adapter** | A tool-specific file (such as `.claude/agents/builder.md` or `.cursor/rules/00-repo.mdc`) generated from the tool-neutral `agents/` folder |
| **Canceled** | Terminal status for a work item that was dropped or rejected without shipping; archived by `tools/archive_item.py` |
| **Core** | Everything that is not an optional module; never depends on a module |
| **Diátaxis** | The documentation framework that splits docs into tutorials, how-to guides, reference and explanation |
| **Evidence** | What proves a claim: a command that was run, a file, a link. "Tests pass" without a command is not evidence |
| **Generated file** | A file rebuilt by a sync tool from its sources (`docs/INDEX.md`, `work/ACTIVE.md`, `.claude/`); never edited by hand |
| **Handoff** | `handoff.md`: the file that carries a work item's state between sessions and roles |
| **Harness** | The `agents/` folder: roles, protocols and skills that tell agents how to work |
| **Human queue** | `work/HUMAN.md`: the single list of decisions only the human can make |
| **Light item** | A work item that is one file instead of a folder, for tasks under about an hour |
| **Module** | An optional, self-contained part of the repo (`product`, `operations`, `security`, `release`, `infra`, `evals`, `github`) that can be cut with `tools/remove_module.py` |
| **Orchestrator** | The role that triages requests, dispatches items and clears blocks |
| **Owner (of a folder)** | The role named by `owner_role` in a folder's README; the only role that writes there |
| **Placeholder** | A deliberately empty file or folder marked `status: placeholder`; fill it or delete it |
| **Profile** | How much of the skeleton is generated: `full`, `standard`, `lean` or `custom` |
| **Role** | A charter in `agents/roles/` defining what an agent in that job reads, writes and must never do |
| **Skill** | A reusable procedure in the open Agent Skills format, loaded only when a task matches its description |
| **Stale** | An item idle for 14 days; its handoff is untrusted until re-verified |
| **Work item** | A unit of work tracked under `work/items/` with a status, an owner and a handoff |
