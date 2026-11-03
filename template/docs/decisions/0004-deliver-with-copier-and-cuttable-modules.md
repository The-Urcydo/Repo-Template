---
title: Deliver with Copier and cuttable modules
type: decision
status: accepted
summary: The skeleton is a Copier template with a full-by-default profile whose optional parts are modules that can be cut cleanly with a tool.
date: 2026-11-01
decision_makers: human
supersedes: []
---
# 0004: Deliver with Copier and cuttable modules

## Context and problem statement

The skeleton must contain enough placeholders that nobody researches the structure again, yet any unneeded part must be easy to remove, and improvements to the template should reach repos already created from it.

## Decision drivers

- Detailed placeholders by default (the owner prefers cutting to researching)
- Clean removal of optional parts without leaving dangling references
- Template improvements must propagate to existing repos
- Low dependency footprint inside the generated repo

## Considered options

- Plain GitHub template repository (one-time copy)
- Cookiecutter (one-time generation)
- Copier with profiles and a module registry

## Decision outcome

Chosen option: "Copier with profiles and a module registry". Default profile `full`; `standard` and `lean` generate less, and `custom` picks modules. Optional parts (`product`, `operations`, `security`, `release`, `infra`, `evals`, `github`) are modules listed in `tools/modules.json`. Core never links into a module (enforced by `check.py`), and `tools/remove_module.py` cuts one and updates `.copier-answers.yml` so `copier update` does not resurrect it.

### Consequences

- Good: `copier update` pulls improvements; cutting is one command and verified by the checks.
- Bad: Copier is a Python dependency for creating and updating (not for using) the repo; `--trust` is required because the template runs its own two stdlib tools after generation; updates can conflict where generated files were hand-edited.

### Confirmation

The template's own test suite generates every profile and layout, runs `check.py` on each, and cuts every module in turn.

## More information

`docs/dev/how-to/cut-a-module.md`, `docs/dev/how-to/update-from-template.md`.
