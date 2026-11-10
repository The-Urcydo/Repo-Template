# Repo-Template

> A [Copier](https://copier.readthedocs.io) template for repositories that one human and several AI agents work in together.

[![CI](https://github.com/The-Urcydo/Repo-Template/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/The-Urcydo/Repo-Template/actions/workflows/test.yml)
[![Version](https://img.shields.io/github/v/tag/The-Urcydo/Repo-Template?sort=semver&label=version)](https://github.com/The-Urcydo/Repo-Template/tags)
[![License: MIT](https://img.shields.io/github/license/The-Urcydo/Repo-Template)](LICENSE)

Repo-Template gives a new project a finished *structure*: docs grouped by audience, work tracking with handoffs, tool-neutral agent roles and skills, and a one-command health check. Nobody has to research how to organize the repo again, and every optional part can be cut off when you do not need it.

## Quick start

Requires Python 3.9+, git and Copier 9.4+. Generate with Copier: cloning or forking this repository gives you the template source (Jinja files), not a finished project, and it cannot receive later updates.

```
pipx install copier            # or: pip install copier
copier copy --trust gh:The-Urcydo/Repo-Template projects/my-app/my-app
cd projects/my-app/my-app
git init && git add -A && git commit -m "Initial commit from Repo-Template"
python3 tools/check.py         # prints "ok" and how many placeholders remain
python3 tools/check.py --stubs # lists the placeholders to fill or delete
```

- **Generate into a folder of its own** (`my-app/my-app`, as above; Copier creates the missing parent folders). Parallel agents work in git worktrees that the tools create beside the clone (`my-app/my-app-<item-id>`), so this keeps them together instead of mixing them into the folder that holds your other projects. The tools warn once, when the first worktree is created in a folder that also holds other git repos.
- **`--trust` is required** because the template runs two of its own stdlib-only tools after generating, to build the indexes and agent adapters. Without it Copier stops and tells you so; nothing is written.
- **You answer five questions:** project name, one-line description, **profile**, **layout**, and whether to generate the `.claude/` adapter (see [Profiles and layouts](#profiles-and-layouts)).

## Why this structure

A repository worked by one human and many agents, over many fresh sessions, breaks the usual assumptions. The design answers four problems (the reasoning is in [design-rationale.md](template/docs/dev/explanation/design-rationale.md) and the [decision records](template/docs/decisions/)):

- **Things that change at different speeds rot each other.** Durable docs, volatile work and the agent harness live in separate folders, each with one lifecycle and one owner.
- **Context is a budget.** A short root `AGENTS.md` loads always, one-line-per-doc indexes come next, and the content itself is opened only when a task needs it.
- **Parallel writers need structure, not luck.** Single-writer ownership, one git worktree per agent, a handoff file per work item, and a state machine that refuses `done` without independent review and evidence.
- **Optional parts must be cuttable.** Modules that the core never links to, removed with one command.

## What you get

| Layer | Folder | Purpose |
|---|---|---|
| Durable knowledge | `docs/` | Docs grouped by audience (`dev/`, `user/`), each in [Diátaxis](https://diataxis.fr) types (tutorials, how-to, reference, explanation), plus numbered decision records (ADRs) |
| Volatile work | `work/` | Inbox, one folder per work item with a `handoff.md`, a generated board, and a queue of questions for the human |
| Agent harness | `agents/` | Role charters, protocols, skills. **The source of truth** for any agent tool |
| Tooling | `tools/` | Standard-library Python (3.9+): health check, index generators, work/ADR/doc/worktree/eval helpers |
| Code | `src/`, `apps/` + `packages/`, `data/` + `notebooks/`, or none (`minimal`) | Placeholders for your stack or engine |

A generated project (profile `full`, layout `single`) looks like this:

```
my-app/
├── AGENTS.md            short instructions every agent reads first (≤100 lines, enforced)
├── CLAUDE.md            shim for Claude Code, generated from agents/
├── README.md  CONTRIBUTING.md  SECURITY.md  CHANGELOG.md
├── docs/                durable knowledge, grouped by audience
│   ├── dev/             tutorials, how-to, reference, explanation
│   ├── user/            end-user docs (type folders are created on demand)
│   ├── decisions/       numbered ADRs
│   └── product/ operations/ security/ release/    optional modules
├── work/                what is happening now
│   ├── inbox/  items/  research/  archive/
│   ├── ACTIVE.md        generated board
│   └── HUMAN.md         questions waiting for the human
├── agents/              the harness, tool-neutral
│   ├── roles/           orchestrator, planner, architect, builder, reviewer, scribe, researcher (+ security)
│   └── skills/  protocols/  evals/  adapters/
├── tools/               check.py, new_item.py, transition.py, sync_indexes.py, sync_agents.py, ...
├── src/  tests/         your code (depends on the layout)
├── infra/  .github/     optional modules
└── .claude/             generated Claude Code adapter (optional)
```

Rules that make it work for agents: a short root `AGENTS.md` (≤100 lines, enforced), a `CLAUDE.md` shim beside each `AGENTS.md`, front matter on every doc, one declared owner per folder, evidence and independent role verification (`--by <role>`) required before work counts as done, workspace dependency boundaries (`depends_on`) enforced across `apps/` and `packages/`, and `python3 tools/check.py` as the single "is the repo healthy?" command.

## Profiles and layouts

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

Local edits are merged, and modules you cut stay cut. See `docs/dev/how-to/update-from-template.md` in a generated project. Copier builds from the newest release tag of this template, so improvements reach your project once a new tag exists. A release that renames files says so in its tag message and release notes: run the update on a clean repo and read the diff.

## What it does not include

- **No application code or stack.** The code folders are placeholders, and the shipped skills are stack-neutral procedures built on the `tools/` commands.
- **No dependencies in a generated project.** The tools are standard-library Python. Copier is needed only to create and update a project, not to use it.
- **No production mileage yet for multi-agent workflows.** See [Known limits](#known-limits).

## Developing this template

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest tests -q
```

The tests generate real projects and exercise them: every profile × layout, custom module sets, deterministic output, idempotent sync, every documented command and flag, the tutorial end to end, the shipped unit tests, parity between the stdlib front-matter parser and PyYAML, and a full `copier update` that keeps local edits and cut modules.

To try your branch by hand, always pass `--vcs-ref HEAD` (`copier copy --trust --vcs-ref HEAD . <dir>`). Without it Copier builds from the newest release tag, so you would test the tag, not your branch.

Changes arrive as pull requests, one topic each, branched from `main`. The owner approves every pull request; agents propose and never merge on their own. The rules are in [AGENTS.md](AGENTS.md).

Layout of this repo: `copier.yml` (questions, exclusions, tasks) · `template/` (everything that is generated) · `tests/` (template-level tests) · `.github/` (this repo's CI; not copied into projects).

## Releasing

```
git tag -a vX.Y.Z -m "vX.Y.Z: short summary"
git push origin vX.Y.Z
```

Tag on the merge commit, after the pull requests you want to ship have merged. The tag message lists what changed for generated projects and says when an update renames files.

## Known limits

- The multi-agent workflows are exercised with fixtures and reference solutions, not yet with real parallel agent runs across separate sessions. Treat role handoffs as validated by the harness, not by production mileage.
- Exercise the `agents/evals` golden tasks against your own agent CLI with `python3 tools/eval_harness.py --cmd "..."` (`--verify-fixtures` validates the sandbox seeding and grading logic offline).
- The `.claude/` paths and file formats follow Claude Code's documentation as of November 2026 and may change; only `agents/` is yours to rely on.
- Creating and updating a project needs Copier (so Python). Using a generated project needs only `python3`.

## License

Released under the [MIT License](LICENSE).
