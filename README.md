# agent-repo-skeleton

A [Copier](https://copier.readthedocs.io) template for new repositories that one human and several AI agents work in together. It gives you a finished *structure* — docs, work tracking, agent roles, health checks — so nobody researches how to organize the repo again, and every part can be cut off when you do not need it.

## What you get

| Layer | Folder | Purpose |
|---|---|---|
| Durable knowledge | `docs/` | [Diátaxis](https://diataxis.fr) docs (tutorials, how-to, reference, explanation) and numbered decision records (ADRs) |
| Volatile work | `work/` | Inbox, one folder per work item with a `handoff.md`, a generated board, and a queue of questions for the human |
| Agent harness | `agents/` | Role charters, protocols, skills. **The source of truth** for any agent tool |
| Tooling | `tools/` | Standard-library Python (3.9+): health check, index generators, work/ADR/doc helpers |
| Code | `src/` or `apps/` + `packages/`, `tests/` | Placeholders for you to replace |

Rules that make it work for agents: a short root `AGENTS.md` (≤100 lines, enforced), a `CLAUDE.md` shim beside each `AGENTS.md`, front matter on every doc, one declared owner per folder, evidence required before work counts as done, and `python3 tools/check.py` as the single "is the repo healthy?" command.

## Create a project

Requires Python 3.9+, git and Copier 9.4+.

```
pipx install copier            # or: pip install copier
copier copy --trust gh:<you>/agent-repo-skeleton path/to/new-project
cd path/to/new-project
git init && git add -A && git commit -m "Initial commit from agent-repo-skeleton"
python3 tools/check.py         # prints "ok"
python3 tools/check.py --stubs # placeholders to fill or delete
```

`--trust` is required because the template runs two of its own stdlib-only tools after generating, to build the indexes and agent adapters. Without it Copier stops and tells you so; nothing is written.

You answer five questions: project name, one-line description, **profile**, **layout**, and whether to generate the `.claude/` adapter.

| Profile | Modules included |
|---|---|
| `full` (default) | product, operations, security, release, infra, evals, github |
| `standard` | product, operations, github |
| `lean` | none: only docs, work, agents, tools and the code folders |
| `custom` | the modules you pick |

| Layout | Code folders |
|---|---|
| `single` (default) | `src/`, `tests/` |
| `workspace` | `apps/`, `packages/`, `tests/` |

Modules are folders that nothing in the core links to, so they can be removed at any time: `python3 tools/remove_module.py <name> --apply` (omit `--apply` for a dry run). It also records the cut in `.copier-answers.yml`, so a later update does not bring the module back.

## Use it with agents other than Claude

`agents/` is tool-neutral. Claude Code reads `.claude/` and `CLAUDE.md`, which are *generated* from `agents/` by `python3 tools/sync_agents.py` (the sync refuses to overwrite files it did not generate). Any other agent can read `AGENTS.md` and `agents/` directly. See `docs/how-to/use-with-other-agents.md` in a generated project.

## Pull in template improvements

```
cd path/to/project             # must be a clean git repo
copier update --trust
```

Local edits are merged, and modules you cut stay cut. See `docs/how-to/update-from-template.md` in a generated project. Tag releases of this template (`v0.1.0`, …) so updates have a stable reference.

## Developing this template

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest tests -q
```

The tests generate real projects and exercise them: every profile × layout, custom module sets, deterministic output, idempotent sync, every documented command and flag, the tutorial end to end, the shipped unit tests, parity between the stdlib front-matter parser and PyYAML, and a full `copier update` that keeps local edits and cut modules.

Layout of this repo: `copier.yml` (questions, exclusions, tasks) · `template/` (everything that is generated) · `tests/` (template-level tests) · `.github/` (this repo's CI; not copied into projects).

## Known limits

- Not exercised with real multi-agent runs yet; the `agents/evals` module exists so you can measure that on your own project.
- The `.claude/` paths and file formats follow Claude Code's documentation as of November 2026 and may change; only `agents/` is yours to rely on.
- Creating and updating a project needs Copier (so Python). Using a generated project needs only `python3`.
- No license is included. Add one before publishing.
# Repo-Template
