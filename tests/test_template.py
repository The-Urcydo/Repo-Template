"""Tests for the template itself (not for a generated repo).

Run from the template root:  python -m pytest tests -q
Needs: pytest, copier>=9.4, git, python3.
"""
from __future__ import annotations

import hashlib
import json
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
    vcs = [] if "--vcs-ref" in extra else ["--vcs-ref", "HEAD"]
    r = copier("copy", "--defaults", "--trust", "-q", *data, *vcs, *extra, str(src), str(dest))
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
    if layout == "data-ml":
        ignore = (p / ".gitignore").read_text(encoding="utf-8")
        for pattern in ("data/raw/", ".ipynb_checkpoints/", "*.parquet"):
            assert pattern in ignore, pattern
    # a layout's folder excludes must never reach into tools/ (the unit tests live in tools/tests)
    assert (p / "tools" / "tests" / "test_tools.py").exists(), layout
    # core is always present
    for core in ["AGENTS.md", "README.md", "docs/INDEX.md", "work/ACTIVE.md", "work/HUMAN.md", "agents/ROSTER.md",
                 "tools/check.py", "docs/decisions/0000-use-madr-for-decision-records.md", "agents/roles/builder/ROLE.md",
                 "docs/dev/how-to/README.md", "docs/dev/reference/repo-map.md", "docs/user/README.md"]:
        assert (p / core).exists(), core
    # docs are grouped by audience: the four type folders live under docs/dev/, never at the top of docs/
    for type_folder in ("tutorials", "how-to", "reference", "explanation"):
        assert (p / "docs" / "dev" / type_folder).is_dir(), type_folder
        assert not (p / "docs" / type_folder).exists(), f"docs/{type_folder}/ must not exist at the top level"


@pytest.mark.parametrize("modules", [[], ["evals"], ["infra", "github"], ["product", "security"]])
def test_custom_profile_picks_exactly_the_chosen_modules(tmp_path, modules):
    data = tmp_path / "answers.yml"
    data.write_text("custom_modules: [" + ", ".join(modules) + "]\n")
    dest = tmp_path / "p"
    r = copier("copy", "--defaults", "--trust", "-q", "--vcs-ref", "HEAD", "--data", "project_name=C", "--data", "profile=custom",
               "--data-file", str(data), str(TEMPLATE), str(dest))
    assert r.returncode == 0, r.stderr
    for module, path in MODULE_PATHS.items():
        assert (dest / path).exists() == (module in modules), module
    # the security role is a whole bundle folder (charter + skills/): cutting the module removes all of it
    assert (dest / "agents" / "roles" / "security").exists() == ("security" in modules)
    assert py(dest, "tools/check.py", "--strict").returncode == 0


def test_every_role_is_a_bundle_with_a_skills_folder(full):
    roles = full / "agents" / "roles"
    bundles = sorted(p for p in roles.iterdir() if p.is_dir())
    assert bundles, "no role folders"
    for b in bundles:
        assert (b / "ROLE.md").is_file(), f"{b.name} has no ROLE.md"
        assert (b / "skills").is_dir(), f"{b.name} has no skills/ folder (keep an empty one with .gitkeep)"
    flat = [p.name for p in roles.glob("*.md") if p.name.lower() != "readme.md"]
    assert not flat, f"flat role files left behind: {flat}"


def test_roster_lists_role_and_shared_skills(full):
    text = (full / "agents" / "ROSTER.md").read_text(encoding="utf-8")
    assert "roles/reviewer/skills/verify-work/SKILL.md" in text, "role-exclusive skill missing from roster"
    assert "skills/write-doc/SKILL.md" in text, "shared skill missing from roster"
    assert "Shared skills (any role)" in text
    assert "roles/scribe/skills/write-doc" not in text, "write-doc is shared, not scribe-only"


def test_no_unrendered_template_syntax_leaks(full):
    bad = []
    for p in full.rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.name == "justfile" or p.suffix == ".pyc":
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        # `${{ ... }}` is a GitHub Actions expression, not a Jinja leak (Copier renders only *.jinja files)
        if re.search(r"(?<!\$)\{\{", text) or "{%" in text:
            bad.append(p.relative_to(full).as_posix())
        assert ".jinja" not in p.name, p
        if p.suffix in (".md", ".json", ".yml") and "_templates" not in p.parts:
            assert not re.search(r"__[A-Z_]+__", text), f"unfilled work/doc token leaked into {p}"
    assert not bad, bad


