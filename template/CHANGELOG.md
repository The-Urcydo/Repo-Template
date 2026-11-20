# Changelog

All notable changes to this project are recorded here, newest first. The scribe role owns this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: decide in an ADR when you first release.

## [Unreleased]

### Removed
- Generated projects no longer ship `tools/tests` in any profile. The tool tests now live in the template repository's
  root-level `tool-tests/` and the root suite runs them against a generated project. **If your project has its own
  tests under `tools/tests/`, they will no longer run in shipped CI**: move them under your project's `tests/` or add
  your own CI step. `copier update` removes the two shipped test files while keeping project-owned files in that folder.

### Added
- Project created from Repo-Template.
