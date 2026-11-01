# docs/ rules

- One doc, one Diátaxis type: **tutorial** (learn by doing), **how-to** (solve one task), **reference** (facts, no opinions), **explanation** (why). If a page needs two types, split it and link.
- Create docs with `python3 tools/new_doc.py <type> "Title"`; decisions with `python3 tools/new_adr.py "Title"`.
- Front matter is mandatory: `title`, `type`, `status`, `summary`. The summary is one sentence that lets a stranger decide whether to open the file. Schema: `docs/reference/front-matter.md`.
- Docs say what is true now. History lives in ADRs, work items and git. Delete or deprecate stale pages instead of leaving them.
- A doc that describes code lists it under `related_code`; bump `last_verified` when you re-check it.
- After any change: `python3 tools/sync_indexes.py`, then `python3 tools/check.py`.
- Core docs never link into optional module folders (`docs/product`, `docs/operations`, ...). Mention them in backticks.
