#!/usr/bin/env python3
"""Archive finished work items and flag abandoned ones.

Usage:
  python3 tools/archive_item.py <item-id>          archive one item (must be `done`)
  python3 tools/archive_item.py --sweep [--dry-run]
        - archive every `done` item last updated more than DONE_ARCHIVE_DAYS ago
        - mark active items not updated for STALE_DAYS as `stale` (owner -> orchestrator)

Archived items move to work/archive/<year>/ (moved, never deleted; git keeps history).
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_indexes  # noqa: E402
from _lib import (  # noqa: E402
    DONE_ARCHIVE_DAYS, STALE_DAYS, FrontMatterError, file_lock, find_item, iter_items, parse_date,
    parse_front_matter, read_text, repo_root, set_fm_value, today, write_text, yaml_scalar,
)

ACTIVE = {"draft", "planned", "in-progress", "in-review", "blocked"}


def _fm(item):
    try:
        fm, _ = parse_front_matter(read_text(item.handoff)) if item.handoff.exists() else (None, "")
    except FrontMatterError:
        return {}
    return fm or {}


def archive(root: Path, item) -> str:
    year = (parse_date(_fm(item).get("created")) or today()).year
    dest_dir = root / "work" / "archive" / str(year)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / item.path.name
    if dest.exists():
        raise FileExistsError(f"{dest.relative_to(root)} already exists")
    shutil.move(str(item.path), str(dest))
    return f"archived {item.id} -> {dest.relative_to(root).as_posix()}"


def mark_stale(item) -> None:
    text = read_text(item.handoff)
    old_next = str(_fm(item).get("next_action", "")).strip()
    text = set_fm_value(text, "status", "stale")
    text = set_fm_value(text, "owner_role", "orchestrator")
    text = set_fm_value(text, "next_action", yaml_scalar(f"Re-triage (idle {STALE_DAYS}+ days). Was: {old_next}"))
    write_text(item.handoff, text)


def sweep(root: Path, dry: bool) -> list[str]:
    log: list[str] = []
    for item in list(iter_items(root)):
        fm = _fm(item)
        status, updated = str(fm.get("status", "")), parse_date(fm.get("updated"))
        if updated is None:
            continue
        age = (today() - updated).days
        if status == "done" and age > DONE_ARCHIVE_DAYS:
            log.append(f"would archive {item.id}" if dry else archive(root, item))
        elif status in ACTIVE and age > STALE_DAYS:
            if not dry:
                mark_stale(item)
            log.append(f"{'would mark' if dry else 'marked'} {item.id} stale ({age} days idle)")
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("item", nargs="?")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    root = repo_root()
    try:
        with file_lock(root, "items"):
            if args.sweep:
                log = sweep(root, args.dry_run)
            elif args.item:
                item = find_item(root, args.item)
                status = _fm(item).get("status")
                if status != "done":
                    print(f"error: {item.id} is '{status}', only done items can be archived", file=sys.stderr)
                    return 2
                log = [f"would archive {item.id}"] if args.dry_run else [archive(root, item)]
            else:
                ap.error("give an item id or --sweep")
            if not args.dry_run:
                sync_indexes.write_outputs(root)
    except (LookupError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(log) if log else "nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
