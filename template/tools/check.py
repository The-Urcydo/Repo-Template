#!/usr/bin/env python3
"""Repo health check: the one command every agent runs before handing work off.

Usage:
  python3 tools/check.py            quiet on success; exit 1 on any error
  python3 tools/check.py --strict   warnings also fail (use in CI once the repo is filled in)
  python3 tools/check.py --json     machine-readable findings
  python3 tools/check.py --stubs    list unfilled placeholders (never fails)

Levels: error (must fix), warn (should fix), info (placeholders: fill or delete).
Standard library only. Findings look like:  ERROR  <code>  <path>[:line]  <message>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_agents  # noqa: E402
import sync_indexes  # noqa: E402
from _lib import (  # noqa: E402
    ADR_STATUSES, DIATAXIS_DIRS, DOC_STATUSES, DOC_TYPES, ITEM_ID_RE, NEEDS_EVIDENCE, SKIP_DIRS,
    STALE_DAYS, STATUSES, FrontMatterError, folder_owners, git_last_change, iter_docs, iter_items,
    iter_markdown, load_catalog, load_modules, load_roles, load_targets, md_links, module_of,
    module_present, parse_date, parse_front_matter, parse_queue, read_fm, read_text, repo_root,
    resolve_link, today,
)

ROOT_AGENTS_MAX_LINES = 100
NESTED_AGENTS_MAX_LINES = 60
DOC_MAX_LINES = 400
SKILL_MAX_LINES = 500
SUMMARY_MAX = 240
QUESTION_WARN_DAYS = 7
ROLE_REQUIRED = ("role", "mission", "reads", "never", "done_when", "escalate_when")
TREE_CHARS = ("├──", "└──", "│  ")


@dataclass
class Finding:
    level: str
    code: str
    where: str
    msg: str


class Report:
    def __init__(self) -> None:
        self.items: list[Finding] = []

    def add(self, level: str, code: str, where: str, msg: str) -> None:
        self.items.append(Finding(level, code, where, msg))

    def error(self, code: str, where: str, msg: str) -> None:
        self.add("error", code, where, msg)

    def warn(self, code: str, where: str, msg: str) -> None:
        self.add("warn", code, where, msg)

    def info(self, code: str, where: str, msg: str) -> None:
        self.add("info", code, where, msg)

    def count(self, level: str) -> int:
        return sum(1 for f in self.items if f.level == level)


def rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


# ----------------------------------------------------------------------- docs
def check_docs(root: Path, rep: Report) -> None:
    for p in iter_docs(root):
        r = rel(root, p)
        text = read_text(p)
        try:
            fm, _ = parse_front_matter(text)
        except FrontMatterError as exc:
            rep.error("front-matter", r, str(exc))
            continue
        if fm is None:
            rep.error("front-matter", r, "missing front matter (title, type, status, summary)")
            continue
        missing = [k for k in ("title", "type", "status", "summary") if not str(fm.get(k) or "").strip()]
        if missing:
            rep.error("front-matter", r, f"missing keys: {', '.join(missing)}")
            continue
        typ, status, summary = str(fm["type"]), str(fm["status"]), str(fm["summary"])
        if typ not in DOC_TYPES:
            rep.error("doc-type", r, f"type '{typ}' not in {', '.join(DOC_TYPES)}")
        allowed = set(DOC_STATUSES) | (set(ADR_STATUSES) if typ == "decision" else set())
        if status not in allowed:
            rep.error("doc-status", r, f"status '{status}' not in {', '.join(sorted(allowed))}")
        if len(summary) > SUMMARY_MAX:
            rep.error("summary-length", r, f"summary is {len(summary)} chars; keep it to one sentence (<= {SUMMARY_MAX})")
        parts = p.relative_to(root / "docs").parts
        if len(parts) > 1 and parts[0] in DIATAXIS_DIRS and typ not in ("index", "meta"):
            if typ != DIATAXIS_DIRS[parts[0]]:
                rep.error("diataxis", r, f"type '{typ}' does not belong in docs/{parts[0]}/ (expects '{DIATAXIS_DIRS[parts[0]]}')")
        if status == "placeholder":
            rep.info("placeholder", r, "unfilled placeholder: fill it or delete it")
        elif summary.upper().startswith("TODO"):
            rep.info("placeholder", r, "summary still says TODO: write the one-sentence summary")
        n_lines = text.count("\n") + 1
        if status != "generated" and n_lines > DOC_MAX_LINES:
            rep.warn("doc-size", r, f"{n_lines} lines; split by topic so agents can load only what they need")
        if "related_code" in fm:
            _check_related_code(root, p, fm, rep)


def _check_related_code(root: Path, p: Path, fm: dict, rep: Report) -> None:
    r = rel(root, p)
    paths = fm.get("related_code") or []
    paths = paths if isinstance(paths, list) else [paths]
    verified = parse_date(fm.get("last_verified"))
    for code_path in map(str, paths):
        if any(c in code_path for c in "*?["):
            continue
        if not (root / code_path).exists():
            rep.error("related-code", r, f"related_code path does not exist: {code_path}")
            continue
        if verified:
            changed = parse_date(git_last_change(root, code_path))
            if changed and changed > verified:
                rep.warn("doc-stale", r, f"{code_path} changed {changed} after last_verified {verified}; re-verify and bump last_verified")


def check_adrs(root: Path, rep: Report) -> None:
    d = root / "docs" / "decisions"
    if not d.is_dir():
        return
    numbers: dict[str, Path] = {}
    by_num: dict[str, dict] = {}
    for p in sorted(d.glob("*.md")):
        if p.name in ("README.md", "INDEX.md"):
            continue
        r = rel(root, p)
        m = re.match(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$", p.name)
        if not m:
            rep.error("adr-name", r, "ADR files are named NNNN-kebab-title.md")
            continue
        if m.group(1) in numbers:
            rep.error("adr-number", r, f"number {m.group(1)} also used by {numbers[m.group(1)].name}; renumber with the latest first")
        numbers[m.group(1)] = p
        fm = read_fm(p)
        by_num[m.group(1)] = fm
        status = str(fm.get("status", ""))
        if status not in ADR_STATUSES:
            rep.error("adr-status", r, f"status '{status}' not in {', '.join(ADR_STATUSES)}")
        if status == "accepted" and not str(fm.get("date", "")).strip():
            rep.error("adr-date", r, "accepted ADRs need a date")
        if status == "superseded" and not fm.get("superseded_by"):
            rep.error("adr-supersede", r, "superseded ADRs need superseded_by")
    for num, fm in by_num.items():
        for key in ("supersedes", "superseded_by"):
            vals = fm.get(key) or []
            vals = vals if isinstance(vals, list) else [vals]
            for v in vals:
                if str(v).zfill(4) not in numbers:
                    rep.error("adr-supersede", rel(root, numbers[num]), f"{key} refers to missing ADR {v}")


# ---------------------------------------------------------------------- links
def check_links(root: Path, rep: Report) -> None:
    modules = load_modules(root)
    for p in iter_markdown(root):
        r = rel(root, p)
        generated = read_fm(p).get("status") == "generated"
        owner_mod = module_of(r, modules)
        for line, target in md_links(read_text(p)):
            dest = resolve_link(p, target, root)
            if dest is None:
                continue
            if not dest.exists():
                rep.error("broken-link", f"{r}:{line}", f"link target not found: {target}")
                continue
            try:
                dest_rel = dest.relative_to(root.resolve()).as_posix()
            except ValueError:
                rep.error("link-outside-repo", f"{r}:{line}", f"link leaves the repo: {target}")
                continue
            dest_mod = module_of(dest_rel, modules)
            if dest_mod and dest_mod != owner_mod and not generated:
                where = f"module '{owner_mod}'" if owner_mod else "core"
                rep.error("module-coupling", f"{r}:{line}",
                          f"{where} links into optional module '{dest_mod}' ({target}); cutting the module would break this. "
                          "Mention it in backticks instead of linking, or move the link into the module.")


# --------------------------------------------------------------- agent files
def check_agents_md(root: Path, rep: Report) -> None:
    top = root / "AGENTS.md"
    if not top.exists():
        rep.error("agents-md", "AGENTS.md", "missing root AGENTS.md")
    for p in sorted(root.rglob("AGENTS.md")):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        r = rel(root, p)
        text = read_text(p)
        n = text.count("\n") + (0 if text.endswith("\n") else 1)
        limit = ROOT_AGENTS_MAX_LINES if p == top else NESTED_AGENTS_MAX_LINES
        if n > limit:
            rep.error("agents-md-size", r, f"{n} lines > budget {limit}. Move detail into docs/ and link to it; every line here is paid for in every session.")
        if any(c in text for c in TREE_CHARS):
            rep.warn("agents-md-tree", r, "contains a directory tree; agents discover structure themselves. Keep only facts they cannot discover.")
        if re.search(r"\bTODO\b|<fill", text):
            rep.info("placeholder", r, "contains TODO/<fill> markers: complete before relying on it")


def check_roles(root: Path, rep: Report) -> None:
    roles = load_roles(root)
    if not roles:
        return
    seen_item: dict[str, str] = {}
    seen_file: dict[str, str] = {}
    for name, r in roles.items():
        p = f"agents/roles/{name}.md"
        if r["error"]:
            rep.error("role", p, r["error"])
            continue
        fm = r["fm"]
        if fm is None:
            rep.error("role", p, "missing front matter")
            continue
        for k in ROLE_REQUIRED:
            if not fm.get(k):
                rep.error("role", p, f"missing '{k}'")
        if fm.get("role") != name:
            rep.error("role", p, f"role '{fm.get('role')}' must equal the filename '{name}'")
        for key, seen in (("item_files", seen_item), ("writes_files", seen_file)):
            for f in fm.get(key) or []:
                if f in seen:
                    rep.error("ownership", p, f"{key} entry '{f}' is also claimed by role '{seen[f]}'; one writer per file")
                seen[str(f)] = name
    for folder, role in sorted(folder_owners(root).items()):
        if role not in roles:
            rep.error("ownership", f"{folder or '.'}/README.md", f"owner_role '{role}' is not a role in agents/roles/")


def check_top_level_readmes(root: Path, rep: Report) -> None:
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in SKIP_DIRS:
            continue
        readme = d / "README.md"
        r = f"{d.name}/README.md"
        if not readme.exists():
            rep.error("folder-readme", d.name + "/", "top-level folders need a README.md with summary and owner_role")
            continue
        fm = read_fm(readme)
        for k in ("summary", "owner_role"):
            if not str(fm.get(k) or "").strip():
                rep.error("folder-readme", r, f"front matter is missing '{k}'")
        if fm.get("status") == "placeholder":
            rep.info("placeholder", r, "unfilled placeholder: fill it or delete the folder")


def check_skills(root: Path, rep: Report) -> None:
    base = root / "agents" / "skills"
    if not base.is_dir():
        return
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        sk = d / "SKILL.md"
        r = rel(root, sk)
        if not sk.exists():
            rep.error("skill", rel(root, d), "skill folder has no SKILL.md")
            continue
        text = read_text(sk)
        try:
            fm, _ = parse_front_matter(text)
        except FrontMatterError as exc:
            rep.error("skill", r, str(exc))
            continue
        fm = fm or {}
        name, desc = str(fm.get("name", "")), str(fm.get("description", ""))
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
            rep.error("skill", r, "name must be 1-64 chars: lowercase letters, digits, single hyphens, no leading/trailing hyphen")
        if name != d.name:
            rep.error("skill", r, f"name '{name}' must match the folder '{d.name}'")
        if not desc.strip() or len(desc) > 1024:
            rep.error("skill", r, "description must be 1-1024 chars and say what the skill does and when to use it")
        n = text.count("\n") + 1
        if n > SKILL_MAX_LINES:
            rep.warn("skill-size", r, f"{n} lines; move detail into references/ (spec recommends < {SKILL_MAX_LINES})")


# ------------------------------------------------------------------ work state
def check_items(root: Path, rep: Report) -> None:
    roles = set(load_roles(root))
    for item in iter_items(root):
        r = rel(root, item.handoff if item.handoff.exists() else item.path)
        if not ITEM_ID_RE.match(item.id):
            rep.error("item-id", r, "item ids look like YYYY-MM-DD-kebab-slug")
        if not item.handoff.exists():
            rep.error("item", rel(root, item.path), "work item folder has no handoff.md")
            continue
        try:
            fm, _ = parse_front_matter(read_text(item.handoff))
        except FrontMatterError as exc:
            rep.error("handoff", r, str(exc))
            continue
        if not fm:
            rep.error("handoff", r, "missing front matter")
            continue
        for k in ("id", "title", "status", "owner_role", "created", "updated"):
            if not str(fm.get(k) or "").strip():
                rep.error("handoff", r, f"missing '{k}'")
        if fm.get("id") != item.id:
            rep.error("handoff", r, f"id '{fm.get('id')}' must equal the item name '{item.id}'")
        status = str(fm.get("status", ""))
        if status not in STATUSES:
            rep.error("handoff", r, f"status '{status}' not in {', '.join(STATUSES)}")
            continue
        if roles and str(fm.get("owner_role")) not in roles:
            rep.error("handoff", r, f"owner_role '{fm.get('owner_role')}' is not a role")
        if status != "done" and not str(fm.get("next_action") or "").strip():
            rep.error("handoff", r, "next_action is empty: say what the next role should do")
        evidence = fm.get("evidence") or []
        if status in NEEDS_EVIDENCE and not (evidence if isinstance(evidence, list) else [evidence]):
            rep.error("handoff", r, f"status {status} needs evidence (commands run, links)")
        if status in ("verified", "done") and not item.light and not (item.path / "review.md").exists():
            rep.error("handoff", r, f"status {status} needs review.md in {item.id}/")
        updated = parse_date(fm.get("updated"))
        if updated is None:
            rep.error("handoff", r, "updated must be an ISO date")
        elif status not in ("done",) and (today() - updated).days > STALE_DAYS:
            rep.warn("item-stale", r, f"not updated for {(today() - updated).days} days; run tools/archive_item.py --sweep")
        elif status == "done" and (today() - updated).days > 7:
            rep.warn("item-archive", r, "done for over a week; run tools/archive_item.py --sweep")


def check_queue(root: Path, rep: Report) -> None:
    p = root / "work" / "HUMAN.md"
    if not p.exists():
        return
    r = rel(root, p)
    text = read_text(p)
    if not re.search(r"^## Open\s*$", text, re.M) or not re.search(r"^## Answered\s*$", text, re.M):
        rep.error("human-queue", r, "needs '## Open' and '## Answered' headings")
        return
    seen: set[str] = set()
    for q in parse_queue(text):
        where = f"{r}:{q['line']}"
        if q["id"] is None:
            rep.error("human-queue", where, f"entry '{q['title']}' must be headed '### Q-0001: title'")
            continue
        if q["id"] in seen:
            rep.error("human-queue", where, f"duplicate id {q['id']}")
        seen.add(q["id"])
        if q["section"] == "open":
            for k in ("asked_by", "date", "recommended", "if_no_answer", "cost_of_wrong"):
                if not q["fields"].get(k):
                    rep.error("human-queue", where, f"{q['id']} is missing '{k}': give a recommendation, a default, and the cost of guessing wrong")
            d = parse_date(q["fields"].get("date"))
            if d and (today() - d).days > QUESTION_WARN_DAYS:
                rep.warn("human-queue", where, f"{q['id']} has waited {(today() - d).days} days; apply its if_no_answer default or re-ask")
        elif not q["fields"].get("answer"):
            rep.error("human-queue", where, f"{q['id']} is in Answered but has no answer")


# ------------------------------------------------------------ generated state
def check_generated(root: Path, rep: Report) -> None:
    stale, orphans = sync_indexes.stale_outputs(root)
    for p in stale:
        rep.error("generated-drift", rel(root, p), "generated file is out of date: run `python3 tools/sync_indexes.py`")
    for p in orphans:
        rep.error("generated-drift", rel(root, p), "orphan generated index: run `python3 tools/sync_indexes.py`")
    for problem in sync_agents.drift(root):
        rep.error("adapter-drift", "agents/adapters/", f"{problem}: run `python3 tools/sync_agents.py`")


def check_modules(root: Path, rep: Report) -> None:
    for name, m in load_catalog(root).items():
        if not module_present(root, m):
            continue
        absent = [p for p in m.get("paths", []) if not (root / p).exists()]
        if absent:
            rep.warn("module-partial", "tools/modules.json",
                     f"module '{name}' is partly present (missing: {', '.join(absent)}); finish the cut with remove_module.py --apply or restore it")
        for dep in m.get("requires") or []:
            if dep not in load_modules(root):
                rep.error("module-requires", "tools/modules.json", f"module '{name}' requires '{dep}', which is not installed")


def check_adapters_config(root: Path, rep: Report) -> None:
    p = root / "agents" / "adapters" / "targets.json"
    if p.exists():
        try:
            load_targets(root)
        except json.JSONDecodeError as exc:
            rep.error("adapters", "agents/adapters/targets.json", f"invalid JSON: {exc}")


# ------------------------------------------------------------------------ main
def run_all(root: Path) -> Report:
    rep = Report()
    check_docs(root, rep)
    check_adrs(root, rep)
    check_links(root, rep)
    check_agents_md(root, rep)
    check_roles(root, rep)
    check_top_level_readmes(root, rep)
    check_skills(root, rep)
    check_items(root, rep)
    check_queue(root, rep)
    check_modules(root, rep)
    check_adapters_config(root, rep)
    check_generated(root, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="warnings fail too")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--stubs", action="store_true", help="list placeholders and exit 0")
    args = ap.parse_args(argv)
    root = repo_root()
    rep = run_all(root)
    if args.stubs:
        stubs = [f for f in rep.items if f.level == "info"]
        for f in stubs:
            print(f"{f.where}  {f.msg}")
        print(f"{len(stubs)} placeholder(s)")
        return 0
    if args.json:
        print(json.dumps([asdict(f) for f in rep.items], indent=2))
    else:
        order = {"error": 0, "warn": 1, "info": 2}
        for f in sorted(rep.items, key=lambda f: (order[f.level], f.code, f.where)):
            if f.level == "info":
                continue
            print(f"{f.level.upper():<5}  {f.code:<16} {f.where}  {f.msg}")
        e, w, i = rep.count("error"), rep.count("warn"), rep.count("info")
        if e or w:
            print(f"-- {e} error(s), {w} warning(s), {i} placeholder(s)")
        else:
            print(f"ok ({i} placeholder(s); list them with: python3 tools/check.py --stubs)")
    failed = rep.count("error") > 0 or (args.strict and rep.count("warn") > 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
