# Repo-Template

A [Copier](https://copier.readthedocs.io) template for new repositories that one human and several AI agents work in together. It gives you a finished *structure* — docs, work tracking, agent roles, health checks — so nobody researches how to organize the repo again, and every part can be cut off when you do not need it.

## What you get

| Layer | Folder | Purpose |
|---|---|---|
| Durable knowledge | `docs/` | Docs grouped by audience (`dev/`, `user/`), each in [Diátaxis](https://diataxis.fr) types (tutorials, how-to, reference, explanation), plus numbered decision records (ADRs) |
| Volatile work | `work/` | Inbox, one folder per work item with a `handoff.md`, a generated board, and a queue of questions for the human |
| Agent harness | `agents/` | Role charters, protocols, skills. **The source of truth** for any agent tool |
| Tooling | `tools/` | Standard-library Python (3.9+): health check, index generators, work/ADR/doc/worktree/eval helpers |
| Code | `src/`, `apps/` + `packages/`, `data/` + `notebooks/`, or none (`minimal`) | Placeholders for your stack or engine |

Rules that make it work for agents: a short root `AGENTS.md` (≤100 lines, enforced), a `CLAUDE.md` shim beside each `AGENTS.md`, front matter on every doc, one declared owner per folder, evidence and independent role verification (`--by <role>`) required before work counts as done, workspace dependency boundaries (`depends_on`) enforced across `apps/` and `packages/`, and `python3 tools/check.py` as the single "is the repo healthy?" command.

## Create a project

Requires Python 3.9+, git and Copier 9.4+.

```
pipx install copier            # or: pip install copier
copier copy --trust gh:<you>/Repo-Template projects/my-app/my-app
cd projects/my-app/my-app
git init && git add -A && git commit -m "Initial commit from Repo-Template"
python3 tools/check.py         # prints "ok"
python3 tools/check.py --stubs # placeholders to fill or delete
```

Generate into a folder of its own (`my-app/my-app`, as above; Copier creates the missing parent folders). Parallel agents work in git worktrees that the tools create beside the clone (`my-app/my-app-<item-id>`), so this keeps them together instead of mixing them into the folder that holds your other projects. The tools warn when the clone's folder also holds other git repos.

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
| `data-ml` | `src/`, `data/`, `notebooks/`, `tests/` |
| `minimal` | none (for game engines, hardware/firmware, or custom root layouts) |

Modules are folders that nothing in the core links to, so they can be removed at any time: `python3 tools/remove_module.py <name> --apply` (omit `--apply` for a dry run). It also records the cut in `.copier-answers.yml`, so a later update does not bring the module back.

## Use it with agents other than Claude

`agents/` is tool-neutral. Claude Code reads `.claude/` and `CLAUDE.md`, which are *generated* from `agents/` by `python3 tools/sync_agents.py` (the sync refuses to overwrite files it did not generate). Optional adapters for Cursor (`.cursor/rules/`), GitHub Copilot (`.github/copilot-instructions.md`), and Gemini CLI (`.gemini/settings.json`) can be enabled in `agents/adapters/targets.json`; they are short pointers/configs, not copies of `AGENTS.md`. Any other agent can read `AGENTS.md` and `agents/` directly. See `docs/dev/how-to/use-with-other-agents.md` in a generated project.

## Pull in template improvements

```
cd path/to/project             # must be a clean git repo
copier update --trust
```

Local edits are merged, and modules you cut stay cut. See `docs/dev/how-to/update-from-template.md` in a generated project. Tag releases of this template (`v0.2.0`, …) so updates have a stable reference.

## Releasing

```
git tag -a v0.2.0 -m "v0.2.0"
git push origin v0.2.0
```

## Developing this template

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest tests -q
```

The tests generate real projects and exercise them: every profile × layout, custom module sets, deterministic output, idempotent sync, every documented command and flag, the tutorial end to end, the shipped unit tests, parity between the stdlib front-matter parser and PyYAML, and a full `copier update` that keeps local edits and cut modules.

Layout of this repo: `copier.yml` (questions, exclusions, tasks) · `template/` (everything that is generated) · `tests/` (template-level tests) · `.github/` (this repo's CI; not copied into projects).

## Known limits

- The multi-agent workflows are exercised with fixtures and reference solutions, not yet with real parallel agent runs across separate sessions. Treat role handoffs as validated by the harness, not by production mileage.
- Exercise the `agents/evals` golden tasks against your own agent CLI with `python3 tools/eval_harness.py --cmd "..."` (`--verify-fixtures` validates the sandbox seeding and grading logic offline).
- The `.claude/` paths and file formats follow Claude Code's documentation as of November 2026 and may change; only `agents/` is yours to rely on.
- Creating and updating a project needs Copier (so Python). Using a generated project needs only `python3`.

## License

Released under the [MIT License](LICENSE).
