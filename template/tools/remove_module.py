#!/usr/bin/env python3
"""Cut an optional module out of the repo cleanly.

Usage:
  python3 tools/remove_module.py                 list modules (installed / not)
  python3 tools/remove_module.py <name>          preview what would be removed (dry run)
  python3 tools/remove_module.py <name> --apply  remove it, then re-sync indexes/adapters and run the checks

Afterwards, if the repo came from the Copier template, .copier-answers.yml is updated
(profile: custom, custom_modules: what remains) so `copier update` does not bring the module back.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_agents  # noqa: E402
import sync_indexes  # noqa: E402
from _lib import load_catalog, load_modules, module_present, read_text, repo_root, write_text  # noqa: E402


def update_answers(root: Path, remaining: list[str]) -> bool:
    path = root / ".copier-answers.yml"
    if not path.exists():
        return False
    lines = read_text(path).split("\n")
    out: list[str] = []
    skipping = False
    for line in lines:
        if re.match(r"^(profile|custom_modules):", line):
            skipping = line.startswith("custom_modules:")
            continue
        if skipping and re.match(r"^\s*-\s", line):
            continue
        skipping = False
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    out.append("profile: custom")
    if remaining:
        out.append("custom_modules:")
        out += [f"- {m}" for m in sorted(remaining)]
    else:
        out.append("custom_modules: []")
    write_text(path, "\n".join(out) + "\n")
    return True


def _prune_empty_parents(root: Path, path: Path) -> None:
    parent = path.parent
    while parent != root and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?")
    ap.add_argument("--apply", action="store_true", help="actually remove (default is a dry run)")
    args = ap.parse_args(argv)
    root = repo_root()
    catalog = load_catalog(root)
    if not args.name:
        for n, m in sorted(catalog.items()):
            state = "installed" if module_present(root, m) else "not installed"
            print(f"{n:<12} {state:<14} {m.get('summary', '')}")
        return 0
    if args.name not in catalog:
        print(f"error: unknown module '{args.name}'. Known: {', '.join(sorted(catalog))}", file=sys.stderr)
        return 2
    mod = catalog[args.name]
    installed = load_modules(root)
    if args.name not in installed:
        print(f"{args.name} is not installed; nothing to do")
        return 0
    dependants = [n for n, m in installed.items() if args.name in (m.get("requires") or [])]
    if dependants:
        print(f"error: module(s) {', '.join(dependants)} require '{args.name}'; remove those first", file=sys.stderr)
        return 2
    targets = [p for p in mod["paths"] if (root / p).exists()]
    print(f"module '{args.name}': {mod.get('summary', '')}")
    for p in targets:
        print(f"  {'remove' if args.apply else 'would remove'}: {p}")
    if mod.get("removal_notes"):
        print(f"  note: {mod['removal_notes']}")
    if not args.apply:
        print("dry run. Re-run with --apply to remove.")
        return 0
    for p in targets:
        full = root / p
        shutil.rmtree(full) if full.is_dir() else full.unlink()
        _prune_empty_parents(root, full)
    remaining = [n for n in installed if n != args.name]
    if update_answers(root, remaining):
        print("  updated .copier-answers.yml (profile: custom)")
    sync_agents.sync(root)  # first: adapters can create or delete files the indexes describe
    sync_indexes.write_outputs(root)
    check = root / "tools" / "check.py"
    result = subprocess.run([sys.executable, str(check)], cwd=root, env={**__import__("os").environ, "REPO_ROOT": str(root)})
    print("module removed." + ("" if result.returncode == 0 else " check.py reports problems: fix them (usually dangling mentions)."))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
