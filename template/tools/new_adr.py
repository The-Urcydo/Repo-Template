#!/usr/bin/env python3
"""Create the next Architecture Decision Record (MADR style) in docs/decisions/.

Usage:
  python3 tools/new_adr.py "Use PostgreSQL for storage" [--status proposed|accepted]
                           [--supersedes 0003] [--decider NAME]

The number is allocated under a lock, so parallel agents never collide.
--supersedes marks the older ADR `superseded` and links both directions.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_indexes  # noqa: E402
from _lib import (  # noqa: E402
    FrontMatterError, apply_tokens, file_lock, parse_front_matter, read_text, repo_root, set_fm_value,
    slugify, today, write_text, yaml_list, yaml_scalar,
)

NUM_RE = re.compile(r"^(\d{4})-.+\.md$")


def _parse_adr_num(raw: str) -> str:
    m = re.search(r"(\d+)", str(raw).strip())
    if not m:
        raise ValueError(f"invalid ADR number '{raw}'")
    return f"{int(m.group(1)):04d}"


def create(root: Path, title: str, status: str, supersedes: str | None, decider: str) -> Path:
    if status not in ("proposed", "accepted"):
        raise ValueError("--status must be proposed or accepted for a new ADR")
    d = root / "docs" / "decisions"
    tpl = root / "docs" / "_templates" / "adr.md"
    if not d.is_dir() or not tpl.exists():
        raise FileNotFoundError("docs/decisions/ or docs/_templates/adr.md is missing")
    slug = slugify(title)
    if not slug:
        raise ValueError("title is empty after cleaning")
    with file_lock(root, "adr"):
        nums = [int(m.group(1)) for p in d.iterdir() if (m := NUM_RE.match(p.name))]
        number = f"{(max(nums) + 1) if nums else 0:04d}"
        old_path = None
        sup_num = None
        if supersedes:
            sup_num = _parse_adr_num(supersedes)
            matches = list(d.glob(f"{sup_num}-*.md"))
            if len(matches) != 1:
                raise ValueError(f"cannot find exactly one ADR numbered {sup_num}")
            old_path = matches[0]
        target = d / f"{number}-{slug}.md"
        text = apply_tokens(read_text(tpl), {
            "__NUMBER__": number, "__TITLE_YAML__": yaml_scalar(title.strip()), "__TITLE__": title.strip(),
            "__DATE__": today().isoformat(), "__STATUS__": status, "__DECIDER__": yaml_scalar(decider),
        })
        text = set_fm_value(text, "supersedes", yaml_list([sup_num]) if sup_num else "[]")
        write_text(target, text)
        if old_path:
            old = read_text(old_path)
            try:
                fm, _ = parse_front_matter(old)
            except FrontMatterError as exc:
                raise ValueError(f"{old_path.name}: {exc}") from exc
            if (fm or {}).get("status") not in ("accepted", "proposed"):
                print(f"warning: {old_path.name} was '{(fm or {}).get('status')}', not accepted", file=sys.stderr)
            old = set_fm_value(old, "status", "superseded")
            old = set_fm_value(old, "superseded_by", yaml_scalar(number))
            write_text(old_path, old)
        sync_indexes.write_outputs(root)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("title")
    ap.add_argument("--status", default="proposed")
    ap.add_argument("--supersedes")
    ap.add_argument("--decider", default="human")
    args = ap.parse_args(argv)
    root = repo_root()
    try:
        print(create(root, args.title, args.status, args.supersedes, args.decider).relative_to(root).as_posix())
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
