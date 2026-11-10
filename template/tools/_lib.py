"""Shared helpers for the repo tooling. Standard library only (Python 3.9+).

Design rules for everything in tools/:
- No third-party dependencies, so an agent can always just run `python3 tools/<x>.py`.
- Deterministic output, quiet on success, non-zero exit code on failure.
- Functions take `root` explicitly so tests can run against temporary trees.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

TOOLS_DIR = Path(__file__).resolve().parent

# --- work-item state machine (single source of truth; protocol doc mirrors it) ---
STATUSES = ("draft", "planned", "in-progress", "in-review", "verified", "done", "blocked", "stale", "canceled")
TRANSITIONS: dict[str, set[str]] = {
    "draft": {"planned", "blocked", "canceled"},
    "planned": {"in-progress", "blocked", "draft", "canceled"},
    "in-progress": {"in-review", "blocked", "planned", "canceled"},
    "in-review": {"verified", "in-progress", "blocked", "draft", "canceled"},
    "verified": {"done", "in-progress", "canceled"},
    "blocked": {"draft", "planned", "in-progress", "canceled"},
    "stale": {"draft", "planned", "in-progress", "in-review", "canceled"},
    "done": set(),
    "canceled": set(),
}
NEEDS_EVIDENCE = {"in-review", "verified", "done"}
# Who acts next by default after a transition (mirrored in agents/protocols/handoff.md).
DEFAULT_OWNER = {
    "draft": "planner", "planned": "builder", "in-progress": "builder", "in-review": "reviewer",
    "verified": "scribe", "done": "orchestrator", "blocked": "orchestrator", "stale": "orchestrator",
    "canceled": "orchestrator",
}
STALE_DAYS = 14
STALE_REWARN_DAYS = 30
DONE_ARCHIVE_DAYS = 7

DOC_TYPES = ("tutorial", "how-to", "reference", "explanation", "decision", "index", "meta")
DOC_STATUSES = ("placeholder", "draft", "active", "deprecated", "generated")
ADR_STATUSES = ("proposed", "accepted", "rejected", "deprecated", "superseded")
DIATAXIS_DIRS = {
    "tutorials": "tutorial",
    "how-to": "how-to",
    "reference": "reference",
    "explanation": "explanation",
    "decisions": "decision",
}
# Docs are grouped by audience first, then by Diataxis type:
#   docs/dev/<type>/ and docs/user/<type>/  hold the four type folders (TYPE_FOLDERS),
#   docs/decisions/                         is shared by every audience,
#   docs/product, operations, release, security are optional modules, one audience each.
TYPE_FOLDERS = ("tutorials", "how-to", "reference", "explanation")
TYPED_AUDIENCE_DIRS = ("dev", "user")
AUDIENCES = ("dev", "user", "product", "ops", "security")
# Top-level docs folder -> the audience it implies when a doc has no `audience:` key.
DOCS_FOLDER_AUDIENCE = {
    "dev": "dev", "user": "user", "product": "product",
    "operations": "ops", "release": "ops", "security": "security",
}

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".claude", ".cursor", ".gemini", ".idea", ".vscode"}


def repo_root() -> Path:
    env = os.environ.get("REPO_ROOT")
    return Path(env).resolve() if env else TOOLS_DIR.parent


def today() -> dt.date:
    return dt.date.today()


def parse_date(value: Any) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- io
def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    """Atomic write with LF newlines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    os.replace(tmp, path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@contextlib.contextmanager
def file_lock(root: Path, name: str, timeout: float = 15.0) -> Iterator[None]:
    """Cross-process lock via O_EXCL file; stale locks (>60s) are reclaimed."""
    lock_dir = root / "work" / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / f"{name}.lock"
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > 60:
                    path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.time() > deadline:
                raise TimeoutError(f"lock '{name}' is busy")
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


def slugify(text: str, max_len: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:max_len].strip("-")


# ------------------------------------------------------------- front matter
FM_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*)$")


class FrontMatterError(ValueError):
    pass


def _strip_comment(s: str) -> str:
    """Drop a trailing ' # comment'. A quote only opens a quoted scalar at the start of a
    value or right after '[' or ',' (YAML rules), so an apostrophe inside a word is literal."""
    out: list[str] = []
    quote = None
    token_start = True
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
            token_start = False
        elif ch in "\"'" and token_start:
            quote = ch
            token_start = False
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        else:
            token_start = ch in "[," or (ch in " \t" and token_start)
        out.append(ch)
    return "".join(out).rstrip()


_PLAIN_BAD_START = "[]{}*&!|>%@`"


