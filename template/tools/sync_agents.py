#!/usr/bin/env python3
"""Generate tool-specific adapters from the tool-neutral harness in agents/.

Source of truth:  agents/roles/*.md, agents/skills/*/, every AGENTS.md
Generated for Claude Code (when enabled in agents/adapters/targets.json):
  .claude/agents/<role>.md        subagent definitions (name + description + charter)
  .claude/skills/<name>/...       copies of the open-standard skill folders
  <dir>/CLAUDE.md                 one-line shim importing the sibling AGENTS.md
                                  (Claude Code reads CLAUDE.md instead of AGENTS.md
                                  when both exist, so each AGENTS.md needs a shim)
Generated for Cursor (optional, disabled by default in targets.json):
  .cursor/rules/00-repo.mdc       root AGENTS.md wrapped as a Cursor always-on rule
  .cursor/rules/role-<role>.mdc   role charters as manual/agent-requested Cursor rules
Generated for GitHub Copilot (optional, disabled by default in targets.json):
  .github/copilot-instructions.md pointer to AGENTS.md, docs/INDEX.md, and agents/

Everything generated is recorded in agents/adapters/manifest.json. Never edit
generated files by hand; edit the source and re-run this tool.

Usage: python3 tools/sync_agents.py [--check]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    SKIP_DIRS, folder_owners, load_roles, load_targets, read_text, repo_root, sha256_bytes, write_text,
    yaml_scalar,
)

MANIFEST = "agents/adapters/manifest.json"
SHIM = "@AGENTS.md\n"


def _agents_md_dirs(root: Path) -> list[Path]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not (
            Path(dirpath).relative_to(root).parts[:1] == ("work",) and d in ("archive", ".locks")))
        if "AGENTS.md" in filenames:
            found.append(Path(dirpath))
    return found


def render_subagent(role: str, fm: dict, body: str, owned: list[str]) -> str:
    mission = " ".join(str(fm.get("mission", "")).split())
    desc = f"{mission} Use when a work item's handoff owner_role is {role}."

    def lst(key: str) -> str:
        v = fm.get(key) or []
        return ", ".join(str(x) for x in v) if isinstance(v, list) and v else "(none)"

    folders = ", ".join(owned + [str(f) for f in (fm.get("writes_files") or [])]) or "(none)"
    lines = [
        "---",
        f"name: {role}",
        f"description: {yaml_scalar(desc)}",
        "---",
        f"You are the **{role}** role for this repository.",
        "",
        f"Before acting, read `AGENTS.md`, your charter `agents/roles/{role}.md`, and `agents/protocols/handoff.md`.",
        "",
        f"- Reads: {lst('reads')}",
        f"- Folders and files you exclusively own: {folders}",
        f"- Work-item files you exclusively write: {lst('item_files')}",
        f"- Never: {lst('never')}",
        f"- Done when: {fm.get('done_when', '')}",
        f"- Escalate when: {fm.get('escalate_when', '')}",
        "",
        body.strip(),
        "",
        f"> Generated from `agents/roles/{role}.md` by `tools/sync_agents.py`. Do not edit.",
        "",
    ]
    return "\n".join(lines)


def render_cursor_rule(role: str, fm: dict, body: str, owned: list[str]) -> str:
    mission = " ".join(str(fm.get("mission", "")).split())
    desc = f"Role charter for '{role}': {mission}"
    lines = [
        "---",
        f"description: {yaml_scalar(desc)}",
        "alwaysApply: false",
        "---",
        render_subagent(role, fm, body, owned).split("---\n", 2)[-1].strip(),
        "",
    ]
    return "\n".join(lines)


def expected_outputs(root: Path) -> dict[str, bytes]:
    """Map of repo-relative POSIX path -> bytes that the adapters should contain."""
    targets = load_targets(root)
    out: dict[str, bytes] = {}
    owners = folder_owners(root)
    roles = load_roles(root)

    claude = targets.get("claude", {})
    if claude.get("enabled"):
        agents_dir = claude.get("agents_dir", ".claude/agents")
        skills_dir = claude.get("skills_dir", ".claude/skills")
        for role, r in roles.items():
            if r["fm"]:
                owned = [f"`{f}/`" for f, who in sorted(owners.items()) if who == role and f]
                out[f"{agents_dir}/{role}.md"] = render_subagent(role, r["fm"], r["body"], owned).encode("utf-8")
        skills_root = root / "agents" / "skills"
        if skills_root.is_dir():
            for sk in sorted(skills_root.iterdir()):
                if sk.is_dir() and (sk / "SKILL.md").exists():
                    for f in sorted(sk.rglob("*")):
                        if f.is_file() and "__pycache__" not in f.parts:
                            out[f"{skills_dir}/{sk.name}/{f.relative_to(sk).as_posix()}"] = f.read_bytes()
        if claude.get("claude_md_shims", True):
            for d in _agents_md_dirs(root):
                rel = (d / "CLAUDE.md").relative_to(root).as_posix()
                out[rel] = SHIM.encode("utf-8")

    cursor = targets.get("cursor", {})
    if cursor.get("enabled"):
        rules_dir = cursor.get("rules_dir", ".cursor/rules")
        if (root / "AGENTS.md").exists():
            repo_rule = (
                "---\ndescription: Repository-wide rules from AGENTS.md\nalwaysApply: true\n---\n"
                + read_text(root / "AGENTS.md").strip()
                + "\n\n> Generated from `AGENTS.md` by `tools/sync_agents.py`. Do not edit.\n"
            )
            out[f"{rules_dir}/00-repo.mdc"] = repo_rule.encode("utf-8")
        for role, r in roles.items():
            if r["fm"]:
                owned = [f"`{f}/`" for f, who in sorted(owners.items()) if who == role and f]
                out[f"{rules_dir}/role-{role}.mdc"] = render_cursor_rule(role, r["fm"], r["body"], owned).encode("utf-8")

    copilot = targets.get("copilot", {})
    if copilot.get("enabled") and (root / "AGENTS.md").exists():
        inst_file = copilot.get("instructions_file", ".github/copilot-instructions.md")
        content = (
            "<!-- Generated from AGENTS.md by tools/sync_agents.py. Do not edit by hand. -->\n\n"
            + read_text(root / "AGENTS.md").strip()
            + "\n"
        )
        out[inst_file] = content.encode("utf-8")

    return out


def manifest_for(files: dict[str, bytes]) -> str:
    data = {"generated_by": "tools/sync_agents.py", "files": {k: sha256_bytes(v) for k, v in sorted(files.items())}}
    return json.dumps(data, indent=2) + "\n"


def _previous_manifest(root: Path) -> dict[str, str]:
    p = root / MANIFEST
    if not p.exists():
        return {}
    try:
        return json.loads(read_text(p)).get("files", {})
    except (json.JSONDecodeError, OSError):
        return {}


def drift(root: Path) -> list[str]:
    """Human-readable list of differences between disk and what sync would write."""
    want = expected_outputs(root)
    problems = []
    for rel, data in sorted(want.items()):
        p = root / rel
        if not p.exists():
            problems.append(f"missing generated file: {rel}")
        elif p.read_bytes() != data:
            problems.append(f"generated file differs from its source: {rel}")
    for rel in sorted(set(_previous_manifest(root)) - set(want)):
        if (root / rel).exists():
            problems.append(f"stale generated file (source removed): {rel}")
    mp = root / MANIFEST
    if want or mp.exists():
        if not mp.exists() or read_text(mp) != manifest_for(want):
            problems.append(f"manifest out of date: {MANIFEST}")
    return problems


def sync(root: Path) -> list[str]:
    want = expected_outputs(root)
    prev = _previous_manifest(root)
    log: list[str] = []
    for rel, data in sorted(want.items()):
        p = root / rel
        if p.exists() and p.read_bytes() == data:
            continue
        if p.exists() and rel not in prev and p.read_bytes() != data:
            log.append(f"SKIPPED {rel}: exists and is not generated; move or delete it, then re-run")
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        log.append(f"wrote {rel}")
    for rel in sorted(set(prev) - set(want)):
        p = root / rel
        if p.exists():
            p.unlink()
            log.append(f"removed {rel}")
            parent = p.parent
            while parent != root and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
    if want or (root / MANIFEST).exists():
        mp = root / MANIFEST
        content = manifest_for({k: v for k, v in want.items() if (root / k).exists() and (root / k).read_bytes() == v})
        if not mp.exists() or read_text(mp) != content:
            write_text(mp, content)
            log.append(f"wrote {MANIFEST}")
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if adapters are out of date")
    args = ap.parse_args(argv)
    root = repo_root()
    if args.check:
        problems = drift(root)
        for p in problems:
            print(p)
        return 1 if problems else 0
    log = sync(root)
    print("\n".join(log) if log else "adapters already up to date")
    return 1 if any(line.startswith("SKIPPED") for line in log) else 0


if __name__ == "__main__":
    sys.exit(main())
