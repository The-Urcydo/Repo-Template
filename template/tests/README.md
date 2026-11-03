---
title: Tests
type: meta
status: placeholder
summary: Cross-cutting and end-to-end tests of the product; unit tests live next to the code they test.
owner_role: builder
---
# tests/

Placeholder. Put integration, end-to-end and cross-cutting tests here. Unit tests live next to the code they test, so they move and are deleted with it.

The tooling in `tools/` has its own unit tests in `tools/tests/`: `python3 -m unittest discover -s tools/tests`.

When the first test lands, propose how to run the whole suite for the root `AGENTS.md` (the human owns it; propose the change with `python3 tools/question.py ask`) and change this file's `status` to `active`.