def test_template_name_is_consistent():
    for rel in ("README.md", "copier.yml", "template/CHANGELOG.md", "template/README.md.jinja",
                "template/docs/dev/how-to/bootstrap-from-template.md"):
        text = (TEMPLATE / rel).read_text(encoding="utf-8")
        assert "agent-repo-skeleton" not in text, rel


def test_root_only_copier_excludes_are_anchored():
    text = (TEMPLATE / "copier.yml").read_text(encoding="utf-8")
    for path in ("docs/product", "docs/operations", "docs/security", "SECURITY.md",
                 "agents/roles/security", "work/_templates/security-review.md", "docs/release",
                 "infra", "agents/evals", ".github", "apps", "packages"):
        assert f'/{path}' in text, path


def test_workflows_pin_actions_and_declare_permissions():
    paths = sorted((TEMPLATE / ".github" / "workflows").glob("*.yml"))
    paths += sorted((TEMPLATE / "template" / ".github" / "workflows").glob("*.yml"))
    assert paths, "no workflows found"
    for p in paths:
        text = p.read_text(encoding="utf-8")
        assert re.search(r"^permissions:\s*$", text, re.M), p
        assert re.search(r"^\s+contents:\s*read\s*$", text, re.M), p
        uses = re.findall(r"^\s*-?\s*uses:\s*(\S+)", text, re.M)
        assert uses, p
        for target in uses:
            assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", target), f"{p}: {target} is not pinned to a full SHA"


def test_dependabot_configs_are_valid_and_grouped(full):
    yaml = pytest.importorskip("yaml")
    for p in (TEMPLATE / ".github" / "dependabot.yml", full / ".github" / "dependabot.yml"):
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert data["version"] == 2, p
        actions = [u for u in data["updates"] if u["package-ecosystem"] == "github-actions"]
        assert actions, p
        assert actions[0]["schedule"]["interval"] == "weekly", p
        assert actions[0]["groups"], p


def test_github_module_registers_dependabot():
    modules = json.loads((TEMPLATE / "template" / "tools" / "modules.json").read_text(encoding="utf-8"))
    assert ".github/dependabot.yml" in modules["modules"]["github"]["paths"]


def test_agents_md_lists_every_generated_adapter_output():
    for rel in ("AGENTS.md.jinja", "agents/AGENTS.md"):
        text = (TEMPLATE / "template" / rel).read_text(encoding="utf-8")
        for token in (".claude/", ".cursor/rules/", "CLAUDE.md", "copilot-instructions.md", ".gemini/settings.json"):
            assert token in text, f"{rel} does not mention {token}"


def test_every_tool_is_documented_in_tools_readme_and_commands_ref():
    tools_dir = TEMPLATE / "template" / "tools"
    tools_readme = (tools_dir / "README.md").read_text(encoding="utf-8")
    commands_doc = (TEMPLATE / "template" / "docs" / "dev" / "reference" / "commands.md").read_text(encoding="utf-8")
    for p in sorted(tools_dir.glob("*.py")):
        if p.name == "_lib.py":
            continue
        assert p.name in tools_readme, f"tools/README.md does not document {p.name}"
        assert p.name in commands_doc, f"docs/dev/reference/commands.md does not document {p.name}"


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
            elif tool == "worktree":
                parts += [py(full, f"tools/{tool}.py", sub, "--help").stdout for sub in ("create", "remove", "list")]
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
    run("tools/transition.py", item, "planned", "--next", "Builder: create the greeting file and verify it exists", "--by", "planner")
    run("tools/transition.py", item, "in-progress", "--next", "Creating the file", "--by", "builder")
    run("tools/transition.py", item, "in-review", "--next", "Reviewer: verify criterion 1", "--evidence", "python3 tools/check.py", "--by", "builder")
    refuses("tools/transition.py", item, "done")
    refuses("tools/transition.py", item, "verified", "--next", "x")  # no review.md yet
    run("tools/item_file.py", item, "review")
    run("tools/transition.py", item, "verified", "--next", "Scribe: update docs and changelog", "--evidence", "criterion 1 checked", "--by", "reviewer")
    run("tools/transition.py", item, "done", "--by", "scribe")
    run("tools/archive_item.py", item)
    assert run("tools/check.py").startswith("ok")