def _guard_plain(s: str) -> None:
    """Reject plain scalars that real YAML parsers reject, so a file that passes our check
    also renders on GitHub and opens in other tools. Quote the value to fix."""
    if s[0] in _PLAIN_BAD_START or ": " in s or s.endswith(":"):
        raise FrontMatterError(f"plain value {s[:40]!r} is not valid YAML; wrap it in double quotes")


def _scalar(s: str) -> Any:
    s = s.strip()
    if s == "":
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        inner = s[1:-1]
        if s[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner.replace("''", "'")
    _guard_plain(s)
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


def _split_inline(s: str) -> list[Any]:
    parts: list[str] = []
    buf: list[str] = []
    quote = None
    token_start = True
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            token_start = False
        elif ch in "\"'" and token_start:
            quote = ch
            buf.append(ch)
            token_start = False
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
            token_start = True
        else:
            buf.append(ch)
            token_start = token_start and ch in " \t"
    parts.append("".join(buf))
    return [_scalar(p) for p in parts if p.strip() != ""]


def parse_front_matter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Parse a small YAML subset: scalars, inline lists, block lists. No nesting.

    Returns (None, text) when the file has no front matter. Raises FrontMatterError
    when the block exists but cannot be parsed.
    """
    m = FM_RE.match(text)
    if not m:
        return None, text
    data: dict[str, Any] = {}
    key: str | None = None
    for offset, raw in enumerate(m.group(1).split("\n"), start=2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        if raw[0] in " \t" or stripped.startswith("- ") or stripped == "-":
            if stripped.startswith("- ") or stripped == "-":
                if key is None:
                    raise FrontMatterError(f"line {offset}: list item without a key")
                if data.get(key) is None:
                    data[key] = []
                if not isinstance(data[key], list):
                    raise FrontMatterError(f"line {offset}: list item under scalar key '{key}'")
                data[key].append(_scalar(_strip_comment(stripped[1:].strip())))
                continue
            raise FrontMatterError(f"line {offset}: nested structures are not supported")
        km = KEY_RE.match(raw)
        if not km:
            raise FrontMatterError(f"line {offset}: cannot parse {raw!r}")
        key, rest = km.group(1), _strip_comment(km.group(2)).strip()
        if key in data:
            raise FrontMatterError(f"line {offset}: duplicate key '{key}'")
        if rest in ("|", ">", "|-", ">-"):
            raise FrontMatterError(f"line {offset}: block scalars are not supported")
        if rest == "":
            data[key] = None
        elif rest.startswith("[") and rest.endswith("]"):
            data[key] = _split_inline(rest[1:-1])
        else:
            data[key] = _scalar(rest)
    return data, text[m.end():]


_RESERVED = {"true", "false", "null", "~", "yes", "no", "on", "off"}


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    s = str(value)
    needs_quote = (
        s == ""
        or s != s.strip()
        or s.lower() in _RESERVED
        or re.fullmatch(r"-?\d+", s) is not None
        or re.search(r"[:#\[\]{},&*!|>'\"%@`]", s) is not None
        or s.startswith(("-", "?"))
    )
    if not needs_quote:
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def yaml_list(items: list[Any]) -> str:
    return "[" + ", ".join(yaml_scalar(i) for i in items) + "]"


def set_fm_value(text: str, key: str, value: str) -> str:
    """Set a top-level key to an already-formatted YAML value. Inserts it if missing."""
    m = FM_RE.match(text)
    if not m:
        raise FrontMatterError("file has no front matter")
    lines = m.group(1).split("\n")
    out: list[str] = []
    replaced = False
    i = 0
    while i < len(lines):
        line = lines[i]
        km = KEY_RE.match(line)
        if km and km.group(1) == key and not line.startswith((" ", "\t")):
            out.append(f"{key}: {value}")
            replaced = True
            i += 1
            while i < len(lines) and lines[i].strip().startswith("-") and (
                lines[i].startswith((" ", "\t")) or lines[i].startswith("- ")
            ):
                i += 1
            continue
        out.append(line)
        i += 1
    if not replaced:
        out.append(f"{key}: {value}")
    return text[: m.start(1)] + "\n".join(out) + text[m.end(1):]


def replace_block(text: str, name: str, content: str) -> str:
    begin = f"<!-- BEGIN GENERATED: {name} -->"
    end = f"<!-- END GENERATED: {name} -->"
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise KeyError(f"generated block '{name}' not found")
    return pattern.sub(lambda _m: f"{begin}\n{content.rstrip()}\n{end}", text, count=1)


GENERATED_BANNER = "<!-- GENERATED by tools/sync_indexes.py. Do not edit by hand; run `python3 tools/sync_indexes.py`. -->"


# --------------------------------------------------------------- file walking
def _skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).parts
    if any(p in SKIP_DIRS for p in rel):
        return True
    if rel[:2] == ("work", "archive") or rel[:2] == ("work", ".locks"):
        return True
    if "scratch" in rel and rel[:2] == ("work", "items"):
        return True
    return False


def iter_markdown(root: Path, include_templates: bool = False) -> Iterator[Path]:
    for p in sorted(root.rglob("*.md")):
        if _skip(p, root):
            continue
        if not include_templates and any(part == "_templates" for part in p.relative_to(root).parts):
            continue
        yield p


def iter_docs(root: Path) -> Iterator[Path]:
    docs = root / "docs"
    if not docs.is_dir():
        return
    for p in sorted(docs.rglob("*.md")):
        rel = p.relative_to(root).parts
        if any(part.startswith("_") for part in rel):
            continue
        if p.name in ("AGENTS.md", "CLAUDE.md"):  # instruction files, not documentation pages
            continue
        yield p


def doc_type_dir(parts: tuple[str, ...]) -> str | None:
    """The type folder a doc sits in, from its path parts relative to docs/.

    Returns one of TYPE_FOLDERS (for docs/<dev|user>/<type>/...), "decisions", or None.
    """
    if len(parts) > 1 and parts[0] == "decisions":
        return "decisions"
    if len(parts) > 2 and parts[0] in TYPED_AUDIENCE_DIRS and parts[1] in TYPE_FOLDERS:
        return parts[1]
    return None


def doc_audience(parts: tuple[str, ...], fm: dict[str, Any]) -> str | None:
    """Audience of a doc: its `audience:` key if set, else the one its top-level folder implies, else None
    (shared docs such as decisions have none)."""
    explicit = str(fm.get("audience") or "").strip()
    if explicit:
        return explicit
    return DOCS_FOLDER_AUDIENCE.get(parts[0]) if len(parts) > 1 else None


# ------------------------------------------------------------------- links
FENCE_RE = re.compile(r"^(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
LINK_RE = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def md_links(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    in_fence = False
    for n, line in enumerate(text.split("\n"), start=1):
        if FENCE_RE.match(line.lstrip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        clean = INLINE_CODE_RE.sub("", line)
        for m in LINK_RE.finditer(clean):
            found.append((n, m.group(1)))
    return found


def resolve_link(src: Path, target: str, root: Path) -> Path | None:
    """Return the filesystem path a link points to, or None if it is external/skippable."""
    t = target.strip()
    if not t or t.startswith("#"):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", t):
        return None
    if any(c in t for c in "{}<>$*"):
        return None
    t = t.split("#")[0].split("?")[0]
    if not t:
        return None
    base = root if t.startswith("/") else src.parent
    return (base / t.lstrip("/")).resolve()


def git_last_change(root: Path, rel: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%cs", "--", rel],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = r.stdout.strip()
    return (out or None) if r.returncode == 0 else None


# ------------------------------------------------------- roles / modules / items
ROLE_FILE = "ROLE.md"
# Optional `access` in a charter, a tool-neutral hint. `read-only`: the role changes only the item files it
# declares and the folders it owns. An adapter may turn it into a tool limit, which is coarser than this rule
# and guards against accidents only (a shell can still change files). Leaving it out means `full`.
ACCESS_LEVELS = ("full", "read-only")
# A tool name an adapter writes unquoted into a subagent file (`Edit`, `NotebookEdit`, `mcp__github__*`).
TOOL_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_*]*")


def load_roles(root: Path) -> dict[str, dict[str, Any]]:
    """Role charters: `agents/roles/<role>/ROLE.md`. The role name is the folder name."""
    roles: dict[str, dict[str, Any]] = {}
    d = root / "agents" / "roles"
    if not d.is_dir():
        return roles
    for folder in sorted(p for p in d.iterdir() if p.is_dir()):
        p = folder / ROLE_FILE
        if not p.is_file():
            continue
        try:
            fm, body = parse_front_matter(read_text(p))
            err = None
        except FrontMatterError as exc:
            fm, body, err = None, "", str(exc)
        roles[folder.name] = {"path": p, "fm": fm, "body": body, "error": err}
    return roles


def skill_folders(root: Path) -> list[tuple[str, Path]]:
    """Every skill folder as (owner, path).

    Shared skills live in `agents/skills/<name>/` and have owner "". A skill that only one role
    uses lives in `agents/roles/<role>/skills/<name>/` and has that role as owner.
    """
    found: list[tuple[str, Path]] = []
    shared = root / "agents" / "skills"
    if shared.is_dir():
        found += [("", p) for p in sorted(shared.iterdir()) if p.is_dir()]
    roles = root / "agents" / "roles"
    if roles.is_dir():
        for folder in sorted(p for p in roles.iterdir() if p.is_dir()):
            lane = folder / "skills"
            if lane.is_dir():
                found += [(folder.name, p) for p in sorted(lane.iterdir()) if p.is_dir()]
    return found


def read_fm(path: Path) -> dict[str, Any]:
    """Front matter of a file, or {} when absent/unreadable (use parse_front_matter to see errors)."""
    try:
        fm, _ = parse_front_matter(read_text(path))
    except (FrontMatterError, OSError, UnicodeDecodeError):
        return {}
    return fm or {}


def load_catalog(root: Path) -> dict[str, dict[str, Any]]:
    """Every module the template knows about, installed or not (tools/modules.json)."""
    p = root / "tools" / "modules.json"
    if not p.exists():
        return {}
    return json.loads(read_text(p)).get("modules", {})


def module_present(root: Path, module: dict[str, Any]) -> bool:
    return any((root / p).exists() for p in module.get("paths", []))


def load_modules(root: Path) -> dict[str, dict[str, Any]]:
    """Installed modules only: a module is installed while any of its paths exists."""
    return {n: m for n, m in load_catalog(root).items() if module_present(root, m)}


def module_of(rel: str, modules: dict[str, dict[str, Any]]) -> str | None:
    rel = rel.strip("/")
    for name, m in modules.items():
        for p in m.get("paths", []):
            p = p.strip("/")
            if rel == p or rel.startswith(p + "/"):
                return name
    return None


def folder_owners(root: Path) -> dict[str, str]:
    """Folder (posix, no trailing slash) -> role, from `owner_role` in that folder's README.md."""
    owners: dict[str, str] = {}
    for p in iter_markdown(root):
        if p.name != "README.md":
            continue
        role = read_fm(p).get("owner_role")
        if role:
            folder = p.parent.relative_to(root).as_posix()
            owners["" if folder == "." else folder] = str(role)
    return owners


def owner_of(rel: str, owners: dict[str, str]) -> str | None:
    """Nearest-ancestor owner of a path (a deeper README overrides a shallower one)."""
    parts = rel.strip("/").split("/")
    for n in range(len(parts), -1, -1):
        key = "/".join(parts[:n])
        if key in owners:
            return owners[key]
    return None


def apply_tokens(text: str, mapping: dict[str, str]) -> str:
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text


def load_targets(root: Path) -> dict[str, dict[str, Any]]:
    p = root / "agents" / "adapters" / "targets.json"
    if not p.exists():
        return {}
    return json.loads(read_text(p))


ITEM_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class Item:
    id: str
    path: Path
    handoff: Path
    light: bool


def iter_items(root: Path) -> Iterator[Item]:
    items = root / "work" / "items"
    if not items.is_dir():
        return
    for p in sorted(items.iterdir()):
        if p.name.startswith((".", "_")) or p.name.lower() == "readme.md":
            continue
        if p.is_dir():
            yield Item(p.name, p, p / "handoff.md", False)
        elif p.suffix == ".md":
            yield Item(p.stem, p, p, True)


def find_item(root: Path, query: str) -> Item:
    items = list(iter_items(root))
    exact = [i for i in items if i.id == query]
    if exact:
        return exact[0]
    partial = [i for i in items if query in i.id]
    if len(partial) == 1:
        return partial[0]
    if not partial:
        raise LookupError(f"no work item matches '{query}'")
    raise LookupError(f"'{query}' is ambiguous: " + ", ".join(i.id for i in partial))


# --------------------------------------------------------- human queue parsing
Q_HEAD_RE = re.compile(r"^### (Q-\d{4}): (.+)$")
Q_FIELD_RE = re.compile(r"^- ([a-z_]+): (.*)$")
Q_REQUIRED_OPEN = ("asked_by", "date", "recommended", "if_no_answer", "cost_of_wrong")


def parse_queue(text: str) -> list[dict[str, Any]]:
    section: str | None = None
    cur: dict[str, Any] | None = None
    out: list[dict[str, Any]] = []
    for n, line in enumerate(text.split("\n"), start=1):
        s = line.strip()
        if s == "## Open":
            section, cur = "open", None
            continue
        if s == "## Answered":
            section, cur = "answered", None
            continue
        if line.startswith("## "):
            section, cur = None, None
            continue
        if section is None:
            continue
        m = Q_HEAD_RE.match(line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2).strip(), "section": section, "fields": {}, "line": n}
            out.append(cur)
            continue
        if line.startswith("### "):
            cur = {"id": None, "title": line[4:].strip(), "section": section, "fields": {}, "line": n}
            out.append(cur)
            continue
        fm = Q_FIELD_RE.match(line)
        if fm and cur is not None:
            cur["fields"][fm.group(1)] = fm.group(2).strip()
    return out
