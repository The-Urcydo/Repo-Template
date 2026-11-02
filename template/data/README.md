---
title: Data
type: meta
status: placeholder
summary: Datasets, schemas and artifacts for data or ML projects; raw data is immutable and large files stay out of git.
owner_role: builder
---
# data/

Placeholder (`data-ml` layout). Put dataset schemas, small fixtures and data pipeline definitions here.

Rules worth keeping from the start:
- Never commit large binary datasets or sensitive/personal records to git; ignore them in `.gitignore` or track them with DVC / object storage.
- Keep raw input data immutable; write cleaned or derived outputs to separate paths.
- When the first dataset or schema lands, set this file's `status` to `active`.
