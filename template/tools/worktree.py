#!/usr/bin/env python3
"""Manage isolated sibling git worktrees for parallel agent work items.

Usage:
  python3 tools/worktree.py create <item-id-or-unique-fragment> [--path DIR]
  python3 tools/worktree.py remove <item-id-or-unique-fragment> [--force]
  python3 tools/worktree.py list

Creates a sibling worktree at ../<repo>-<item-id> on branch item/<item-id> so parallel
building agents never share a working directory or step on each other's index.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import find_item, read_fm, repo_root  # noqa: E402


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, timeout=60,
    )


def default_wt_path(root: Path, item_id: str) -> Path:
    return root.parent / f"{root.name}-{item_id}"


def create(root: Path, query: str, custom_path: str | None = None) -> Path:
    item = find_item(root, query)
    wt_path = Path(custom_path).resolve() if custom_path else default_wt_path(root, item.id)
    if wt_path == root or root in wt_path.parents:
        raise ValueError("worktree path must be outside the repository root (prefer a sibling folder)")
    branch = f"item/{item.id}"
    check_branch = _git(root, "rev-parse", "--verify", f"refs/heads/{branch}")
    if check_branch.returncode == 0:
        res = _git(root, "worktree", "add", str(wt_path), branch)
    else:
        res = _git(root, "worktree", "add", str(wt_path), "-b", branch)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip() or "git worktree add failed")
    return wt_path


def remove(root: Path, query: str, force: bool = False) -> str:
    item = find_item(root, query)
    status = str(read_fm(item.handoff).get("status") or "") if item.handoff.exists() else ""
    if not force and status not in ("done", "canceled", "verified"):
        raise ValueError(f"{item.id} is '{status}'; only verified, done or canceled items should have their worktree removed (pass --force to override)")
    wt_path = default_wt_path(root, item.id)
    args = ["worktree", "remove"] + (["--force"] if force else []) + [str(wt_path)]
    res = _git(root, *args)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip() or "git worktree remove failed")
    return f"removed worktree {wt_path}"


def list_worktrees(root: Path) -> str:
    res = _git(root, "worktree", "list")
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "git worktree list failed")
    return res.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_create = sub.add_parser("create", help="create a sibling worktree for a work item")
    p_create.add_argument("item")
    p_create.add_argument("--path", help="custom worktree path (default: ../<repo>-<item-id>)")

    p_remove = sub.add_parser("remove", help="remove a work item's sibling worktree")
    p_remove.add_argument("item")
    p_remove.add_argument("--force", action="store_true", help="remove even if item is not done/canceled or has uncommitted changes")

    sub.add_parser("list", help="list active git worktrees")

    args = ap.parse_args(argv)
    root = repo_root()
    try:
        if args.cmd == "create":
            print(create(root, args.item, args.path))
        elif args.cmd == "remove":
            print(remove(root, args.item, args.force))
        else:
            print(list_worktrees(root))
    except (ValueError, LookupError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