def test_eval_harness_verifies_all_golden_tasks(full):
    listing = py(full, "tools/eval_harness.py", "--list")
    assert listing.returncode == 0, f"{listing.stdout}\n{listing.stderr}"
    expected = len([line for line in listing.stdout.splitlines() if line.strip()])
    r = py(full, "tools/eval_harness.py", "--verify-fixtures")
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert r.stdout.count("PASS") == expected, r.stdout


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
    note = proj / "docs/dev/reference/naming-conventions.md"
    note.write_text(note.read_text() + "\nLocal convention: tabs are banned.\n")
    git(proj, "commit", "-qam", "local edit")
    r = py(proj, "tools/remove_module.py", "evals", "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "cut evals")
    assert "profile: custom" in (proj / ".copier-answers.yml").read_text()

    # 3. the template improves: a new how-to, a new glossary row, and a changed module file
    (tpl / "template/docs/dev/how-to/new-guide.md").write_text(
        "---\ntitle: A new guide\ntype: how-to\nstatus: active\nsummary: Added in template v0.2.0.\n---\n# A new guide\n")
    g = tpl / "template/docs/dev/reference/glossary.md"
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
    assert (proj / "docs/dev/how-to/new-guide.md").exists(), "template improvement not delivered"
    assert "Zebra" in (proj / "docs/dev/reference/glossary.md").read_text()
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


@pytest.mark.parametrize("profile,layout", [("lean", "minimal"), ("full", "workspace")])
def test_pre_commit_hook_ships_in_every_profile_executable_and_never_switched_on(tmp_path, profile, layout):
    p = generate(tmp_path / "p", profile=profile, layout=layout)
    hook = p / ".githooks" / "pre-commit"
    assert hook.is_file() and os.access(hook, os.X_OK), "the hook must ship with its executable bit"
    assert hook.read_text().startswith("#!/bin/sh\n")
    assert "hooks:\n    git config core.hooksPath .githooks" in (p / "justfile").read_text()
    git(p, "init", "-q")
    r = subprocess.run(["git", "-C", str(p), "config", "--local", "--get", "core.hooksPath"], capture_output=True, text=True)
    assert r.stdout.strip() == "", "the template must not turn the hook on by itself"
    assert py(p, "tools/check.py", "--strict").returncode == 0


def test_cursor_and_copilot_adapters_ship_disabled(full):
    targets = json.loads((full / "agents" / "adapters" / "targets.json").read_text(encoding="utf-8"))
    assert targets["cursor"]["enabled"] is False
    assert targets["copilot"]["enabled"] is False
    assert targets["gemini"]["enabled"] is False
    assert not (full / ".cursor").exists()
    assert not (full / ".github" / "copilot-instructions.md").exists()
    assert not (full / ".gemini").exists()


# --- template update notifier (tools/template_status.py + .github/workflows/template-update.yml) ---------------------
def test_template_update_workflow_is_weekly_and_can_only_open_an_issue():
    yaml = pytest.importorskip("yaml")
    path = TEMPLATE / "template" / ".github" / "workflows" / "template-update.yml"
    text = path.read_text(encoding="utf-8")
    wf = yaml.safe_load(text)
    triggers = wf.get("on", wf.get(True))  # PyYAML reads the bare key `on` as True
    assert set(triggers) == {"schedule", "workflow_dispatch"}, "no push or pull_request trigger: it must not run on code"
    assert re.fullmatch(r"\d+ \d+ \* \* \d", triggers["schedule"][0]["cron"]), "weekly, at an off-peak minute"
    assert wf["permissions"] == {"contents": "read"}
    (job,) = wf["jobs"].values()
    assert job["permissions"] == {"contents": "read", "issues": "write"}, "an issue is the only write it may do"
    assert 0 < job["timeout-minutes"] <= 15
    checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"].get("persist-credentials") is False
    assert not re.search(r"gh pr |git push|git commit|pull-requests:|pip install|pipx ", text), "the notifier opens an issue, never a PR (decision 6)"
    assert "python3 tools/template_status.py --check" in text and "gh issue create" in text
    assert "gh issue list --label template-update --state open" in text, "dedupe by the label, not one issue per version"
    assert "docs/decisions/0008" not in text, "do not link a doc a behind project may not have"
    assert "github.event" not in text, "no event data reaches the shell"
    assert ".github/workflows/template-update.yml" in json.loads(
        (TEMPLATE / "template" / "tools" / "modules.json").read_text(encoding="utf-8"))["modules"]["github"]["paths"]


def test_template_status_is_documented_where_every_tool_is(full):
    assert "template_status.py" in (full / "tools" / "README.md").read_text(encoding="utf-8")
    commands = (full / "docs/dev/reference/commands.md").read_text(encoding="utf-8")
    assert "`template_status.py" in commands and "tools/template_status.py" in commands.split("related_code:")[1].split("\n")[0]
    assert "template_status.py" in (full / "docs/dev/how-to/update-from-template.md").read_text(encoding="utf-8")
    r = py(full, "tools/template_status.py", "--check")  # a fresh local-source project: nothing to compare, never an error
    assert r.returncode == 0, r.stdout + r.stderr


# --- settings as code: repository rulesets and the how-to that goes with them --------------------------------------
RULESETS = TEMPLATE / "template" / ".github" / "rulesets"
RULESET_KEYS = {"name", "target", "enforcement", "conditions", "rules", "bypass_actors"}  # what GitHub's importer reads
PULL_REQUEST_PARAMS = {  # the parameters of a live ruleset's `pull_request` rule (read from the API, 2026-11-12)
    "required_approving_review_count", "dismiss_stale_reviews_on_push", "required_reviewers", "require_code_owner_review",
    "dismissal_restriction", "require_last_push_approval", "required_review_thread_resolution",
    "require_extra_approval_for_unattributed_changes", "allowed_merge_methods",
}
HOW_TO = "docs/dev/how-to/protect-the-repo.md"


def _ruleset(name: str) -> dict:
    return json.loads((RULESETS / f"{name}.json").read_text(encoding="utf-8"))


def test_shipped_rulesets_are_well_formed_json():
    # Shape only: GitHub's import is the owner's dry run, not a test here.
    files = sorted(RULESETS.glob("*.json"))
    assert [f.stem for f in files] == ["protect-default-branch", "protect-release-tags"]
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert set(data) == RULESET_KEYS, f"{f.name}: {set(data) ^ RULESET_KEYS}"
        assert data["name"] == f.stem and data["enforcement"] == "active"
        assert data["bypass_actors"] == [], "no hidden bypass: the owner who needs one adds it knowingly"
        assert {r["type"] for r in data["rules"]} <= {"deletion", "non_fast_forward", "update", "pull_request", "required_status_checks"}
        assert len({r["type"] for r in data["rules"]}) == len(data["rules"]), "a rule type may appear only once"


def test_default_branch_ruleset_works_for_a_solo_owner_and_requires_the_ci_job():
    rs = _ruleset("protect-default-branch")
    assert rs["target"] == "branch" and rs["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    rules = {r["type"]: r.get("parameters", {}) for r in rs["rules"]}
    assert {"deletion", "non_fast_forward", "pull_request", "required_status_checks"} == set(rules)
    pr = rules["pull_request"]
    assert set(pr) <= PULL_REQUEST_PARAMS, set(pr) - PULL_REQUEST_PARAMS
    assert pr["required_approving_review_count"] == 0, "1 approval deadlocks a repository with one human"
    assert pr["allowed_merge_methods"] == ["merge"] and pr["dismiss_stale_reviews_on_push"] is True
    assert pr["require_extra_approval_for_unattributed_changes"] is False, \
        "GitHub defaults this to true, which would make a team's Copilot PR need an extra review"
    contexts = [c["context"] for c in rules["required_status_checks"]["required_status_checks"]]
    yaml = pytest.importorskip("yaml")
    jobs = yaml.safe_load((TEMPLATE / "template" / ".github" / "workflows" / "check.yml").read_text(encoding="utf-8"))["jobs"]
    # GitHub reports a job's `name` when set, otherwise its id, as the required status context.
    assert contexts == ["check"] and contexts[0] in jobs
    assert jobs[contexts[0]].get("name", contexts[0]) == contexts[0], "rename the context when the job display name changes"


def test_release_tag_ruleset_makes_published_tags_permanent():
    rs = _ruleset("protect-release-tags")
    assert rs["target"] == "tag" and rs["conditions"]["ref_name"]["include"] == ["refs/tags/v*"]
    assert {r["type"] for r in rs["rules"]} == {"update", "deletion", "non_fast_forward"}


def test_github_module_owns_the_rulesets_and_the_how_to(full):
    modules = json.loads((TEMPLATE / "template" / "tools" / "modules.json").read_text(encoding="utf-8"))
    github = modules["modules"]["github"]
    assert ".github/rulesets" in github["paths"] and HOW_TO in github["paths"]
    assert "ruleset" in github["removal_notes"].lower(), "cutting the module removes the rulesets too; say so"
    repo_map = (full / "docs/dev/reference/repo-map.md").read_text(encoding="utf-8")
    assert "rulesets" in repo_map.lower(), "the generated repo map must describe the module as it is now"


def test_cutting_the_github_module_leaves_neither_rulesets_nor_how_to(full, tmp_path):
    assert (full / ".github/rulesets/protect-default-branch.json").is_file() and (full / HOW_TO).is_file()
    lean = generate(tmp_path / "lean", profile="lean")
    assert not (lean / ".github").exists() and not (lean / HOW_TO).exists()
    assert py(lean, "tools/check.py", "--strict").returncode == 0


def test_the_how_to_names_every_setting_a_file_cannot_set(full):
    text = (full / HOW_TO).read_text(encoding="utf-8")
    lowered = text.lower()
    for topic in ("Import a ruleset", "secret scanning", "push protection", "private vulnerability reporting", "Dependabot",
                  "code scanning", "Workflow permissions", "release immutability"):
        assert topic.lower() in lowered, topic
    for fact in ("not enabled by default", "public repositories", "read repository contents and packages permissions",
                 "merge commits", "scratch repository"):
        assert fact in lowered, fact
    assert "protect-default-branch.json" in text and "protect-release-tags.json" in text


# --- upgrade across the docs layout move (ADR 0008) -------------------------------------------------------------
MIGRATION = TEMPLATE / "migrations" / "docs_layout.py"
OLD_TAG = "v0.2.0"  # the last release that shipped docs/{explanation,how-to,reference,tutorials}/
BROKEN_TAG = "v0.3.0"  # the release that moved the folders without a migration


def _have_tag(tag: str) -> bool:
    r = subprocess.run(["git", "-C", str(TEMPLATE), "rev-parse", "--verify", "-q", f"{tag}^{{commit}}"], capture_output=True)
    return r.returncode == 0


def _require_tag(tag: str) -> None:
    if _have_tag(tag):
        return
    why = f"tag {tag} not available (shallow clone): git fetch --depth=1 origin tag {tag}"
    if os.environ.get("CI"):  # a CI that cannot see the tag must not silently lose the upgrade test
        pytest.fail(why + "; CI needs `fetch-depth: 0` on the checkout")
    pytest.skip(why)


def _clear_tree(tpl: Path) -> None:
    for child in tpl.iterdir():
        if child.name != ".git":
            shutil.rmtree(child) if child.is_dir() else child.unlink()


def _add_release(tpl: Path, tag: str) -> None:
    """Commit the tree that `tag` released in the real repo, then tag it in the throwaway repo."""
    import io
    import tarfile
    _clear_tree(tpl)
    old = subprocess.run(["git", "-C", str(TEMPLATE), "archive", tag], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(old)) as tf:
        tf.extractall(tpl, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    git(tpl, "add", "-A")
    git(tpl, "commit", "-qm", tag)
    git(tpl, "tag", tag)


_COPY_IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", "*.pyc", ".pytest_cache", ".venv", ".mypy_cache", ".ruff_cache", ".DS_Store",
)


def _template_copy_ignore(directory: str, names: list[str]) -> set[str]:
    """Copy the template repo, but not its own root tests/ and plans/: nested template/tests and
    template/tools/tests are shipped to projects and must stay in the fixture."""
    skip = set(_COPY_IGNORE(directory, names))
    if Path(directory).resolve() == TEMPLATE:
        skip |= {"tests", "plans"} & set(names)
    return skip


def _release_repo(tmp_path: Path, *tags: str) -> Path:
    """A throwaway template repo: each released tag as it was, then the current tree tagged one version ahead.
    Copier refuses to update to an untagged HEAD (it reads that as a downgrade), so the current tree needs a tag."""
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    git(tpl, "init", "-q")
    for tag in tags:
        _add_release(tpl, tag)
    _clear_tree(tpl)
    shutil.copytree(TEMPLATE, tpl, dirs_exist_ok=True, ignore=_template_copy_ignore)
    git(tpl, "add", "-A")
    git(tpl, "commit", "-qm", "current tree")
    git(tpl, "tag", "v99.0.0")
    return tpl


def _doc(title: str, kind: str, body: str) -> str:
    return f"---\ntitle: {title}\ntype: {kind}\nstatus: active\nsummary: Written by the project, not shipped by the template.\n---\n# {title}\n\n{body}\n"


def test_update_across_the_docs_layout_move_keeps_the_projects_own_docs(tmp_path):
    _require_tag(OLD_TAG)
    tpl = _release_repo(tmp_path, OLD_TAG)
    proj = generate(tmp_path / "proj", tpl, "--vcs-ref", OLD_TAG, profile="full")
    git(proj, "init", "-q")
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "init")

    # realistic local work: two docs of the project's own in the old folders, linking to each other and to shipped docs
    (proj / "docs/how-to/deploy-to-staging.md").write_text(_doc(
        "Deploy to staging", "how-to",
        "See [commands](../reference/commands.md), [handoffs](../explanation/ownership-and-handoffs.md), "
        "[the split](../decisions/0001-split-the-repo-by-volatility.md), [docs home](../INDEX.md) and "
        "[the site](https://example.com/a/../b)."))
    (proj / "docs/explanation/our-architecture.md").write_text(_doc(
        "Our architecture", "explanation", "Deploy steps: [staging](../how-to/deploy-to-staging.md#steps)."))
    agents_md = proj / "AGENTS.md"
    agents_md.write_text(agents_md.read_text() + "\nOur rule: never deploy on Fridays.\n")
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "local work")

    r = copier("update", "--defaults", "--trust", "-q", cwd=proj)
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert "_commit: v99.0.0" in (proj / ".copier-answers.yml").read_text()
    assert "migrate: docs/how-to/deploy-to-staging.md -> docs/dev/how-to/deploy-to-staging.md" in r.stdout, r.stdout

    # the current template ships these; a fixture that drops a nested tests/ folder would hide their loss
    assert (proj / "tools/tests/test_tools.py").is_file(), "the update deleted the shipped test suite"
    assert (proj / "tests/README.md").is_file(), "the update deleted the shipped tests folder"

    # the project's own docs moved with the layout, and nothing is left behind in the old folders
    assert (proj / "docs/dev/how-to/deploy-to-staging.md").exists(), "own how-to was not moved"
    assert (proj / "docs/dev/explanation/our-architecture.md").exists(), "own explanation was not moved"
    stale = [p.relative_to(proj).as_posix() for d in ("explanation", "how-to", "reference", "tutorials")
             for p in (proj / "docs" / d).rglob("*") if p.is_file()]
    assert not stale, f"files left in the old layout: {stale}"

    # relative links were recomputed from the new location; absolute URLs were left alone
    how_to = (proj / "docs/dev/how-to/deploy-to-staging.md").read_text()
    assert "(../reference/commands.md)" in how_to and "(../explanation/ownership-and-handoffs.md)" in how_to
    assert "(../../decisions/0001-split-the-repo-by-volatility.md)" in how_to and "(../../INDEX.md)" in how_to
    assert "(https://example.com/a/../b)" in how_to
    assert "(../how-to/deploy-to-staging.md#steps)" in (proj / "docs/dev/explanation/our-architecture.md").read_text()

    assert "never deploy on Fridays" in agents_md.read_text(), "local edit was lost"
    assert "deploy-to-staging.md" in (proj / "docs/INDEX.md").read_text(), "generated index was not rebuilt after the move"
    conflicts = [p for p in proj.rglob("*") if p.is_file() and ".git" not in p.parts
                 and re.search(r"^(<{7} |>{7} |={7}$)", p.read_text(encoding="utf-8", errors="ignore"), re.M)]
    assert not conflicts, conflicts
    r = py(proj, "tools/check.py", "--strict")
    assert r.returncode == 0, r.stdout

    # the migration is idempotent: a second run on the migrated project changes nothing
    r = py(proj, str(MIGRATION), ".")
    assert r.returncode == 0 and not r.stdout.strip(), r.stdout + r.stderr


