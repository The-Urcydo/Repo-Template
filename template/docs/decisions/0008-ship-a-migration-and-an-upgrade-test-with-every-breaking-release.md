---
title: Ship a migration and an upgrade test with every breaking release
type: decision
status: proposed
summary: A template release that moves or renames what a generated project owns must ship a Copier migration and a test that updates a real project across the change.
date: 2026-11-12
decision_makers: human
supersedes: []
---
# 0008: Ship a migration and an upgrade test with every breaking release

## Context and problem statement

Generated projects pull template improvements with `copier update` (ADR 0004). Copier merges three versions of every file, so it handles edits well and renames badly. Release `v0.3.0` moved `docs/{explanation,how-to,reference,tutorials}/` to `docs/dev/...` (ADR 0006), and nothing checked what an update across that move does to a project.

Measured on a project generated at `v0.2.0`, with two docs of its own and an edit to `AGENTS.md`, then updated to `v0.3.0`:

- `tools/check.py` reported 19 errors.
- The project's own docs stayed in `docs/how-to/` and `docs/explanation/`, a layout the template no longer owns.
- The generated indexes were stale, because `_tasks` run on the new tree before Copier applies the project's changes.
- Conflict markers sat in `README.md` and `docs/INDEX.md`, and no check looked for them (fixed separately by the `conflict-marker` rule).

`v0.2.0` was public, so this is a break that real projects meet. The template is pre-1.0 and should stay free to change its layout. What must a release owe the projects that update across such a change?

## Decision drivers

- Pre-1.0 means layout may change; it does not mean an update may damage a project.
- A project's own files are the project's, and Copier cannot know where they should go.
- A claim about upgrades needs a test that runs one, not a description.
- The cost lands on the person who updates, often an agent in a fresh session with no memory of the old layout.
- Migrations are code that runs on a user's machine: they stay small, offline, standard library only and idempotent.

## Considered options

- Release notes only: say that files moved and let each project fix its own.
- Ship a Copier migration and an upgrade test with every breaking release.
- Freeze the layout until 1.0.

## Decision outcome

Chosen option: "Ship a Copier migration and an upgrade test with every breaking release", because it is the only option that protects the project's own files and proves it on every run of the suite.

1. **What is breaking.** A change after which a project that updates without hand work fails `python3 tools/check.py --strict`, or loses or misplaces files it owns. Examples: moving or renaming a folder or a file the template ships, changing a front-matter rule so that old docs fail, renaming a command. Adding files or tools is not breaking.
2. **A breaking release ships a migration.** An entry in `_migrations` in `copier.yml`, with `version:` set to that release. Copier runs it only when a project crosses that version. The script lives in `migrations/` at the template repo root, outside `template/`, so it is never shipped. It uses the standard library, is idempotent, never overwrites a file, stages what it moves, and prints one line per change. A migration that moves files runs in the `before` stage; because `_tasks` run on the new tree first, it is followed by `after`-stage entries that rebuild the generated files.
3. **A breaking release ships an upgrade test.** `tests/test_template.py` generates a project at the previous release tag, adds realistic local work, updates it and asserts that `check.py --strict` passes and the project's own files are where they belong. The test skips when the tag is not available (a shallow clone); the repo's CI fetches tags so it runs there.
4. **Release notes say it.** The tag message names the breaking change and the migration, and says what stays manual.
5. **What a migration does not cover** is written in `docs/dev/how-to/update-from-template.md`, next to the recovery step: a project's own edit on a line the template also changed still conflicts (Copier's merge); an edit to a shipped file at its old path is not carried to the new path; links from files that stay put to a moved doc are not rewritten. `check.py` reports the first and the last.
6. **Old migrations stay.** A project may update across several releases at once; Copier runs each migration whose version it crosses, in order.

### Consequences

- Good: an update across a known break leaves the project's own docs in place and the checks green; the next break cannot ship without its test.
- Bad: each breaking release carries extra code and a test; a migration is one more thing to review.
- Neutral: Copier's merge, the `--trust` requirement and the generated projects themselves do not change.

### Confirmation

- `test_update_across_the_docs_layout_move_keeps_the_projects_own_docs` and `test_docs_layout_migration_never_overwrites_and_skips_what_the_template_ships` pass, on Copier 9.4.0 (the declared minimum) and on the current release.
- A pull request that changes `template/` in a breaking way (rule 1) without a `_migrations` entry and a test is not merged.
- Migrations are changes to `copier.yml`, which the review treats as a harness-adjacent file.

## Pros and cons of the options

### Release notes only

- Good: no code to maintain.
- Bad: every project repeats the same hand work, and an agent that updates without reading the notes ends with broken links and files in a dead folder.

### Ship a migration and an upgrade test with every breaking release

- Good: protects the project's own files and proves it on each run.
- Bad: costs code and time per breaking release, and Copier's `_migrations` are run with `--trust`.

### Freeze the layout until 1.0

- Good: no breaks.
- Bad: locks in today's mistakes and gives up the point of a template that learns.
