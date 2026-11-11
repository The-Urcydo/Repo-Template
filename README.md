# Repo-Template

> **One human. Several AI agents. One structure.**
>
> A [Copier](https://copier.readthedocs.io) template for repositories where one human and several AI agents work together.

[![CI](https://github.com/The-Urcydo/Repo-Template/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/The-Urcydo/Repo-Template/actions/workflows/test.yml)
[![Release](https://img.shields.io/github/v/release/The-Urcydo/Repo-Template?sort=semver&label=release)](https://github.com/The-Urcydo/Repo-Template/releases)
[![License: MIT](https://img.shields.io/github/license/The-Urcydo/Repo-Template)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](#quick-start)
[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)

**Works with:** Claude Code · Codex · OpenCode · Cursor · GitHub Copilot · Gemini CLI

**Jump to:** [Quick start](#quick-start) · [Why this structure](#why-this-structure) · [What you get](#what-you-get) · [Profiles](#profiles-and-layouts) · [Works with your agent](#works-with-your-agent) · [Updating](#pull-in-template-improvements) · [FAQ](#faq) · [Contributing](#contributing)

Repo-Template gives a new project a finished *structure*: docs grouped by audience, work tracking with handoffs, tool-neutral agent roles and skills, and a one-command health check. Nobody has to research how to organize the repo again, and every optional part can be cut off when you do not need it.

## Quick start

**Requires** Python 3.9+, git, and Copier 9.4+. Cloning or forking this repository gives you the template source (Jinja files), not a finished project, and it cannot receive later updates. Generate with Copier instead:

```
pipx install copier            # or: pip install copier
copier copy --trust gh:The-Urcydo/Repo-Template projects/my-app/my-app
cd projects/my-app/my-app
git init && git add -A && git commit -m "Initial commit from Repo-Template"
python3 tools/check.py         # prints "ok" and how many placeholders remain
python3 tools/check.py --stubs # lists the placeholders to fill or delete
```

With [uv](https://docs.astral.sh/uv/), `uvx copier copy --trust gh:The-Urcydo/Repo-Template projects/my-app/my-app` runs it without a global install.

- **Generate into a folder of its own** (`my-app/my-app`, as above; Copier creates the missing parent folders). Parallel agents work in git worktrees that the tools create beside the clone (`my-app/my-app-<item-id>`), so this keeps them together instead of mixing them into the folder that holds your other projects. The tools warn once, when the first worktree is created in a folder that also holds other git repos.
- **`--trust` is required** because the template runs two of its own stdlib-only tools after generating, to build the indexes and agent adapters. Without it Copier stops and tells you so; nothing is written.
- **You answer five questions:** project name, one-line description, **profile**, **layout**, and whether to generate the `.claude/` adapter (plus the module picker if you choose `custom`; see [Profiles and layouts](#profiles-and-layouts)).

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

## Works with your agent

`agents/` is tool-neutral. Claude Code reads `.claude/` and `CLAUDE.md`, which are *generated* from `agents/` by `python3 tools/sync_agents.py` (the sync refuses to overwrite files it did not generate). Codex, OpenCode, and other `AGENTS.md`-aware tools read `AGENTS.md` and `agents/` directly. Cursor, GitHub Copilot, and Gemini CLI use optional adapters generated from the same source; enable them in `agents/adapters/targets.json`.

| Tool | How it reads the harness | Setup |
|---|---|---|
| Claude Code | `.claude/` + `CLAUDE.md`, generated | on by default |
| Codex, OpenCode, other `AGENTS.md` tools | `AGENTS.md` + `agents/` directly | none |
| Cursor | `.cursor/rules/`, generated | set `enabled` to `true` under `cursor` in `targets.json` |
| GitHub Copilot | `.github/copilot-instructions.md`, generated | set `enabled` to `true` under `copilot` |
| Gemini CLI | `.gemini/settings.json`, generated | set `enabled` to `true` under `gemini` |

After editing `agents/` or changing `targets.json`, run `python3 tools/sync_agents.py`. The generated files are not hand-edited. See [the adapter reference](template/agents/adapters/README.md) and `docs/dev/how-to/use-with-other-agents.md` in a generated project.

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

## FAQ

**Is this a GitHub template?** No. A GitHub template creates a copy with no built-in way to receive later fixes. Repo-Template uses Copier, which records your answers and merges template updates into the generated project while keeping your edits and cut modules.

**Do I have to use Claude Code?** No. The harness in `agents/` is tool-neutral. Claude Code, Cursor, GitHub Copilot, and Gemini CLI can use generated adapters; Codex, OpenCode, and other `AGENTS.md`-aware tools read it directly.

**Can I use it for a non-Python project?** Yes. The generated tools are standard-library Python, but the code layout can be `minimal` (bring your own folders) or any of the shipped layouts. The template does not impose a language or framework.

**Does a generated project have dependencies?** No. The tools use only the Python standard library. Copier is needed only to create and update the project.

**How do I update a generated project?** Run `copier update --trust` on a clean git tree. Local edits are merged, and modules you cut stay cut.

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
git tag -a vX.Y.Z -m "vX.Y.Z: short summary" \
  -m "What changed for generated projects; mention file renames."
git push origin vX.Y.Z
gh release create vX.Y.Z --verify-tag --notes-from-tag
```

Tag on the merge commit, after the pull requests you want to ship have merged. The tag message (the summary and the detail paragraph) becomes the [release notes](https://github.com/The-Urcydo/Repo-Template/releases): list what changed for generated projects and say when an update renames files. `--notes-from-tag` reads that message, so write it for the people updating their projects.

## Known limits

- The multi-agent workflows are exercised with fixtures and reference solutions, not yet with real parallel agent runs across separate sessions. Treat role handoffs as validated by the harness, not by production mileage.
- Exercise the `agents/evals` golden tasks against your own agent CLI with `python3 tools/eval_harness.py --cmd "..."` (`--verify-fixtures` validates the sandbox seeding and grading logic offline).
- The `.claude/` paths and file formats follow Claude Code's documentation as of November 2026 and may change; only `agents/` is yours to rely on.
- Creating and updating a project needs Copier (so Python). Using a generated project needs only `python3`.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first; the rules in [AGENTS.md](AGENTS.md) apply to humans and agents alike. By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities privately through the [security policy](SECURITY.md), never in a public issue.

If this template saves you time, a star helps other people find it.

## License

Released under the [MIT License](LICENSE).
