#!/usr/bin/env python3
"""Manage isolated sibling git worktrees for parallel agent work items.

Usage:
  python3 tools/worktree.py create <item-id-or-unique-fragment> [--path DIR]
  python3 tools/worktree.py remove <item-id-or-unique-fragment> [--force]
  python3 tools/worktree.py list

Creates a sibling worktree at ../<repo>-<item-id> on branch item/<item-id> so parallel
building agents never share a working directory or step on each other's index. When the
first worktree is created and the folder that holds the clone also holds other git repos, it
prints one warning (it never blocks): the owner should keep the project in its own folder,
<name>/<name>, so its worktrees stay together.
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


def branch_name(item_id: str) -> str:
    return f"item/{item_id}"


def branch_exists(root: Path, item_id: str) -> bool:
    return _git(root, "rev-parse", "--verify", f"refs/heads/{branch_name(item_id)}").returncode == 0


def _worktree_entries(root: Path) -> list[dict[str, str]]:
    res = _git(root, "worktree", "list", "--porcelain")
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "git worktree list failed")
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in res.stdout.splitlines() + [""]:
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return entries


def registered_worktree(root: Path, item_id: str) -> Path | None:
    """Return the worktree currently checked out on item/<id>, wherever it lives."""
    wanted = f"refs/heads/{branch_name(item_id)}"
    for entry in _worktree_entries(root):
        if entry.get("branch") == wanted:
            return Path(entry["worktree"]).resolve()
    return None


def crowded_parent(root: Path) -> int:
    """Count the other git repos in the folder that holds the clone, until the clone has a worktree.

    Returns 0 once the clone has any worktree: moving the clone then breaks it, so the advice would be
    wrong, and repeating it on every create would only cost the agent tokens. The clone itself does not
    count. Any trouble reading the folder counts as none: the warning is a courtesy and must never stop
    a worktree from being created."""
    try:
        me = root.resolve()
        if {Path(e["worktree"]).resolve() for e in _worktree_entries(root)} - {me}:
            return 0
        count = 0
        for child in root.parent.iterdir():
            if child.is_dir() and (child / ".git").exists() and child.resolve() != me:
                count += 1
        return count
    except (OSError, RuntimeError):
        return 0


def _warn_if_crowded(root: Path) -> None:
    others = crowded_parent(root)
    if others:
        print(
            f"warning: {root.parent} also holds {others} other git repo{'' if others == 1 else 's'}, "
            f"so this worktree will sit among them. Tell the owner: the project belongs in a folder of its own "
            f"({root.name}/{root.name}); do not move the clone yourself "
            f"(see agents/protocols/parallel-work.md)",
            file=sys.stderr,
        )


def _resolve_item(root: Path, query: str) -> tuple[str, Path]:
    """Find an item in the main checkout or, failing that, in a registered worktree."""
    try:
        item = find_item(root, query)
        return item.id, item.handoff
    except LookupError as original:
        prefix = "refs/heads/item/"
        matches: list[tuple[str, Path]] = []
        for entry in _worktree_entries(root):
            ref = entry.get("branch", "")
            if not ref.startswith(prefix):
                continue
            item_id = ref[len(prefix):]
            if item_id == query or query in item_id:
                matches.append((item_id, Path(entry["worktree"]).resolve()))
        exact = [m for m in matches if m[0] == query]
        candidates = exact or matches
        if len(candidates) > 1:
            raise LookupError("'" + query + "' is ambiguous: " + ", ".join(i for i, _ in candidates)) from original
        if not candidates:
            raise original
        item_id, wt_path = candidates[0]
        items = wt_path / "work" / "items"
        handoff = items / item_id / "handoff.md"
        if not handoff.exists() and (items / f"{item_id}.md").exists():
            handoff = items / f"{item_id}.md"
        return item_id, handoff


def create_for_id(root: Path, item_id: str, custom_path: str | None = None) -> Path:
    wt_path = Path(custom_path).resolve() if custom_path else default_wt_path(root, item_id)
    if wt_path == root or root in wt_path.parents:
        raise ValueError("worktree path must be outside the repository root (prefer a sibling folder)")
    if custom_path is None:  # an explicit --path is the person's own choice of place
        _warn_if_crowded(root)
    branch = branch_name(item_id)
    if branch_exists(root, item_id):
        res = _git(root, "worktree", "add", str(wt_path), branch)
    else:
        res = _git(root, "worktree", "add", str(wt_path), "-b", branch)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip() or "git worktree add failed")
    return wt_path


def create(root: Path, query: str, custom_path: str | None = None) -> Path:
    item = find_item(root, query)
    return create_for_id(root, item.id, custom_path)


def discard(root: Path, item_id: str) -> None:
    """Remove a worktree and branch created for an item that was never written. Best effort."""
    wt_path = registered_worktree(root, item_id)
    if wt_path is not None:
        _git(root, "worktree", "remove", "--force", str(wt_path))
    if branch_exists(root, item_id):
        _git(root, "branch", "-D", branch_name(item_id))


def remove(root: Path, query: str, force: bool = False) -> str:
    item_id, handoff = _resolve_item(root, query)
    status = str(read_fm(handoff).get("status") or "") if handoff.exists() else ""
    if not force and status not in ("done", "canceled", "verified"):
        raise ValueError(f"{item_id} is '{status}'; only verified, done or canceled items should have their worktree removed (pass --force to override)")
    wt_path = registered_worktree(root, item_id)
    if wt_path is None:
        raise ValueError(f"no registered worktree for branch {branch_name(item_id)}")
    args = ["worktree", "remove"] + (["--force"] if force else []) + [str(wt_path)]
    res = _git(root, *args)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip() or "git worktree remove failed")
    branch = branch_name(item_id)
    if not branch_exists(root, item_id):
        return f"removed worktree {wt_path}"
    deleted = _git(root, "branch", "-d", branch)
    if deleted.returncode == 0:
        return f"removed worktree {wt_path} and branch {branch}"
    return (
        f"removed worktree {wt_path}; branch {branch} kept because it is not merged "
        f"(merge it, then run: git branch -D {branch})"
    )


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
