# Decision records

This repository's architecture decision records. They are maintainer documents: Copier copies only
`template/`, so nothing here reaches a generated project.

- Paths inside these records are relative to a generated project (`template/`) unless they start with
  `docs/maintainers/` or `tests/`.
- The next number is 0012. Take it from `main` and check open pull requests for the same number first.
- Accepted records are never edited; write a new record that supersedes the old one.
- The template keeps `template/docs/decisions/README.md` and `template/docs/_templates/adr.md` because
  `tools/new_adr.py` needs both. With no record shipped, a project's first ADR is 0000; that is expected.
