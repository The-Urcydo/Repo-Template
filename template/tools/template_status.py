#!/usr/bin/env python3
"""Say whether a newer release of the template this repo was generated from is available.

Usage:
  python3 tools/template_status.py            # print one line; always exit 0
  python3 tools/template_status.py --check    # exit 1 only when a newer release exists

Reads `_src_path` and `_commit` from .copier-answers.yml and asks the template's git remote for its release tags
(`git ls-remote`, 20 s timeout, nothing is cloned or changed). Only plain `vX.Y.Z` tags count. A source that is a
local path, unreachable or private, or a repo not generated from a template, prints a line starting `unknown` or
`not generated` and exits 0: the check must never fail because the network did.
To update: `copier update --trust` (docs/dev/how-to/update-from-template.md).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import repo_root  # noqa: E402

RELEASE_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
BUILD_RE = re.compile(r"^(v\d+\.\d+\.\d+)(?:-\d+-g[0-9a-f]+)?$")  # `git describe` output: v0.3.0 or v0.3.0-39-ge31e9ee
SHORTHANDS = {"gh:": "https://github.com/", "gl:": "https://gitlab.com/"}
REMOTE_RE = re.compile(r"^(https?|ssh|git|file)://|^git@[^:]+:")
TIMEOUT_SECONDS = 20


def parse_answers(text: str) -> "dict[str, str]":
    """Top-level `key: value` scalars of a Copier answers file; comments, lists and nested lines are skipped."""
    out: "dict[str, str]" = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        if m and m.group(2) and not m.group(2).startswith("#"):
            out[m.group(1)] = m.group(2).strip("'\"")
    return out


def source_url(src: str) -> Optional[str]:
    """A git URL for a Copier source, or None when it is a local path (nothing to ask)."""
    src = src.strip()
    for prefix, base in SHORTHANDS.items():
        if src.startswith(prefix):
            name = src[len(prefix):].rstrip("/")
            if name.endswith(".git"):
                name = name[:-4]  # Copier records `gh:owner/repo.git` verbatim; do not add a second .git
            return f"{base}{name}.git"
    if src.startswith("git+"):
        src = src[4:]
    return src if REMOTE_RE.match(src) else None


def _version(tag: str) -> "tuple[int, int, int]":
    m = RELEASE_RE.match(tag)
    assert m
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def latest_release(tags: Sequence[str]) -> Optional[str]:
    releases = [t for t in tags if RELEASE_RE.match(t)]
    return max(releases, key=_version) if releases else None


def release_of(commit: str) -> Optional[str]:
    m = BUILD_RE.match(commit.strip())
    return m.group(1) if m else None


def list_tags(url: str) -> "list[str]":
    r = subprocess.run(
        ["git", "ls-remote", "--tags", "--refs", url], capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},  # never wait for a password; keep proxy settings
    )
    if r.returncode != 0:
        raise OSError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "git ls-remote failed")
    return [ref.split("refs/tags/", 1)[1] for ref in (line.split("\t")[-1] for line in r.stdout.splitlines()) if "refs/tags/" in ref]


def status(root: Path, lister: Callable[[str], "list[str]"] = list_tags) -> "tuple[str, bool]":
    """(one line for the human, behind?)"""
    path = root / ".copier-answers.yml"
    if not path.is_file():
        return "not generated from a template: no .copier-answers.yml", False
    answers = parse_answers(path.read_text(encoding="utf-8"))
    src, commit = answers.get("_src_path", ""), answers.get("_commit", "")
    url = source_url(src) if src else None
    if url is None:
        return f"unknown: the template source '{src or '(none)'}' is a local path, nothing to compare with", False
    current = release_of(commit)
    if current is None:
        return f"unknown: cannot read a release from _commit '{commit or '(none)'}'", False
    try:
        latest = latest_release(lister(url))
    except (OSError, subprocess.SubprocessError) as e:
        return f"unknown: could not read the releases of {url} ({e})", False
    if latest is None:
        return f"unknown: {url} has no vX.Y.Z release tags", False
    if _version(latest) > _version(current):
        return (f"behind: {latest} available (you are on {current}). "
                f"Update on a clean repo: copier update --trust (docs/dev/how-to/update-from-template.md)"), True
    return f"up to date ({current}, latest release {latest})", False


def main(argv: "Sequence[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="Say whether a newer template release is available.")
    ap.add_argument("--check", action="store_true", help="exit 1 when a newer release exists (default: always 0)")
    args = ap.parse_args(argv)
    line, behind = status(repo_root())
    print(line)
    return 1 if (behind and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
