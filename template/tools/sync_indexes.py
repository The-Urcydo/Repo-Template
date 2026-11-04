#!/usr/bin/env python3
"""Regenerate every derived index in the repo from its source of truth.

Outputs (deterministic, so `--check` can detect drift):
  docs/INDEX.md              one line per doc, grouped by audience then type, from front-matter `summary`
  docs/<folder>/INDEX.md     only when one folder (docs/dev/reference, docs/decisions, ...) has more than
                             SPLIT_THRESHOLD docs; it then lists every doc of that folder
  docs/dev/reference/repo-map.md top-level folders and workspace components, from each folder README `summary`
  docs/dev/reference/modules.md  installed modules and how to cut them
  work/ACTIVE.md             board of in-flight work items, from handoff front matter
  agents/ROSTER.md           roles, their skills, ownership and item files, from agents/roles/<role>/ROLE.md

Usage: python3 tools/sync_indexes.py [--check]
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    DOCS_FOLDER_AUDIENCE, GENERATED_BANNER, SKIP_DIRS, TYPE_FOLDERS, TYPED_AUDIENCE_DIRS, FrontMatterError,
    doc_audience, doc_type_dir, folder_owners, iter_docs, iter_items, load_modules, load_roles,
    parse_front_matter, read_fm, read_text, repo_root, skill_folders, write_text,
)

SPLIT_THRESHOLD = 40
BOARD_LIMIT = 60
STATUS_ORDER = ["blocked", "in-review", "in-progress", "planned", "draft", "stale", "verified", "done", "canceled"]
AUDIENCE_ORDER = ["dev", "user", "product", "ops", "security"]
AUDIENCE_TITLES = {
    "dev": "Contributors (dev)",
    "user": "End users (user)",
    "product": "Product and design (product)",
    "ops": "Operations (ops)",
    "security": "Security (security)",
}
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


@dataclass
class Entry:
    title: str
    rel: str  # path relative to docs/
    summary: str
    status: str
    group: str  # the folder the doc sits in: "dev/reference", "decisions", "operations", "(top level)"
    audience: str | None  # the `audience:` key, else the audience the top-level folder implies, else None (shared)
    implied: str | None  # the audience the folder alone implies

    @property
    def section(self) -> str:
        return self.group.rsplit("/", 1)[-1]


def _group_of(parts: tuple[str, ...]) -> str:
    if len(parts) == 1:
        return "(top level)"
    type_dir = doc_type_dir(parts)
    if type_dir and type_dir != "decisions":
        return f"{parts[0]}/{type_dir}"
    return parts[0]


def _is_folder_guide(parts: tuple[str, ...]) -> bool:
    """The README.md of docs/<folder>/ or of a type folder under an audience: it guides, it is not listed."""
    if parts[-1] != "README.md":
        return False
    return len(parts) <= 2 or (len(parts) == 3 and parts[0] in TYPED_AUDIENCE_DIRS and parts[1] in TYPE_FOLDERS)


def _doc_entries(root: Path, virtual: dict[Path, str]) -> list[Entry]:
    """Every doc the index lists.

    `virtual` holds other generated docs about to be written (repo-map, modules), so the index
    is already correct after a single sync pass instead of changing on the second one.
    """
    entries: list[Entry] = []
    docs = root / "docs"
    paths = set(iter_docs(root)) | {p for p in virtual if docs in p.parents and not p.name.startswith("_")}
    for p in sorted(paths):
        rel = p.relative_to(docs)
        if rel.name == "INDEX.md" or _is_folder_guide(rel.parts):
            continue
        fm = _fm_of(virtual[p]) if p in virtual else read_fm(p)
        entries.append(Entry(
            title=str(fm.get("title") or rel.stem.replace("-", " ").title()),
            rel=rel.as_posix(),
            summary=str(fm.get("summary") or "(no summary)"),
            status=str(fm.get("status") or ""),
            group=_group_of(rel.parts),
            audience=doc_audience(rel.parts, fm),
            implied=DOCS_FOLDER_AUDIENCE.get(rel.parts[0]) if len(rel.parts) > 1 else None,
        ))
    return entries


def _line(title: str, path: str, summary: str, status: str) -> str:
    tag = f" _({status})_" if status in TAGGED else ""
    return f"- [{title}]({path}) — {summary}{tag}"


def _section_title(section: str) -> str:
    return GROUP_TITLES.get(section, section.replace("-", " ").title())


def _section_key(section: str) -> tuple[int, int, str]:
    """Type folders and decisions in teaching order, then other folders A-Z, then top-level files."""
    if section in GROUP_ORDER:
        return (0, GROUP_ORDER.index(section), section)
    return (2, 0, section) if section == "(top level)" else (1, 0, section)


def _guide(root: Path, groups: set[str]) -> str:
    """' — [folder guide](...)' when a section comes from exactly one folder that has a README."""
    if len(groups) == 1:
        g = next(iter(groups))
        if g != "(top level)" and (root / "docs" / g / "README.md").exists():
            return f" — [folder guide]({g}/README.md)"
    return ""


def _audience_folders(root: Path, audience: str) -> list[str]:
    return [f for f, a in DOCS_FOLDER_AUDIENCE.items() if a == audience and (root / "docs" / f).is_dir()]


def build_docs_indexes(root: Path, virtual: dict[Path, str]) -> dict[Path, str]:
    by_group: dict[str, list[Entry]] = {}
    for e in _doc_entries(root, virtual):
        by_group.setdefault(e.group, []).append(e)

    out: dict[Path, str] = {}
    placed: dict[tuple[str | None, str], list[tuple[str, str]]] = {}  # (audience, section) -> [(sort key, line)]
    feeders: dict[tuple[str | None, str], set[str]] = {}  # (audience, section) -> folders that feed it
    for group, items in sorted(by_group.items()):
        items = sorted(items, key=lambda e: e.rel)
        section = items[0].section
        if len(items) > SPLIT_THRESHOLD and group != "(top level)":
            # A big folder keeps its own index listing all of its docs; the main index points to it under the
            # audience the folder implies (an `audience:` key only regroups docs that the main index lists).
            key = (items[0].implied, section)
            pointer = f"- [{len(items)} documents — see the section index]({group}/INDEX.md)"
            placed.setdefault(key, []).append((group, pointer))
            feeders.setdefault(key, set()).add(group)
            title = f"{_section_title(section)} index ({group})"
            sub = [
                _front(title, "index", f"Generated one-line-per-doc map of docs/{group}/.", "scribe"),
                f"# {title}",
                "",
            ]
            sub += [_line(e.title, Path(e.rel).relative_to(group).as_posix(), e.summary, e.status) for e in items]
            out[root / "docs" / group / "INDEX.md"] = "\n".join(sub) + "\n"
            continue
        for e in items:
            key = (e.audience, section)
            placed.setdefault(key, []).append((e.rel, _line(e.title, e.rel, e.summary, e.status)))
            feeders.setdefault(key, set()).add(group)

    lines = [
        _front("Docs index", "index",
               "Generated one-line-per-doc map of docs/. Read this first, then open only what the task needs.",
               "scribe"),
        "# Docs index",
        "",
        "Pick your audience, then what you need: learn, do a task, look up a fact, or understand why.",
        "Placeholders are empty on purpose: fill them or delete them (`python3 tools/check.py --stubs` lists them).",
        "",
    ]
    known = [a for a in AUDIENCE_ORDER if any(k[0] == a for k in placed) or _audience_folders(root, a)]
    other = sorted({k[0] for k in placed if k[0] is not None and k[0] not in AUDIENCE_ORDER})
    for a in known + other:
        sections = sorted({k[1] for k in placed if k[0] == a}, key=_section_key)
        folders = _audience_folders(root, a)
        home = (f" — [folder guide]({folders[0]}/README.md)"
                if len(folders) == 1 and (root / "docs" / folders[0] / "README.md").exists() else "")
        lines += [f"## {AUDIENCE_TITLES.get(a, a.title())}{home}", ""]
        if not sections:
            lines += ["_No documents yet._", ""]
            continue
        show_sections = len(sections) > 1 or sections[0] in GROUP_ORDER
        for s in sections:
            if show_sections:
                lines += [f"### {_section_title(s)}{_guide(root, feeders[(a, s)])}", ""]
            lines += [line for _, line in sorted(placed[(a, s)])]
            lines.append("")
    for s in sorted({k[1] for k in placed if k[0] is None}, key=_section_key):  # shared docs: decisions, top level
        lines += [f"## {_section_title(s)}{_guide(root, feeders[(None, s)])}", ""]
        lines += [line for _, line in sorted(placed[(None, s)])]
        lines.append("")
    out[root / "docs" / "INDEX.md"] = "\n".join(lines).rstrip() + "\n"
    return out


# ------------------------------------------------------------------- repo map
def build_repo_map(root: Path) -> str:
    modules = load_modules(root)
    mod_of: dict[str, str] = {}
    for name, m in modules.items():
        for path in m.get("paths", []):
            top = path.strip("/").split("/")[0]
            # a whole top-level folder is "a module folder"; so is a hidden tool folder (.github) the module's files live in
            if top == path.strip("/") or top.startswith("."):
                mod_of[top] = name
    rows = []
    for d in sorted(root.iterdir()):
        # .github is listed only while its module is installed: a Copilot adapter file alone does not make it a module
        if not d.is_dir() or d.name in SKIP_DIRS or (d.name.startswith(".") and d.name not in mod_of):
            continue
        readme = d / "README.md"
        summary = read_fm(readme).get("summary") if readme.exists() else None
        summary = summary or FALLBACK_SUMMARY.get(d.name) or "(no README.md: add one with a `summary`)"
        mod = f" `[module: {mod_of[d.name]}]`" if d.name in mod_of else ""
        rows.append(f"| `{d.name}/` | {summary}{mod} |")
    ws_rows = []
    for folder in ("apps", "packages"):
        base = root / folder
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name.startswith((".", "_")) or child.name in SKIP_DIRS:
                continue
            fm = read_fm(child / "README.md") if (child / "README.md").exists() else {}
            summary = fm.get("summary") or "(no README.md: add one with a `summary`)"
            raw_deps = fm.get("depends_on") or []
            deps = [str(x).strip() for x in (raw_deps if isinstance(raw_deps, list) else [raw_deps]) if str(x).strip()]
            dep_str = ", ".join(f"`{x}`" for x in deps) if deps else "—"
            ws_rows.append(f"| `{folder}/{child.name}/` | {summary} | {dep_str} |")
    ws_section = ""
    if ws_rows:
        ws_section = (
            "\n## Workspace components\n\n"
            "| Component | Purpose | Depends on |\n|---|---|---|\n"
            + "\n".join(ws_rows) + "\n"
        )
    return (
        _front("Repo map", "reference", "Generated table of top-level folders, workspace components, and what each is for.", "scribe")
        + "# Repo map\n\n| Folder | Purpose |\n|---|---|\n" + "\n".join(rows) + "\n" + ws_section
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
    role_skills: dict[str, list[str]] = {}
    shared_skills: list[str] = []
    for owner, skill in skill_folders(root):
        if not (skill / "SKILL.md").is_file():
            continue
        if owner:
            role_skills.setdefault(owner, []).append(skill.name)
        else:
            shared_skills.append(skill.name)
    lines = [
        _front("Agent roster", "reference",
               "Generated table of agent roles, their exclusive skills, what each owns, and which work-item files each writes.",
               "architect"),
        "# Agent roster",
        "",
        "Ownership comes from each folder README's `owner_role` (nearest ancestor wins) plus each role's `ROLE.md` in `roles/<role>/`.",
        "Exclusive skills live under the role that uses them; shared skills are listed after the table.",
        "Dispatch rule: `protocols/handoff.md`.",
        "",
        "| Role | Mission | Owns (exclusive writes) | Item files | Exclusive skills |",
        "|---|---|---|---|---|",
    ]
    for name, r in sorted(roles.items()):
        fm = r["fm"] or {}
        own = list(owned.get(name, []))
        own += [f"`{f}`" for f in (fm.get("writes_files") or [])]
        items = ", ".join(f"`{f}`" for f in (fm.get("item_files") or [])) or "—"
        skills = ", ".join(f"[`{s}`](roles/{name}/skills/{s}/SKILL.md)" for s in role_skills.get(name, [])) or "—"
        lines.append(f"| [`{name}`](roles/{name}/ROLE.md) | {fm.get('mission', '(missing)')} | {', '.join(own) or '—'} | {items} | {skills} |")
    if shared_skills:
        links = ", ".join(f"[`{s}`](skills/{s}/SKILL.md)" for s in shared_skills)
        lines += ["", f"Shared skills (any role): {links}."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- orchestration
def build_outputs(root: Path) -> dict[Path, str]:
    out: dict[Path, str] = {}
    if (root / "docs").is_dir():
        other: dict[Path, str] = {}
        reference = root / "docs" / "dev" / "reference"
        if reference.is_dir():
            other[reference / "repo-map.md"] = build_repo_map(root)
            other[reference / "modules.md"] = build_modules_doc(root)
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
    return [p for p in sorted(docs.rglob("INDEX.md")) if p not in outputs]


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
