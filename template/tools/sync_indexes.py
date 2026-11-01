#!/usr/bin/env python3
"""Regenerate every derived index in the repo from its source of truth.

Outputs (deterministic, so `--check` can detect drift):
  docs/INDEX.md              one line per doc, from front-matter `summary`
  docs/<group>/INDEX.md      only when a group has more than SPLIT_THRESHOLD docs
  docs/reference/repo-map.md top-level folders, from each folder README `summary`
  docs/reference/modules.md  installed modules and how to cut them
  work/ACTIVE.md             board of in-flight work items, from handoff front matter
  agents/ROSTER.md           the role table, from agents/roles/*.md + folder ownership

Usage: python3 tools/sync_indexes.py [--check]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    GENERATED_BANNER, SKIP_DIRS, FrontMatterError, folder_owners, iter_docs, iter_items,
    load_modules, load_roles, parse_front_matter, read_fm, read_text, repo_root, write_text,
)

SPLIT_THRESHOLD = 40
BOARD_LIMIT = 60
STATUS_ORDER = ["blocked", "in-review", "in-progress", "planned", "draft", "stale", "verified", "done"]
GROUP_ORDER = ["tutorials", "how-to", "reference", "explanation", "decisions"]
GROUP_TITLES = {
    "tutorials": "Tutorials (learn)",
    "how-to": "How-to guides (do)",
    "reference": "Reference (look up)",
    "explanation": "Explanation (understand)",
    "decisions": "Decisions (ADRs)",
}
TAGGED = ("placeholder", "draft", "deprecated", "proposed", "superseded", "rejected")
FALLBACK_SUMMARY = {
    ".github": "CI workflow, PR template, CODEOWNERS.",
}


def _front(title: str, type_: str, summary: str, owner: str) -> str:
    return (
        "---\n"
        f"title: {title}\n"
        f"type: {type_}\n"
        "status: generated\n"
        f"summary: {summary}\n"
        f"owner_role: {owner}\n"
        "---\n"
        f"{GENERATED_BANNER}\n"
    )


# ------------------------------------------------------------------ docs index
def _fm_of(text: str) -> dict:
    try:
        fm, _ = parse_front_matter(text)
    except FrontMatterError:
        return {}
    return fm or {}


def _doc_entries(root: Path, virtual: dict[Path, str]) -> dict[str, list[tuple[str, str, str, str]]]:
    """group -> [(title, path-relative-to-docs, summary, status)].

    `virtual` holds other generated docs about to be written (repo-map, modules), so the index
    is already correct after a single sync pass instead of changing on the second one.
    """
    groups: dict[str, list[tuple[str, str, str, str]]] = {}
    docs = root / "docs"
    paths = set(iter_docs(root)) | {p for p in virtual if docs in p.parents and not p.name.startswith("_")}
    for p in sorted(paths):
        rel = p.relative_to(docs)
        if rel.name == "INDEX.md" or (rel.name == "README.md" and len(rel.parts) <= 2):
            continue
        group = rel.parts[0] if len(rel.parts) > 1 else "(top level)"
        fm = _fm_of(virtual[p]) if p in virtual else read_fm(p)
        title = str(fm.get("title") or rel.stem.replace("-", " ").title())
        groups.setdefault(group, []).append(
            (title, rel.as_posix(), str(fm.get("summary") or "(no summary)"), str(fm.get("status") or ""))
        )
    return groups


def _line(title: str, path: str, summary: str, status: str) -> str:
    tag = f" _({status})_" if status in TAGGED else ""
    return f"- [{title}]({path}) — {summary}{tag}"


def _group_title(g: str) -> str:
    return GROUP_TITLES.get(g, g.replace("-", " ").title())


def build_docs_indexes(root: Path, virtual: dict[Path, str]) -> dict[Path, str]:
    groups = _doc_entries(root, virtual)
    ordered = [g for g in GROUP_ORDER if g in groups]
    ordered += sorted(g for g in groups if g not in GROUP_ORDER and g != "(top level)")
    if "(top level)" in groups:
        ordered.append("(top level)")
    out: dict[Path, str] = {}
    lines = [
        _front("Docs index", "index",
               "Generated one-line-per-doc map of docs/. Read this first, then open only what the task needs.",
               "scribe"),
        "# Docs index",
        "",
        "Pick the section by what you need: learn, do a task, look up a fact, or understand why.",
        "Placeholders are empty on purpose: fill them or delete them (`python3 tools/check.py --stubs` lists them).",
        "",
    ]
    for g in ordered:
        entries = sorted(groups[g], key=lambda e: e[1])
        guide = f" — [folder guide]({g}/README.md)" if (root / "docs" / g / "README.md").exists() else ""
        lines.append(f"## {_group_title(g)}{guide}")
        lines.append("")
        if len(entries) > SPLIT_THRESHOLD and g != "(top level)":
            lines.append(f"- [{len(entries)} documents — see the section index]({g}/INDEX.md)")
            sub = [
                _front(f"{_group_title(g)} index", "index",
                       f"Generated one-line-per-doc map of docs/{g}/.", "scribe"),
                f"# {_group_title(g)} index",
                "",
            ]
            sub += [_line(t, Path(rel).relative_to(g).as_posix(), s, st) for t, rel, s, st in entries]
            out[root / "docs" / g / "INDEX.md"] = "\n".join(sub) + "\n"
        else:
            lines += [_line(t, rel, s, st) for t, rel, s, st in entries]
        lines.append("")
    out[root / "docs" / "INDEX.md"] = "\n".join(lines).rstrip() + "\n"
    return out


# ------------------------------------------------------------------- repo map
def build_repo_map(root: Path) -> str:
    modules = load_modules(root)
    mod_of: dict[str, str] = {}
    for name, m in modules.items():
        for path in m.get("paths", []):
            if "/" not in path.strip("/"):  # only a whole top-level folder is "a module folder"
                mod_of[path.strip("/")] = name
    rows = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name in SKIP_DIRS or (d.name.startswith(".") and d.name != ".github"):
            continue
        readme = d / "README.md"
        summary = read_fm(readme).get("summary") if readme.exists() else None
        summary = summary or FALLBACK_SUMMARY.get(d.name) or "(no README.md: add one with a `summary`)"
        mod = f" `[module: {mod_of[d.name]}]`" if d.name in mod_of else ""
        rows.append(f"| `{d.name}/` | {summary}{mod} |")
    return (
        _front("Repo map", "reference", "Generated table of top-level folders and what each is for.", "scribe")
        + "# Repo map\n\n| Folder | Purpose |\n|---|---|\n" + "\n".join(rows) + "\n"
    )


def build_modules_doc(root: Path) -> str:
    modules = load_modules(root)
    lines = [
        _front("Modules", "reference",
               "Generated registry of the optional modules installed here and how to cut each one.", "scribe"),
        "# Modules",
        "",
        "Optional capabilities live in self-contained paths. Core never links into them (`check.py` enforces it).",
        "Preview a cut with `python3 tools/remove_module.py <name>`; apply it with `--apply`.",
        "",
    ]
    if not modules:
        lines.append("_No optional modules are installed in this repo (profile: lean)._")
    else:
        lines += ["| Module | What it is | Paths |", "|---|---|---|"]
        for name, m in sorted(modules.items()):
            paths = ", ".join(f"`{p}`" for p in m.get("paths", []))
            lines.append(f"| `{name}` | {m.get('summary', '')} | {paths} |")
        notes = [(n, m["removal_notes"]) for n, m in sorted(modules.items()) if m.get("removal_notes")]
        if notes:
            lines += ["", "## Removal notes", ""]
            lines += [f"- **{n}**: {note}" for n, note in notes]
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------- work board
def build_board(root: Path) -> str:
    rows = []
    for item in iter_items(root):
        fm = {}
        if item.handoff.exists():
            try:
                fm, _ = parse_front_matter(read_text(item.handoff))
            except FrontMatterError:
                fm = {}
        fm = fm or {}
        rows.append({
            "id": item.id,
            "status": str(fm.get("status", "?")),
            "owner": str(fm.get("owner_role", "?")),
            "next": str(fm.get("next_action", "")).replace("|", "/"),
            "updated": str(fm.get("updated", "")),
            "light": item.light,
        })
    rank = {s: i for i, s in enumerate(STATUS_ORDER)}
    rows.sort(key=lambda r: (rank.get(r["status"], 99), r["id"]))
    lines = [
        _front("Active work board", "index",
               "Generated board of in-flight work items. The orchestrator dispatches from this.", "orchestrator"),
        "# Active work board",
        "",
        "Dispatch rule: `agents/protocols/handoff.md`. Move items with `python3 tools/transition.py`.",
        "",
    ]
    if not rows:
        lines.append("_No work items yet. Create one with `python3 tools/new_item.py <slug>`._")
    else:
        lines += ["| Item | Status | Owner | Next action | Updated |", "|---|---|---|---|---|"]
        for r in rows[:BOARD_LIMIT]:
            link = f"items/{r['id']}.md" if r["light"] else f"items/{r['id']}/handoff.md"
            lines.append(f"| [{r['id']}]({link}) | {r['status']} | {r['owner']} | {r['next']} | {r['updated']} |")
        if len(rows) > BOARD_LIMIT:
            lines.append(f"\n_{len(rows) - BOARD_LIMIT} more not shown. Archive finished work: `python3 tools/archive_item.py --sweep`._")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- roster
def build_roster(root: Path) -> str:
    roles = load_roles(root)
    owners = folder_owners(root)
    owned: dict[str, list[str]] = {}
    for folder, role in sorted(owners.items()):
        owned.setdefault(role, []).append(f"`{folder}/`" if folder else "`/`")
    lines = [
        _front("Agent roster", "reference",
               "Generated table of agent roles, what each owns, and which work-item files each writes.",
               "architect"),
        "# Agent roster",
        "",
        "Ownership comes from each folder README's `owner_role` (nearest ancestor wins) plus the role files in `roles/`.",
        "Dispatch rule: `protocols/handoff.md`.",
        "",
        "| Role | Mission | Owns (exclusive writes) | Item files |",
        "|---|---|---|---|",
    ]
    for name, r in sorted(roles.items()):
        fm = r["fm"] or {}
        own = list(owned.get(name, []))
        own += [f"`{f}`" for f in (fm.get("writes_files") or [])]
        items = ", ".join(f"`{f}`" for f in (fm.get("item_files") or [])) or "—"
        lines.append(f"| [`{name}`](roles/{name}.md) | {fm.get('mission', '(missing)')} | {', '.join(own) or '—'} | {items} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- orchestration
def build_outputs(root: Path) -> dict[Path, str]:
    out: dict[Path, str] = {}
    if (root / "docs").is_dir():
        other: dict[Path, str] = {}
        if (root / "docs" / "reference").is_dir():
            other[root / "docs" / "reference" / "repo-map.md"] = build_repo_map(root)
            other[root / "docs" / "reference" / "modules.md"] = build_modules_doc(root)
        out.update(build_docs_indexes(root, other))
        out.update(other)
    if (root / "work").is_dir():
        out[root / "work" / "ACTIVE.md"] = build_board(root)
    if (root / "agents" / "roles").is_dir():
        out[root / "agents" / "ROSTER.md"] = build_roster(root)
    return out


def orphan_indexes(root: Path, outputs: dict[Path, str]) -> list[Path]:
    """Generated per-group indexes that no longer have a reason to exist."""
    docs = root / "docs"
    if not docs.is_dir():
        return []
    return [p for p in sorted(docs.glob("*/INDEX.md")) if p not in outputs]


def stale_outputs(root: Path) -> tuple[list[Path], list[Path]]:
    outputs = build_outputs(root)
    stale = [p for p, c in outputs.items() if not p.exists() or read_text(p) != c]
    return stale, orphan_indexes(root, outputs)


def write_outputs(root: Path) -> list[str]:
    """Bring every generated file up to date. Returns a log of what changed."""
    outputs = build_outputs(root)
    log: list[str] = []
    for p, c in outputs.items():
        if not p.exists() or read_text(p) != c:
            write_text(p, c)
            log.append(f"updated {p.relative_to(root).as_posix()}")
    for p in orphan_indexes(root, outputs):
        p.unlink()
        log.append(f"removed {p.relative_to(root).as_posix()}")
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if any generated file is out of date")
    args = ap.parse_args(argv)
    root = repo_root()
    if args.check:
        stale, orphans = stale_outputs(root)
        for p in stale:
            print(f"out of date: {p.relative_to(root).as_posix()}")
        for p in orphans:
            print(f"orphan generated index: {p.relative_to(root).as_posix()}")
        return 1 if (stale or orphans) else 0
    log = write_outputs(root)
    print("\n".join(log) if log else "indexes already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
