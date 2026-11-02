#!/usr/bin/env python3
"""Add a role-owned file (from its template) to an existing full work item.

Usage:
  python3 tools/item_file.py <item-id-or-unique-fragment> <kind>

Kinds: brief | plan | tasks | review | research | design | security-review
Creates work/items/<id>/<kind>.md from work/_templates/ with the id and title filled in.
Refuses to overwrite an existing file. Light (single-file) items have no extra files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import apply_tokens, find_item, read_fm, read_text, repo_root, today, write_text  # noqa: E402

# kind -> (template file in work/_templates, file written in the item folder)
KINDS = {
    "brief": ("brief.md", "brief.md"),
    "plan": ("plan.md", "plan.md"),
    "tasks": ("tasks.md", "tasks.md"),
    "review": ("review.md", "review.md"),
    "research": ("research-note.md", "research.md"),
    "design": ("design.md", "design.md"),
    "security-review": ("security-review.md", "security-review.md"),
}


def add_file(root: Path, query: str, kind: str) -> Path:
    if kind not in KINDS:
        raise ValueError(f"unknown kind '{kind}'; use one of: {', '.join(KINDS)}")
    item = find_item(root, query)
    if item.light:
        raise ValueError(f"{item.id} is a light item (one file); put the content in that file")
    tpl_name, out_name = KINDS[kind]
    tpl = root / "work" / "_templates" / tpl_name
    if not tpl.exists():
        hint = " (is the security module installed?)" if kind == "security-review" else ""
        raise FileNotFoundError(f"missing template work/_templates/{tpl_name}{hint}")
    target = item.path / out_name
    if target.exists():
        raise FileExistsError(f"{target.relative_to(root).as_posix()} already exists")
    title = str(read_fm(item.handoff).get("title") or item.id)
    write_text(target, apply_tokens(read_text(tpl), {
        "__ID__": item.id, "__TITLE__": title, "__DATE__": today().isoformat(),
    }))
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("item")
    ap.add_argument("kind")
    args = ap.parse_args(argv)
    root = repo_root()
    try:
        print(add_file(root, args.item, args.kind).relative_to(root).as_posix())
    except (ValueError, LookupError, FileNotFoundError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
