#!/usr/bin/env python3
"""Create a work item under work/items/.

Usage:
  python3 tools/new_item.py <slug words...> [--title "Human title"] [--light]
                            [--owner ROLE] [--status STATUS] [--worktree]

Full item  -> work/items/<date>-<slug>/{handoff.md, brief.md}   (other files are added by the role that owns them)
Light item -> work/items/<date>-<slug>.md                        (one file; for tasks under ~an hour)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_indexes  # noqa: E402
import worktree  # noqa: E402
from _lib import (  # noqa: E402
    DEFAULT_OWNER, STATUSES, apply_tokens, file_lock, iter_items, load_roles, read_text, repo_root,
    slugify, today, write_text, yaml_scalar,
)


def _prepare(root: Path, slug: str, owner: str | None, status: str, light: bool) -> tuple[str, str, Path]:
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
    return slug, owner, handoff_tpl


def allocate_id(root: Path, slug: str) -> str:
    """Reserve the next item id without writing files, so a worktree can be created first."""
    slug = slugify(slug)
    if not slug:
        raise ValueError("slug is empty after cleaning; use letters and digits")
    with file_lock(root, "items"):
        existing = {i.id for i in iter_items(root)}
        base = f"{today().isoformat()}-{slug}"
        item_id, n = base, 2
        while item_id in existing:
            item_id, n = f"{base}-{n}", n + 1
        return item_id


def create(root: Path, slug: str, title: str | None, light: bool, owner: str | None, status: str,
           item_id: str | None = None) -> Path:
    slug, owner, handoff_tpl = _prepare(root, slug, owner, status, light)
    tpl_dir = root / "work" / "_templates"
    with file_lock(root, "items"):
        existing = {i.id for i in iter_items(root)}
        if item_id is None:
            base = f"{today().isoformat()}-{slug}"
            item_id, n = base, 2
            while item_id in existing:
                item_id, n = f"{base}-{n}", n + 1
        elif item_id in existing:
            raise ValueError(f"item '{item_id}' already exists")
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
    ap.add_argument("--worktree", action="store_true", help="also create a sibling git worktree on branch item/<id>")
    args = ap.parse_args(argv)
    root = repo_root()
    slug = " ".join(args.slug)
    try:
        if args.worktree:
            _prepare(root, slug, args.owner, args.status, args.light)
            item_id = allocate_id(root, slug)
            if worktree.branch_exists(root, item_id):
                raise ValueError(f"branch {worktree.branch_name(item_id)} already exists")
            wt_path = worktree.create_for_id(root, item_id)
            try:
                target = create(wt_path, slug, args.title, args.light, args.owner, args.status, item_id=item_id)
            except Exception:
                worktree.discard(root, item_id)
                raise
            print(target)
            return 0
        target = create(root, slug, args.title, args.light, args.owner, args.status)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(target.relative_to(root).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