def test_update_from_v0_3_0_repairs_the_docs_layout(tmp_path):
    _require_tag(BROKEN_TAG)
    tpl = _release_repo(tmp_path, BROKEN_TAG)
    proj = generate(tmp_path / "proj", tpl, "--vcs-ref", BROKEN_TAG, profile="full")
    git(proj, "init", "-q")
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "init")

    # a project that crossed v0.3.0 before this migration shipped: its own docs are still in the old folders
    (proj / "docs/how-to").mkdir(parents=True, exist_ok=True)
    (proj / "docs/how-to/stranded.md").write_text(_doc(
        "Stranded", "how-to", "See [the split](../decisions/0001-split-the-repo-by-volatility.md)."))
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "stranded doc")

    r = copier("update", "--defaults", "--trust", "-q", cwd=proj)
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert "_commit: v99.0.0" in (proj / ".copier-answers.yml").read_text()
    assert "migrate: docs/how-to/stranded.md -> docs/dev/how-to/stranded.md" in r.stdout, r.stdout
    assert (proj / "docs/dev/how-to/stranded.md").is_file(), "a project already on v0.3.0 was not repaired"
    assert not (proj / "docs/how-to/stranded.md").exists()
    moved = (proj / "docs/dev/how-to/stranded.md").read_text()
    assert "(../../decisions/0001-split-the-repo-by-volatility.md)" in moved
    assert "stranded.md" in (proj / "docs/INDEX.md").read_text(), "generated index was not rebuilt"
    r = py(proj, "tools/check.py", "--strict")
    assert r.returncode == 0, r.stdout


