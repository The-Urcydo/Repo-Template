#!/usr/bin/env python3
"""Create a doc from its template with valid front matter.

Usage:
  python3 tools/new_doc.py <type> "Title" [--summary "one sentence"] [--audience dev|user]

Types: tutorial | how-to | reference | explanation | runbook | postmortem
The four Diataxis types go to docs/<audience>/<type>/ (default audience: dev, the people building
the project; user is for its end users). Runbooks and postmortems live in the operations module.
For decisions use tools/new_adr.py. New docs start with status `draft`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_indexes  # noqa: E402
from _lib import (  # noqa: E402
    TYPED_AUDIENCE_DIRS, apply_tokens, file_lock, read_text, repo_root, slugify, today, write_text, yaml_scalar,
)

# type -> (target folder under docs/, template path under docs/)
TYPES = {
    "tutorial": ("tutorials", "_templates/tutorial.md"),
    "how-to": ("how-to", "_templates/how-to.md"),
    "reference": ("reference", "_templates/reference.md"),
    "explanation": ("explanation", "_templates/explanation.md"),
    "runbook": ("operations/runbooks", "operations/_templates/runbook.md"),
    "postmortem": ("operations/postmortems", "operations/_templates/postmortem.md"),
}
AUDIENCE_TYPES = ("tutorial", "how-to", "reference", "explanation")  # types that sit under an audience folder


def create(root: Path, type_: str, title: str, summary: str | None, audience: str | None = None) -> Path:
    if type_ not in TYPES:
        raise ValueError(f"unknown type '{type_}'; use one of: {', '.join(TYPES)} (ADRs: tools/new_adr.py)")
    folder, tpl_rel = TYPES[type_]
    if type_ in AUDIENCE_TYPES:
        audience = audience or "dev"
        if audience not in TYPED_AUDIENCE_DIRS:
            raise ValueError(f"unknown audience '{audience}'; use one of: {', '.join(TYPED_AUDIENCE_DIRS)}")
        folder = f"{audience}/{folder}"
    elif audience:
        raise ValueError(f"--audience applies to {', '.join(AUDIENCE_TYPES)}; '{type_}' lives in docs/{folder}/")
    tpl = root / "docs" / tpl_rel
    if not tpl.exists():
        raise FileNotFoundError(f"missing template docs/{tpl_rel}" + (" (is the operations module installed?)" if "operations" in tpl_rel else ""))
    slug = slugify(title)
    if not slug:
        raise ValueError("title is empty after cleaning")
    target = root / "docs" / folder / f"{slug}.md"
    with file_lock(root, "docs"):
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
    ap.add_argument("--audience", help="dev (default) or user; only for tutorial, how-to, reference, explanation")
    args = ap.parse_args(argv)
    root = repo_root()
    try:
        print(create(root, args.type, args.title, args.summary, args.audience).relative_to(root).as_posix())
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
