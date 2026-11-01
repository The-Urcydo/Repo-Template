#!/usr/bin/env python3
"""Create a work item under work/items/.

Usage:
  python3 tools/new_item.py <slug words...> [--title "Human title"] [--light]
                            [--owner ROLE] [--status STATUS]

Full item  -> work/items/<date>-<slug>/{handoff.md, brief.md}   (other files are added by the role that owns them)
Light item -> work/items/<date>-<slug>.md                        (one file; for tasks under ~an hour)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_indexes  # noqa: E402
from _lib import (  # noqa: E402
    DEFAULT_OWNER, STATUSES, apply_tokens, file_lock, iter_items, load_roles, read_text, repo_root,
    slugify, today, write_text, yaml_scalar,
)


def create(root: Path, slug: str, title: str | None, light: bool, owner: str | None, status: str) -> Path:
    slug = slugify(slug)
    if not slug:
        raise ValueError("slug is empty after cleaning; use letters and digits")
    if status not in STATUSES:
        raise ValueError(f"unknown status '{status}'; use one of: {', '.join(STATUSES)}")
    owner = owner or DEFAULT_OWNER[status]
    roles = load_roles(root)
    if roles and owner not in roles:
        raise ValueError(f"unknown role '{owner}'; roles: {', '.join(sorted(roles))}")
    tpl_dir = root / "work" / "_templates"
    handoff_tpl = tpl_dir / ("light-item.md" if light else "handoff.md")
    if not handoff_tpl.exists():
        raise FileNotFoundError(f"missing template {handoff_tpl.relative_to(root)}")

    with file_lock(root, "items"):
        existing = {i.id for i in iter_items(root)}
        base = f"{today().isoformat()}-{slug}"
        item_id, n = base, 2
        while item_id in existing:
            item_id, n = f"{base}-{n}", n + 1
        shown = title or slug.replace("-", " ").capitalize()
        tokens = {
            "__ID__": item_id,
            "__TITLE_YAML__": yaml_scalar(shown),
            "__TITLE__": shown,
            "__DATE__": today().isoformat(),
            "__OWNER__": owner,
            "__STATUS__": status,
        }
        items = root / "work" / "items"
        if light:
            target = items / f"{item_id}.md"
            write_text(target, apply_tokens(read_text(handoff_tpl), tokens))
        else:
            folder = items / item_id
            target = folder / "handoff.md"
            write_text(target, apply_tokens(read_text(handoff_tpl), tokens))
            brief_tpl = tpl_dir / "brief.md"
            if brief_tpl.exists():
                write_text(folder / "brief.md", apply_tokens(read_text(brief_tpl), tokens))
        sync_indexes.write_outputs(root)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="+", help="short words describing the work")
    ap.add_argument("--title")
    ap.add_argument("--light", action="store_true", help="single-file item")
    ap.add_argument("--owner", help="role that acts first (default depends on status)")
    ap.add_argument("--status", default="draft", help="initial status (default: draft)")
    args = ap.parse_args(argv)
    root = repo_root()
    try:
        target = create(root, " ".join(args.slug), args.title, args.light, args.owner, args.status)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(target.relative_to(root).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
