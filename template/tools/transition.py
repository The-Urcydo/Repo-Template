#!/usr/bin/env python3
"""Move a work item to a new status, enforcing the lifecycle and handoff rules.

Usage:
  python3 tools/transition.py <item-id-or-unique-fragment> <status> --by ROLE --next "what the next role should do"
        [--owner ROLE] [--evidence "command or link"]...
  python3 tools/transition.py <item-id-or-unique-fragment> --next "..." [--owner ROLE] [--evidence "..."]
        (no status: change only the next step, owner or evidence; the status stays as it is)

Rules (see agents/protocols/handoff.md):
  * only transitions listed in the state machine are allowed
  * every status change needs --by ROLE, so the actor is recorded and cannot self-review
  * every status except `done` needs --next (blocked: say what unblocks it)
  * in-review, verified and done need evidence (new --evidence or already in the handoff)
  * verified and done need review.md in a full item folder (independent review happened)
  * built_by is set once, when the item first enters in-progress or in-review, and is never overwritten
  * verified and done need an existing built_by, and the role passing --by must be different
  * the next owner defaults to the role in DEFAULT_OWNER; override with --owner
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_indexes  # noqa: E402
from _lib import (  # noqa: E402
    DEFAULT_OWNER, NEEDS_EVIDENCE, STATUSES, TRANSITIONS, FrontMatterError, file_lock, find_item,
    load_roles, parse_front_matter, read_text, repo_root, set_fm_value, today, write_text, yaml_list,
    yaml_scalar,
)


def _apply_by_role(text: str, fm: dict, status: str, by_role: str | None) -> str:
    if not by_role:
        return text
    built_by = str(fm.get("built_by") or "").strip()
    if status in ("in-progress", "in-review"):
        if not built_by:
            return set_fm_value(text, "built_by", yaml_scalar(by_role))
        return text
    if status in ("verified", "done"):
        if not built_by:
            raise ValueError(
                "no builder is recorded: move the item through in-progress with --by <builder> before verifying it"
            )
        if by_role == built_by:
            raise ValueError(
                f"independent review required: role '{by_role}' built this item and cannot mark it {status}"
            )
        if status == "verified":
            return set_fm_value(text, "verified_by", yaml_scalar(by_role))
        if not str(fm.get("verified_by") or "").strip():
            raise ValueError("no reviewer is recorded: move the item through verified with --by <reviewer> before done")
    return text


def transition(root: Path, query: str, target: str | None, next_action: str | None,
               owner: str | None, evidence: list[str], by_role: str | None = None) -> str:
    if target is not None and target not in STATUSES:
        raise ValueError(f"unknown status '{target}'; use one of: {', '.join(STATUSES)}")
    roles = load_roles(root)
    if by_role and roles and by_role not in roles:
        raise ValueError(f"unknown role '{by_role}'; roles: {', '.join(sorted(roles))}")
    item = find_item(root, query)
    if not item.handoff.exists():
        raise FileNotFoundError(f"{item.id} has no handoff.md")
    with file_lock(root, f"item-{item.id}"):
        text = read_text(item.handoff)
        try:
            fm, _ = parse_front_matter(text)
        except FrontMatterError as exc:
            raise ValueError(f"handoff front matter is invalid: {exc}") from exc
        if not fm:
            raise ValueError("handoff has no front matter")
        current = str(fm.get("status", ""))
        if current not in TRANSITIONS:
            raise ValueError(f"current status '{current}' is not a valid status")
        if target is None or target == current:
            return _update_in_place(root, item, text, fm, current, next_action, owner, evidence, by_role)
        if target not in TRANSITIONS[current]:
            allowed = ", ".join(sorted(TRANSITIONS[current])) or "(none: this status is final)"
            raise ValueError(f"cannot move {current} -> {target}; allowed from {current}: {allowed}")
        if target != "done" and not (next_action or "").strip():
            raise ValueError(f"--next is required for {target}" + (" (say what unblocks it)" if target == "blocked" else ""))
        old_ev = fm.get("evidence") or []
        old_ev = old_ev if isinstance(old_ev, list) else [old_ev]
        all_ev = [str(e) for e in old_ev if str(e).strip()] + [e for e in evidence if e.strip()]
        if target in NEEDS_EVIDENCE and not all_ev:
            raise ValueError(f"{target} needs evidence: pass --evidence '<command run or link>'")
        if target in ("verified", "done") and not item.light and not (item.path / "review.md").exists():
            raise ValueError(f"{target} needs {item.id}/review.md written by the reviewer")
        if not by_role:
            raise ValueError(f"--by <role> is required for status changes ({current} -> {target})")
        text = _apply_by_role(text, fm, target, by_role)
        new_owner = owner or DEFAULT_OWNER[target]
        if roles and new_owner not in roles:
            raise ValueError(f"unknown role '{new_owner}'; roles: {', '.join(sorted(roles))}")
        text = set_fm_value(text, "status", target)
        text = set_fm_value(text, "owner_role", new_owner)
        if next_action:
            text = set_fm_value(text, "next_action", yaml_scalar(next_action.strip()))
        elif target == "done":
            text = set_fm_value(text, "next_action", yaml_scalar("archive"))
        text = set_fm_value(text, "evidence", yaml_list(all_ev))
        text = set_fm_value(text, "updated", today().isoformat())
        write_text(item.handoff, text)
        sync_indexes.write_outputs(root)
    return f"{item.id}: {current} -> {target} (owner: {new_owner})"


def _update_in_place(root: Path, item, text: str, fm: dict, current: str, next_action: str | None,
                     owner: str | None, evidence: list[str], by_role: str | None = None) -> str:
    """Change next step, owner or evidence without moving the status. Caller holds the item lock."""
    evidence = [e for e in evidence if e.strip()]
    if by_role:
        raise ValueError("--by applies only to a status change; pass the target status")
    if not ((next_action or "").strip() or owner or evidence):
        raise ValueError("nothing to change: pass a status, or at least one of --next, --owner, --evidence")
    if current in ("done", "canceled"):
        raise ValueError(f"{current} is final; there is nothing left to hand over")
    if owner:
        roles = load_roles(root)
        if roles and owner not in roles:
            raise ValueError(f"unknown role '{owner}'; roles: {', '.join(sorted(roles))}")
        text = set_fm_value(text, "owner_role", owner)
    if (next_action or "").strip():
        text = set_fm_value(text, "next_action", yaml_scalar(next_action.strip()))
    if evidence:
        old = fm.get("evidence") or []
        old = old if isinstance(old, list) else [old]
        text = set_fm_value(text, "evidence", yaml_list([str(e) for e in old if str(e).strip()] + evidence))
    text = set_fm_value(text, "updated", today().isoformat())
    write_text(item.handoff, text)
    sync_indexes.write_outputs(root)
    return f"{item.id}: updated, status stays {current}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("item")
    ap.add_argument("status", nargs="?", help="omit to change only --next/--owner/--evidence")
    ap.add_argument("--next", dest="next_action")
    ap.add_argument("--owner")
    ap.add_argument("--by", dest="by_role", help="role performing a status change (required; enforces independent review)")
    ap.add_argument("--evidence", action="append", default=[])
    args = ap.parse_args(argv)
    try:
        print(transition(repo_root(), args.item, args.status, args.next_action, args.owner, args.evidence, args.by_role))
    except (ValueError, LookupError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
