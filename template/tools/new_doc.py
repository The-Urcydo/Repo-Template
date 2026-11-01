#!/usr/bin/env python3
"""Create a doc from its template with valid front matter.

Usage:
  python3 tools/new_doc.py <type> "Title" [--summary "one sentence"]

Types: tutorial | how-to | reference | explanation | runbook | postmortem
For decisions use tools/new_adr.py. New docs start with status `draft`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_indexes  # noqa: E402
from _lib import apply_tokens, read_text, repo_root, slugify, today, write_text, yaml_scalar  # noqa: E402

# type -> (target folder under docs/, template path under docs/)
TYPES = {
    "tutorial": ("tutorials", "_templates/tutorial.md"),
    "how-to": ("how-to", "_templates/how-to.md"),
    "reference": ("reference", "_templates/reference.md"),
    "explanation": ("explanation", "_templates/explanation.md"),
    "runbook": ("operations/runbooks", "operations/_templates/runbook.md"),
    "postmortem": ("operations/postmortems", "operations/_templates/postmortem.md"),
}


def create(root: Path, type_: str, title: str, summary: str | None) -> Path:
    if type_ not in TYPES:
        raise ValueError(f"unknown type '{type_}'; use one of: {', '.join(TYPES)} (ADRs: tools/new_adr.py)")
    folder, tpl_rel = TYPES[type_]
    tpl = root / "docs" / tpl_rel
    if not tpl.exists():
        raise FileNotFoundError(f"missing template docs/{tpl_rel}" + (" (is the operations module installed?)" if "operations" in tpl_rel else ""))
    slug = slugify(title)
    if not slug:
        raise ValueError("title is empty after cleaning")
    target = root / "docs" / folder / f"{slug}.md"
    if target.exists():
        raise FileExistsError(f"{target.relative_to(root)} already exists")
    one_liner = (summary or "TODO one sentence saying what this doc answers").strip()
    text = apply_tokens(read_text(tpl), {
        "__TITLE_YAML__": yaml_scalar(title.strip()),
        "__TITLE__": title.strip(),
        "__DATE__": today().isoformat(),
        "__SUMMARY_YAML__": yaml_scalar(one_liner),
    })
    write_text(target, text)
    sync_indexes.write_outputs(root)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("type")
    ap.add_argument("title")
    ap.add_argument("--summary")
    args = ap.parse_args(argv)
    root = repo_root()
    try:
        print(create(root, args.type, args.title, args.summary).relative_to(root).as_posix())
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