def test_docs_layout_migration_never_overwrites_and_skips_what_the_template_ships(tmp_path):
    proj = tmp_path / "p"
    for rel, text in {
        ".gitignore": ".DS_Store\n",
        "docs/how-to/ours.md": "# ours\n",
        "docs/how-to/add-a-role.md": "# shipped at the old path: the new template delivers its own copy\n",
        "docs/how-to/taken.md": "# old copy\n",
        "docs/how-to/fenced.md": "`````markdown\n```\n[example](../decisions/0001-split-the-repo-by-volatility.md)\n```\n`````\n",
        "docs/dev/how-to/taken.md": "# already at the new path\n",
        "docs/reference/INDEX-like.md": "<!-- GENERATED by tools/sync_indexes.py -->\n",
        "docs/reference/notes.txt": "plain text moves too\n",
        "docs/other/untouched.md": "# not one of the four folders\n",
    }.items():
        (proj / rel).parent.mkdir(parents=True, exist_ok=True)
        (proj / rel).write_text(text)
    git(proj, "init", "-q")
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "old layout")
    # .DS_Store is ignored and must not abort the migration; draft.md is untracked but not ignored.
    (proj / "docs/how-to/.DS_Store").write_bytes(b"\0\1")
    (proj / "docs/how-to/draft.md").write_text("# draft\n")
    r = py(proj, str(MIGRATION), str(proj))
    assert r.returncode == 0, r.stderr
    assert (proj / "docs/dev/how-to/ours.md").read_text() == "# ours\n"
    assert (proj / "docs/dev/reference/notes.txt").exists()
    assert (proj / "docs/how-to/add-a-role.md").exists() and not (proj / "docs/dev/how-to/add-a-role.md").exists()
    assert (proj / "docs/reference/INDEX-like.md").exists(), "a generated file must be rebuilt, not moved"
    assert (proj / "docs/dev/how-to/taken.md").read_text() == "# already at the new path\n"
    assert (proj / "docs/how-to/taken.md").read_text() == "# old copy\n", "an existing target must never be overwritten"
    assert "already exists" in r.stderr
    assert (proj / "docs/how-to/.DS_Store").exists(), "an ignored file must be left alone, not abort the migration"
    assert not (proj / "docs/dev/how-to/.DS_Store").exists()
    assert (proj / "docs/dev/how-to/draft.md").read_text() == "# draft\n", "an untracked file must move and be staged"
    assert "(../decisions/0001-split-the-repo-by-volatility.md)" in (proj / "docs/dev/how-to/fenced.md").read_text()
    assert (proj / "docs/other/untouched.md").exists()
    assert "migrate: docs/how-to/ours.md -> docs/dev/how-to/ours.md" in r.stdout
    staged = git(proj, "diff", "--cached", "--name-status")
    assert "docs/dev/how-to/ours.md" in staged, "moves must be staged: Copier snapshots the index after the before stage"
    assert "docs/dev/how-to/draft.md" in staged, "an untracked move must be staged too"


