---
title: Release process
type: how-to
status: placeholder
summary: How to cut, verify, publish and roll back a release, including versioning and the changelog.
---
# Release process

Placeholder. Write the real process once you first release, then set `status: active`.

## Versioning

_Scheme (for example SemVer) and what counts as a breaking change. Link the ADR._

## Checklist

1. _All items for the release are `done` and archived._
2. _`python3 tools/check.py --strict` and the full test suite pass on the release commit._
3. _`CHANGELOG.md`: move `[Unreleased]` entries under the new version and date._
4. _Tag and publish: the exact commands._
5. _Verify the published artifact._

## Rollback

_How to undo a bad release, and who decides._
