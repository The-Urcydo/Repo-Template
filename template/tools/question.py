#!/usr/bin/env python3
"""Manage the single human decision queue, work/HUMAN.md.

Usage:
  python3 tools/question.py ask "Title" --asked-by ROLE --recommended "option" \\
        --if-no-answer "what happens by default" --cost "low|medium|high: why" \\
        [--options "A; B; C"] [--item ITEM-ID]
  python3 tools/question.py answer Q-0001 "the decision" [--by NAME]
  python3 tools/question.py list

Use this for decisions that are irreversible, risky, spend money or change scope, and for a
directive of the human that is ambiguous while the human is not in the session
(agents/protocols/escalation.md). A choice of your own that nobody spoke about: decide and note it.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import file_lock, load_roles, parse_queue, read_text, repo_root, today, write_text  # noqa: E402

NONE = "_None._"


def _sections(text: str) -> tuple[list[str], list[str], list[str]]:
    """Split HUMAN.md into (head, open_lines, answered_lines)."""
    lines = text.split("\n")
    try:
        i_open = next(i for i, l in enumerate(lines) if l.strip() == "## Open")
        i_ans = next(i for i, l in enumerate(lines) if l.strip() == "## Answered")
    except StopIteration:
        raise ValueError("work/HUMAN.md must contain '## Open' and '## Answered' headings")
    if i_ans < i_open:
        raise ValueError("'## Open' must come before '## Answered' in work/HUMAN.md")
    return lines[: i_open + 1], lines[i_open + 1: i_ans], lines[i_ans:]


def _blocks(section: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    for line in section:
        if line.startswith("### "):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    return [[l for l in b] for b in blocks]


def _render(head: list[str], open_blocks: list[list[str]], answered_head: list[str], answered_blocks: list[list[str]]) -> str:
    out = list(head) + [""]
    if open_blocks:
        for b in open_blocks:
            out += _strip(b) + [""]
    else:
        out += [NONE, ""]
    out += answered_head  # includes the "## Answered" heading and any prose under it
    for b in answered_blocks:
        out += [""] + _strip(b)
    return "\n".join(out).rstrip() + "\n"


def _strip(block: list[str]) -> list[str]:
    while block and not block[-1].strip():
        block = block[:-1]
    return block


def _next_id(text: str) -> str:
    nums = [int(m.group(1)) for m in re.finditer(r"^### Q-(\d{4}):", text, re.M)]
    return f"Q-{(max(nums) + 1) if nums else 1:04d}"


def _load(root: Path) -> tuple[Path, str]:
    path = root / "work" / "HUMAN.md"
    if not path.exists():
        raise FileNotFoundError("work/HUMAN.md does not exist")
    return path, read_text(path)


def ask(root: Path, title: str, asked_by: str, recommended: str, if_no_answer: str, cost: str,
        options: str | None, item: str | None) -> str:
    roles = load_roles(root)
    if roles and asked_by not in roles:
        raise ValueError(f"unknown role '{asked_by}' for --asked-by; roles: {', '.join(sorted(roles))}")
    with file_lock(root, "human-queue"):
        path, text = _load(root)
        head, open_lines, answered = _sections(text)
        qid = _next_id(text)
        block = [f"### {qid}: {title.strip()}",
                 f"- asked_by: {asked_by}", f"- date: {today().isoformat()}"]
        if item:
            block.append(f"- item: {item}")
        if options:
            block.append(f"- options: {options}")
        block += [f"- recommended: {recommended}", f"- if_no_answer: {if_no_answer}", f"- cost_of_wrong: {cost}"]
        open_blocks = _blocks(open_lines) + [block]
        answered_head, answered_blocks = _split_answered(answered)
        write_text(path, _render(head, open_blocks, answered_head, answered_blocks))
    return qid


def _split_answered(answered: list[str]) -> tuple[list[str], list[list[str]]]:
    idx = next((i for i, l in enumerate(answered) if l.startswith("### ")), len(answered))
    head = _strip(answered[:idx])
    return head, _blocks(answered[idx:])


def answer(root: Path, qid: str, text_answer: str, by: str) -> str:
    with file_lock(root, "human-queue"):
        path, text = _load(root)
        head, open_lines, answered = _sections(text)
        open_blocks = _blocks(open_lines)
        match = [b for b in open_blocks if b[0].startswith(f"### {qid}:")]
        if not match:
            raise LookupError(f"{qid} is not an open question")
        block = _strip(match[0]) + [f"- answer: {text_answer.strip()}", f"- answered_by: {by}",
                                    f"- answered: {today().isoformat()}"]
        remaining = [b for b in open_blocks if b is not match[0]]
        answered_head, answered_blocks = _split_answered(answered)
        write_text(path, _render(head, remaining, answered_head, [block] + answered_blocks))
    return f"{qid} answered"


def listing(root: Path) -> list[str]:
    _, text = _load(root)
    return [f"{q['id']}: {q['title']} (asked by {q['fields'].get('asked_by', '?')}, {q['fields'].get('date', '?')}; "
            f"recommended: {q['fields'].get('recommended', '?')})"
            for q in parse_queue(text) if q["section"] == "open"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask")
    a.add_argument("title", help="short question the human can answer in one word")
    a.add_argument("--asked-by", required=True, help="your role (must exist in agents/roles/)")
    a.add_argument("--recommended", required=True, help="the option you would pick")
    a.add_argument("--if-no-answer", required=True, help="what happens by default; for anything irreversible: nothing changes")
    a.add_argument("--cost", required=True, help="low|medium|high: what guessing wrong would cost")
    a.add_argument("--options", help="the choices, separated by semicolons")
    a.add_argument("--item", help="id of the work item this question blocks, if any")
    r = sub.add_parser("answer")
    r.add_argument("id")
    r.add_argument("text")
    r.add_argument("--by", default="human")
    sub.add_parser("list")
    args = ap.parse_args(argv)
    root = repo_root()
    try:
        if args.cmd == "ask":
            print(ask(root, args.title, args.asked_by, args.recommended, args.if_no_answer, args.cost,
                      args.options, args.item))
        elif args.cmd == "answer":
            print(answer(root, args.id, args.text, args.by))
        else:
            lines = listing(root)
            print("\n".join(lines) if lines else "no open questions")
    except (ValueError, LookupError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