# --- shipped CI hardening (check.yml, dependabot.yml) ------------------------------------------------------------
SHIPPED_GITHUB = TEMPLATE / "template" / ".github"


def _shipped_workflow(name: str) -> dict:
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load((SHIPPED_GITHUB / "workflows" / name).read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))  # PyYAML reads the bare key `on` as the boolean True
    return data


def test_shipped_check_workflow_is_fast_safe_and_queue_ready():
    wf = _shipped_workflow("check.yml")
    assert {"push", "pull_request", "merge_group"} <= set(wf["on"]), "merge_group lets the check run in a merge queue"
    assert wf["permissions"] == {"contents": "read"}
    group = wf["concurrency"]
    assert "pull_request.number" in group["group"] and "github.ref" in group["group"]
    assert "pull_request" in str(group["cancel-in-progress"]), "only superseded pull request runs may be cancelled"
    assert {"check", "workflow-lint"} <= set(wf["jobs"]), "the job id `check` is the status a ruleset requires"
    for name, job in wf["jobs"].items():
        assert 0 < job["timeout-minutes"] <= 30, f"{name} needs a timeout so a hung step cannot burn the runner for 6 hours"
        extra = {k: v for k, v in job.get("permissions", {}).items() if v not in ("read",)}
        assert not extra, f"{name} must not ask for more than read: {extra}"
        assert all(step.get("with", {}).get("persist-credentials") is False
                   for step in job["steps"] if str(step.get("uses", "")).startswith("actions/checkout@")), name


