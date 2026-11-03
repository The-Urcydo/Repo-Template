"""Tests for the template itself (not for a generated repo).

Run from the template root:  python -m pytest tests -q
Needs: pytest, copier>=9.4, git, python3.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[1]
ALL_MODULES = {"product", "operations", "security", "release", "infra", "evals", "github"}
PROFILES = {
    "lean": set(),
    "standard": {"product", "operations", "github"},
    "full": ALL_MODULES,
}
MODULE_PATHS = {
    "product": "docs/product", "operations": "docs/operations", "security": "docs/security",
    "release": "docs/release", "infra": "infra", "evals": "agents/evals", "github": ".github",
}


def copier(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "copier", *args], cwd=cwd, capture_output=True, text=True, timeout=300)


def generate(dest: Path, src: Path = TEMPLATE, *extra: str, **answers: str) -> Path:
    answers.setdefault("project_name", "Test Project")
    data = [x for k, v in answers.items() for x in ("--data", f"{k}={v}")]
    r = copier("copy", "--defaults", "--trust", "-q", *data, *extra, str(src), str(dest))
    assert r.returncode == 0, f"copier copy failed:\n{r.stdout}\n{r.stderr}"
    return dest


def py(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=project, capture_output=True, text=True, timeout=300,
                          env={**os.environ, "REPO_ROOT": str(project)})


def tree(project: Path) -> dict[str, str]:
    out = {}
    for p in sorted(project.rglob("*")):
        if p.is_file() and ".git" not in p.relative_to(project).parts and "__pycache__" not in p.parts:
            out[p.relative_to(project).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@pytest.fixture(scope="module")
def full(tmp_path_factory) -> Path:
    return generate(tmp_path_factory.mktemp("full") / "p", profile="full")


@pytest.mark.parametrize("layout", ["single", "workspace", "data-ml", "minimal"])
@pytest.mark.parametrize("profile", ["lean", "standard", "full"])
def test_profile_generates_a_healthy_repo(tmp_path, profile, layout):
    p = generate(tmp_path / "p", profile=profile, layout=layout)
    r = py(p, "tools/check.py", "--strict")
    assert r.returncode == 0, r.stdout
    for module, path in MODULE_PATHS.items():
        assert (p / path).exists() == (module in PROFILES[profile]), f"{module} wrong for profile {profile}"
    assert (p / "src").exists() == (layout in ("single", "data-ml"))
    assert (p / "apps").exists() == (layout == "workspace")
    assert (p / "packages").exists() == (layout == "workspace")
    assert (p / "data").exists() == (layout == "data-ml")
    assert (p / "notebooks").exists() == (layout == "data-ml")
    assert (p / "tests").exists() == (layout != "minimal")
    # a layout's folder excludes must never reach into tools/ (the unit tests live in tools/tests)
    assert (p / "tools" / "tests" / "test_tools.py").exists(), layout
    # core is always present
    for core in ["AGENTS.md", "README.md", "docs/INDEX.md", "work/ACTIVE.md", "work/HUMAN.md", "agents/ROSTER.md",
                 "tools/check.py", "docs/decisions/0000-use-madr-for-decision-records.md", "agents/roles/builder.md"]:
        assert (p / core).exists(), core


@pytest.mark.parametrize("modules", [[], ["evals"], ["infra", "github"], ["product", "security"]])
def test_custom_profile_picks_exactly_the_chosen_modules(tmp_path, modules):
    data = tmp_path / "answers.yml"
    data.write_text("custom_modules: [" + ", ".join(modules) + "]\n")
    dest = tmp_path / "p"
    r = copier("copy", "--defaults", "--trust", "-q", "--data", "project_name=C", "--data", "profile=custom",
               "--data-file", str(data), str(TEMPLATE), str(dest))
    assert r.returncode == 0, r.stderr
    for module, path in MODULE_PATHS.items():
        assert (dest / path).exists() == (module in modules), module
    assert py(dest, "tools/check.py", "--strict").returncode == 0


def test_no_unrendered_template_syntax_leaks(full):
    bad = []
    for p in full.rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.name == "justfile" or p.suffix == ".pyc":
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "{{" in text or "{%" in text:
            bad.append(p.relative_to(full).as_posix())
        assert ".jinja" not in p.name, p
        if p.suffix in (".md", ".json", ".yml") and "_templates" not in p.parts:
            assert not re.search(r"__[A-Z_]+__", text), f"unfilled work/doc token leaked into {p}"
    assert not bad, bad


def test_template_ships_no_hardcoded_last_verified_date():
    """A date baked into a template doc is older than any project's first commit, so `check --strict` would
    warn `doc-stale` in every generated project (and fail its CI) as soon as the related code is committed."""
    bad = [
        p.relative_to(TEMPLATE).as_posix()
        for p in (TEMPLATE / "template").rglob("*")
        if p.is_file() and re.search(r"^last_verified:", p.read_text(encoding="utf-8", errors="ignore"), re.M)
    ]
    assert not bad, bad


def test_generation_is_deterministic(tmp_path):
    a = tree(generate(tmp_path / "a", profile="full"))
    b = tree(generate(tmp_path / "b", profile="full"))
    answers = ".copier-answers.yml"
    a.pop(answers), b.pop(answers)
    assert a == b


def test_sync_is_idempotent(full):
    before = tree(full)
    for tool in ("tools/sync_indexes.py", "tools/sync_agents.py"):
        assert py(full, tool).returncode == 0
    assert tree(full) == before


def test_tier0_is_small(full):
    text = (full / "AGENTS.md").read_text()
    lines = text.count("\n")
    assert lines <= 60, f"AGENTS.md is {lines} lines; the budget is 100 and the template should leave headroom"
    assert not any(c in text for c in "├└│")
    assert "TODO" in text  # the one thing the owner must fill in


def test_every_documented_command_and_flag_exists(full):
    helps: dict[str, str] = {}

    def help_of(tool: str) -> str:
        if tool not in helps:
            parts = [py(full, f"tools/{tool}.py", "--help").stdout]
            if tool == "question":
                parts += [py(full, f"tools/{tool}.py", sub, "--help").stdout for sub in ("ask", "answer")]
            helps[tool] = "\n".join(parts)
        return helps[tool]

    problems = []
    cmd = re.compile(r"python3 tools/([a-z_]+)\.py([^`\n]*)")
    for p in full.rglob("*.md"):
        rel = p.relative_to(full).as_posix()
        if rel.startswith((".claude/", "work/archive/")) or ".git/" in rel:
            continue
        for m in cmd.finditer(p.read_text(encoding="utf-8")):
            tool, rest = m.group(1), m.group(2)
            if not (full / "tools" / f"{tool}.py").exists():
                problems.append(f"{rel}: unknown tool {tool}")
                continue
            for flag in re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", rest):
                if flag not in help_of(tool) and flag != "--help":
                    problems.append(f"{rel}: {tool} has no flag {flag}")
    assert not problems, "\n".join(sorted(set(problems)))


def test_tutorial_runs_end_to_end(full):
    def run(*args: str) -> str:
        r = py(full, *args)
        assert r.returncode == 0, f"{args}\n{r.stdout}\n{r.stderr}"
        return r.stdout.strip()

    def refuses(*args: str) -> None:
        assert py(full, *args).returncode != 0, f"expected refusal: {args}"

    assert run("tools/check.py").startswith("ok")
    path = run("tools/new_item.py", "hello-world", "--title", "Say hello")
    item = Path(path).parent.name
    assert "draft" in (full / "work/ACTIVE.md").read_text()
    run("tools/transition.py", item, "planned", "--next", "Builder: create the greeting file and verify it exists")
    run("tools/transition.py", item, "in-progress", "--next", "Creating the file")
    run("tools/transition.py", item, "in-review", "--next", "Reviewer: verify criterion 1", "--evidence", "python3 tools/check.py")
    refuses("tools/transition.py", item, "done")
    refuses("tools/transition.py", item, "verified")  # no review.md yet
    run("tools/item_file.py", item, "review")
    run("tools/transition.py", item, "verified", "--next", "Scribe: update docs and changelog", "--evidence", "criterion 1 checked")
    run("tools/transition.py", item, "done")
    run("tools/archive_item.py", item)
    assert run("tools/check.py").startswith("ok")


def test_shipped_unit_tests_pass(full):
    r = py(full, "-m", "unittest", "discover", "-s", "tools/tests")
    assert r.returncode == 0, r.stderr[-3000:]


def test_shipped_unit_tests_ignore_the_projects_own_data(tmp_path):
    """A project in use has work items, open questions and code; none of that may break the tool tests."""
    p = generate(tmp_path / "p", profile="full")
    q = ["tools/question.py", "ask", "Real question?", "--asked-by", "builder", "--recommended", "yes",
         "--if-no-answer", "nothing changes", "--cost", "high: data"]
    assert py(p, *q).returncode == 0
    assert py(p, "tools/new_item.py", "real-work", "--title", "Real work").returncode == 0
    (p / "src" / "big.txt").write_text("x" * 1_000_000)
    r = py(p, "-m", "unittest", "discover", "-s", "tools/tests")
    assert r.returncode == 0, r.stderr[-3000:]


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"git {args}: {r.stderr}"
    return r.stdout


def test_copier_update_merges_improvements_and_respects_cuts(tmp_path):
    # 1. a throwaway git copy of the template at v0.1.0
    tpl = tmp_path / "tpl"
    shutil.copytree(TEMPLATE, tpl, ignore=shutil.ignore_patterns(".git", "__pycache__", "tests", "*.pyc", ".pytest_cache"))
    git(tpl, "init", "-q")
    git(tpl, "add", "-A")
    git(tpl, "commit", "-qm", "v1")
    git(tpl, "tag", "v0.1.0")

    # 2. generate a project, commit it, make a local edit and cut a module
    proj = generate(tmp_path / "proj", tpl, "--vcs-ref", "v0.1.0", profile="full")
    git(proj, "init", "-q")
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "init")
    note = proj / "docs/reference/naming-conventions.md"
    note.write_text(note.read_text() + "\nLocal convention: tabs are banned.\n")
    git(proj, "commit", "-qam", "local edit")
    r = py(proj, "tools/remove_module.py", "evals", "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "cut evals")
    assert "profile: custom" in (proj / ".copier-answers.yml").read_text()

    # 3. the template improves: a new how-to, a new glossary row, and a changed module file
    (tpl / "template/docs/how-to/new-guide.md").write_text(
        "---\ntitle: A new guide\ntype: how-to\nstatus: active\nsummary: Added in template v0.2.0.\n---\n# A new guide\n")
    g = tpl / "template/docs/reference/glossary.md"
    g.write_text(g.read_text() + "| **Zebra** | A new term added upstream |\n")
    ev = tpl / "template/agents/evals/README.md"
    ev.write_text(ev.read_text() + "\nUpstream change to the evals module.\n")
    git(tpl, "add", "-A")
    git(tpl, "commit", "-qm", "v2")
    git(tpl, "tag", "v0.2.0")

    # 4. update the project
    r = copier("update", "--defaults", "--trust", "-q", "--vcs-ref", "v0.2.0", cwd=proj)
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert "_commit: v0.2.0" in (proj / ".copier-answers.yml").read_text()
    assert (proj / "docs/how-to/new-guide.md").exists(), "template improvement not delivered"
    assert "Zebra" in (proj / "docs/reference/glossary.md").read_text()
    assert "tabs are banned" in note.read_text(), "local edit was lost"
    assert not (proj / "agents/evals").exists(), "cut module was resurrected by the update"
    assert "new-guide.md" in (proj / "docs/INDEX.md").read_text(), "tasks did not regenerate the index"
    marker = re.compile(r"^(<<<<<<< |>>>>>>> |=======$)", re.M)  # real markers start a line; docs may mention them
    conflicts = [p for p in proj.rglob("*") if p.is_file() and ".git" not in p.parts
                 and marker.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert not conflicts, conflicts
    r = py(proj, "tools/check.py", "--strict")
    assert r.returncode == 0, r.stdout


def test_front_matter_parser_agrees_with_a_real_yaml_parser(full):
    """Our stdlib parser must accept exactly what PyYAML accepts, with the same values, so files
    that pass tools/check.py also render on GitHub and open in other tools."""
    yaml = pytest.importorskip("yaml")
    import datetime
    sys.path.insert(0, str(full / "tools"))
    try:
        import _lib
        def norm(v):
            if isinstance(v, datetime.date):
                return v.isoformat()
            return [norm(x) for x in v] if isinstance(v, list) else v
        problems, checked = [], 0
        for p in full.rglob("*.md"):
            if ".git" in p.parts:
                continue
            text = p.read_text(encoding="utf-8")
            m = _lib.FM_RE.match(text)
            if not m:
                continue
            checked += 1
            rel = p.relative_to(full).as_posix()
            try:
                real = {k: norm(v) for k, v in (yaml.safe_load(m.group(1)) or {}).items()}
                mine, _ = _lib.parse_front_matter(text)
            except Exception as e:  # either parser rejecting is a defect in a shipped file
                problems.append(f"{rel}: {type(e).__name__}: {e}")
                continue
            for k in set(real) | set(mine):
                a, b = real.get(k), mine.get(k)
                if a != b and not (a in (None, "") and b in (None, "")):
                    problems.append(f"{rel}: key {k}: PyYAML={a!r} ours={b!r}")
        assert checked > 50, "suspiciously few front-matter blocks checked"
        assert not problems, "\n".join(problems)
    finally:
        sys.path.remove(str(full / "tools"))
        sys.modules.pop("_lib", None)


def test_copy_without_trust_fails_with_a_clear_message(tmp_path):
    r = copier("copy", "--defaults", "-q", "--data", "project_name=X", str(TEMPLATE), str(tmp_path / "p"))
    assert r.returncode != 0
    assert "--trust" in (r.stdout + r.stderr)
    assert not (tmp_path / "p" / "AGENTS.md").exists()


def test_template_has_no_stray_artifacts():
    stray = [p for p in (TEMPLATE / "template").rglob("*") if p.name in ("__pycache__", ".DS_Store") or p.suffix == ".pyc"]
    assert not stray
    empty = [p for p in (TEMPLATE / "template").rglob("*") if p.is_dir() and not any(p.iterdir())]
    assert not empty, f"empty dirs are not tracked by git and will vanish: {empty}"