def test_shipped_workflow_lint_job_pins_both_linters():
    text = (SHIPPED_GITHUB / "workflows" / "check.yml").read_text(encoding="utf-8")
    job = _shipped_workflow("check.yml")["jobs"]["workflow-lint"]
    zizmor = [s for s in job["steps"] if str(s.get("uses", "")).startswith("zizmorcore/zizmor-action@")]
    assert len(zizmor) == 1 and re.fullmatch(r"zizmorcore/zizmor-action@[0-9a-f]{40}", zizmor[0]["uses"])
    assert zizmor[0]["with"]["advanced-security"] is False, "the SARIF upload needs security-events: write and GHAS"
    assert re.fullmatch(r"\d+\.\d+\.\d+", str(zizmor[0]["with"]["version"])), "pin the zizmor version too"
    assert re.search(r"^\s*sha256=[0-9a-f]{64}\s*$", text, re.M), "the actionlint download is pinned by checksum"
    assert "sha256sum -c" in text and re.search(r"^\s*version=\d+\.\d+\.\d+\s*$", text, re.M)
    assert not re.search(r"releases/latest|@main|@master", text)


def test_shipped_dependabot_waits_a_week_before_a_new_release_is_proposed():
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load((SHIPPED_GITHUB / "dependabot.yml").read_text(encoding="utf-8"))
    for entry in data["updates"]:
        assert entry["cooldown"]["default-days"] >= 7, entry["package-ecosystem"]


@pytest.mark.skipif(not shutil.which("actionlint"), reason="actionlint not installed")
def test_shipped_workflows_pass_actionlint():
    r = subprocess.run(["actionlint", "-color=false", *map(str, sorted((SHIPPED_GITHUB / "workflows").glob("*.yml")))],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("zizmor"), reason="zizmor not installed")
def test_shipped_github_files_pass_zizmor_offline():
    r = subprocess.run(["zizmor", "--offline", "--no-progress", "--format=plain", str(SHIPPED_GITHUB)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# --- the security policy a project starts with --------------------------------------------------------------------------

def test_shipped_security_policy_works_out_of_the_box_but_stays_flagged_until_finished(full, tmp_path):
    text = (full / "SECURITY.md").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "do not open a public issue" in lowered
    assert "private vulnerability reporting" in lowered and "report a vulnerability" in lowered
    assert "public" in lowered and "settings" in lowered, "say it is for public repositories and the owner switches it on"
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), "an invented address would be published by mistake"
    assert not re.search(r"\b\d+\s*(hours?|days?|weeks?)\b", lowered), "the template must not promise a response time"
    for heading in ("## Reporting a vulnerability", "## Supported versions", "## What to expect"):
        assert heading in text, heading
    assert re.search(r"\bTODO\b", text) and "<fill" in text, "an unfilled policy must stay listed by check.py --stubs"
    assert "SECURITY.md" in py(full, "tools/check.py", "--stubs").stdout
    done = tmp_path / "done"
    shutil.copytree(full, done, symlinks=True)
    finished = re.sub(r"(?m)^TODO:.*\n\n", "", text).replace("<fill: a contact address or private channel>", "the maintainers' private channel")
    (done / "SECURITY.md").write_text(finished, encoding="utf-8")
    assert "SECURITY.md" not in py(done, "tools/check.py", "--stubs").stdout, "filling the two markers must clear the flag"
