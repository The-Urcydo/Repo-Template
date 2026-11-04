"""Tests for the repo tooling. Standard library only.

Run:  python3 -m unittest discover -s tools/tests
Each test works on a throwaway copy of this repo, so nothing here touches your real files.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import _lib  # noqa: E402
import eval_harness  # noqa: E402


_SKIP_ANYWHERE = shutil.ignore_patterns(".git", "__pycache__", ".locks", "*.pyc", "node_modules", ".venv")
_CODE_FOLDERS = {"src", "apps", "packages", "data", "notebooks", "tests"}  # product code is irrelevant here and may be huge
_VOLATILE = ("items", "archive", "inbox", "research")  # work/ subfolders that hold real project data


def _ignore(directory: str, names: list[str]) -> set[str]:
    skip = set(_SKIP_ANYWHERE(directory, names))
    if Path(directory) == ROOT:
        skip |= _CODE_FOLDERS & set(names)
    return skip


def clone(dest: Path) -> Path:
    """A throwaway copy of the harness with the project's own data removed and the generated files
    rebuilt, so a real project's work items, open questions and code cannot change what these tests see."""
    repo = dest / "repo"
    shutil.copytree(ROOT, repo, ignore=_ignore)
    for sub in _VOLATILE:
        folder = repo / "work" / sub
        for child in list(folder.iterdir()) if folder.is_dir() else []:
            if child.name.lower() != "readme.md":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    queue = repo / "work" / "HUMAN.md"
    text = queue.read_text(encoding="utf-8")
    queue.write_text(text[: text.index("## Open")] + "## Open\n\n_None._\n\n## Answered\n", encoding="utf-8")
    for tool in ("sync_indexes", "sync_agents"):  # generated files are derived from the tree we just pruned
        r = run(repo, tool)
        if r.returncode != 0:
            raise RuntimeError(f"{tool} failed on the test fixture:\n{r.stdout}\n{r.stderr}")
    return repo


def run(repo: Path, tool: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "tools" / f"{tool}.py"), *args],
        cwd=repo, env={**os.environ, "REPO_ROOT": str(repo)}, capture_output=True, text=True, timeout=120,
    )


class RepoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = clone(Path(self._tmp.name))

    def sh(self, tool: str, *args: str) -> subprocess.CompletedProcess:
        return run(self.repo, tool, *args)

    def ok(self, tool: str, *args: str) -> str:
        r = self.sh(tool, *args)
        self.assertEqual(r.returncode, 0, f"{tool} {args} failed:\n{r.stdout}\n{r.stderr}")
        return r.stdout.strip()

    def fails(self, tool: str, *args: str) -> str:
        r = self.sh(tool, *args)
        self.assertNotEqual(r.returncode, 0, f"{tool} {args} should have failed:\n{r.stdout}")
        return r.stdout + r.stderr

    def new_item(self, slug: str = "login-flow", *extra: str) -> str:
        path = self.ok("new_item", slug, *extra)
        return Path(path).parent.name if path.endswith("handoff.md") else Path(path).stem


class FrontMatterTests(unittest.TestCase):
    def test_parses_scalars_and_lists(self) -> None:
        fm, body = _lib.parse_front_matter(
            "---\ntitle: \"Hello: world\"\nn: 3\nflag: true\ntags: [a, \"b, c\", d]\nitems:\n- x\n- y\nnote: a # comment\n---\nbody\n"
        )
        self.assertEqual(fm["title"], "Hello: world")
        self.assertEqual(fm["n"], 3)
        self.assertIs(fm["flag"], True)
        self.assertEqual(fm["tags"], ["a", "b, c", "d"])
        self.assertEqual(fm["items"], ["x", "y"])
        self.assertEqual(fm["note"], "a")
        self.assertEqual(body, "body\n")

    def test_apostrophe_inside_a_word_is_not_a_quote(self) -> None:
        fm, _ = _lib.parse_front_matter(
            "---\nnever: [change code, change an accepted ADR's decision, don't guess]\nnote: it's fine # c\n---\n"
        )
        self.assertEqual(fm["never"], ["change code", "change an accepted ADR's decision", "don't guess"])
        self.assertEqual(fm["note"], "it's fine")

    def test_quotes_still_group_at_token_start(self) -> None:
        fm, _ = _lib.parse_front_matter("---\nk: ['a, b', \"c, d\", e's]\n---\n")
        self.assertEqual(fm["k"], ["a, b", "c, d", "e's"])

    def test_rejects_plain_values_that_real_yaml_rejects(self) -> None:
        for bad in ["summary: harness: roles", "summary: ends with colon:", "summary: [unclosed", "summary: `code` first",
                    "summary: *star", "summary: @at", "k: [a, b: c]"]:
            with self.assertRaises(_lib.FrontMatterError, msg=bad):
                _lib.parse_front_matter(f"---\n{bad}\n---\n")

    def test_no_front_matter(self) -> None:
        fm, body = _lib.parse_front_matter("# just a heading\n")
        self.assertIsNone(fm)
        self.assertEqual(body, "# just a heading\n")

    def test_rejects_duplicates_and_nesting(self) -> None:
        with self.assertRaises(_lib.FrontMatterError):
            _lib.parse_front_matter("---\na: 1\na: 2\n---\n")
        with self.assertRaises(_lib.FrontMatterError):
            _lib.parse_front_matter("---\na:\n  b: 1\n---\n")

    def test_set_value_replaces_and_inserts(self) -> None:
        text = "---\nstatus: draft\nevidence:\n- old\nz: 1\n---\nbody\n"
        text = _lib.set_fm_value(text, "evidence", _lib.yaml_list(["a", "b: c"]))
        text = _lib.set_fm_value(text, "extra", "v")
        fm, _ = _lib.parse_front_matter(text)
        self.assertEqual(fm["evidence"], ["a", "b: c"])
        self.assertEqual(fm["z"], 1)
        self.assertEqual(fm["extra"], "v")

    def test_yaml_scalar_round_trips_awkward_values(self) -> None:
        for value in ["plain", "with: colon", "has # hash", "true", "123", "", "say \"hi\"", "- dash", "a, b"]:
            fm, _ = _lib.parse_front_matter(f"---\nk: {_lib.yaml_scalar(value)}\n---\n")
            self.assertEqual(str(fm["k"]), value, value)

    def test_links_ignore_code(self) -> None:
        text = "[a](x.md)\n`[b](y.md)`\n```\n[c](z.md)\n```\n[d](https://e.com)\n"
        self.assertEqual([t for _, t in _lib.md_links(text)], ["x.md", "https://e.com"])


class HealthTests(RepoTestCase):
    def test_fresh_repo_is_healthy(self) -> None:
        self.assertIn("ok", self.ok("check"))
        self.ok("check", "--strict")

    def test_json_output(self) -> None:
        data = json.loads(self.ok("check", "--json"))
        self.assertIsInstance(data, list)
        self.assertTrue(all({"level", "code", "where", "msg"} <= set(f) for f in data))

    def test_stubs_listing_never_fails(self) -> None:
        self.assertIn("placeholder", self.ok("check", "--stubs"))

    def test_stubs_report_release_placeholders(self) -> None:
        out = self.ok("check", "--stubs")
        for where in ("README.md", "SECURITY.md", ".github/CODEOWNERS"):
            self.assertIn(where, out)

    def test_invalid_adapter_targets_report_without_crashing(self) -> None:
        p = self.repo / "agents" / "adapters" / "targets.json"
        p.write_text("{not json\n", encoding="utf-8")
        out = self.fails("check")
        self.assertIn("adapters", out)
        self.assertNotIn("Traceback", out)

        p.write_text("[]\n", encoding="utf-8")
        out = self.fails("check")
        self.assertIn("adapters", out)
        self.assertNotIn("Traceback", out)

    def test_agents_md_over_budget_fails(self) -> None:
        p = self.repo / "AGENTS.md"
        p.write_text(p.read_text() + "\n".join(f"- extra rule {i}" for i in range(120)) + "\n")
        self.assertIn("agents-md-size", self.fails("check"))

    def test_broken_link_fails(self) -> None:
        p = self.repo / "docs" / "dev" / "explanation" / "design-rationale.md"
        p.write_text(p.read_text() + "\nSee [nowhere](does-not-exist.md).\n")
        self.assertIn("broken-link", self.fails("check"))

    def test_missing_summary_fails(self) -> None:
        p = self.repo / "docs" / "dev" / "reference" / "glossary.md"
        p.write_text(p.read_text().replace("summary:", "sumary:", 1))
        self.assertIn("front-matter", self.fails("check"))

    def test_wrong_diataxis_folder_fails(self) -> None:
        p = self.repo / "docs" / "dev" / "reference" / "glossary.md"
        p.write_text(p.read_text().replace("type: reference", "type: how-to", 1))
        self.assertIn("diataxis", self.fails("check"))

    def test_hand_edited_generated_file_fails_until_synced(self) -> None:
        p = self.repo / "docs" / "INDEX.md"
        p.write_text(p.read_text() + "\nhand edit\n")
        self.assertIn("generated-drift", self.fails("check"))
        self.ok("sync_indexes")
        self.ok("check")

    def test_role_change_requires_resync(self) -> None:
        p = self.repo / "agents" / "roles" / "builder" / "ROLE.md"
        p.write_text(p.read_text().replace("Implement work items", "Build work items", 1))
        out = self.fails("check")
        self.assertTrue("generated-drift" in out or "adapter-drift" in out)
        self.ok("sync_indexes")
        self.ok("sync_agents")
        self.ok("check")

    def test_duplicate_item_file_ownership_fails(self) -> None:
        p = self.repo / "agents" / "roles" / "builder" / "ROLE.md"
        p.write_text(p.read_text().replace("item_files: []", "item_files: [brief.md]", 1))
        self.ok("sync_indexes")
        self.ok("sync_agents")
        self.assertIn("ownership", self.fails("check"))

    def test_unknown_owner_role_fails(self) -> None:
        p = self.repo / "work" / "inbox" / "README.md"
        p.write_text(p.read_text().replace("owner_role: orchestrator", "owner_role: ghost", 1))
        self.assertIn("ownership", self.fails("check"))

    def test_skill_name_must_match_folder(self) -> None:
        p = self.repo / "agents" / "roles" / "reviewer" / "skills" / "verify-work" / "SKILL.md"
        p.write_text(p.read_text().replace("name: verify-work", "name: Verify_Work", 1))
        self.assertIn("skill", self.fails("check"))

    def test_skill_names_must_be_unique_across_shared_and_role_lanes(self) -> None:
        # .claude/skills/ is flat: the same name in a role lane and in agents/skills/ would collide.
        src = self.repo / "agents" / "roles" / "reviewer" / "skills" / "verify-work"
        shutil.copytree(src, self.repo / "agents" / "skills" / "verify-work")
        out = self.fails("check")
        self.assertIn("skill", out)
        self.assertIn("already used", out)

    def test_skill_in_a_role_lane_needs_its_own_skill_md(self) -> None:
        (self.repo / "agents" / "roles" / "researcher" / "skills" / "empty-skill").mkdir(parents=True)
        self.assertIn("no SKILL.md", self.fails("check"))

    def test_role_must_equal_its_folder_name(self) -> None:
        p = self.repo / "agents" / "roles" / "builder" / "ROLE.md"
        p.write_text(p.read_text().replace("role: builder", "role: constructor", 1))
        self.assertIn("must equal the folder name", self.fails("check"))

    def test_old_flat_role_file_is_rejected_with_the_new_location(self) -> None:
        shutil.copy(self.repo / "agents" / "roles" / "builder" / "ROLE.md", self.repo / "agents" / "roles" / "legacy.md")
        out = self.fails("check")
        self.assertIn("agents/roles/legacy/ROLE.md", out)

    def test_role_folder_without_a_charter_is_an_error(self) -> None:
        (self.repo / "agents" / "roles" / "ghost").mkdir()
        self.assertIn("has no ROLE.md", self.fails("check"))

    def test_role_folders_without_skills_are_fine(self) -> None:
        # builder, orchestrator, planner, researcher, scribe and security keep an empty skills/ folder (.gitkeep).
        skills = self.repo / "agents" / "roles" / "researcher" / "skills"
        if not skills.is_dir():
            self.skipTest("researcher has no skills/ folder in this project")
        self.assertEqual([p.name for p in skills.iterdir() if p.is_dir()], [])
        self.assertTrue((skills / ".gitkeep").is_file())
        self.ok("check")

    def test_role_folder_without_a_skills_folder_is_an_error(self) -> None:
        src = self.repo / "agents" / "roles" / "builder" / "ROLE.md"
        dst = self.repo / "agents" / "roles" / "ghost" / "ROLE.md"
        dst.parent.mkdir()
        dst.write_text(src.read_text().replace("role: builder", "role: ghost", 1))
        self.assertIn("has no skills/", self.fails("check"))

    def test_default_owner_must_be_a_real_role(self) -> None:
        shutil.rmtree(self.repo / "agents" / "roles" / "scribe")
        out = self.fails("check")
        self.assertIn("DEFAULT_OWNER", out)
        self.assertIn("scribe", out)

    def test_core_linking_into_module_is_an_error(self) -> None:
        modules = _lib.load_modules(self.repo)
        target = None
        for m in modules.values():
            for path in m["paths"]:
                full = self.repo / path
                if path.startswith("docs/") and full.is_dir() and (full / "README.md").exists():
                    target = path + "/README.md"
        if not target:
            self.skipTest("no docs module installed")
        p = self.repo / "docs" / "dev" / "explanation" / "design-rationale.md"
        p.write_text(p.read_text() + f"\nSee [module](../../../{target}).\n")
        self.assertIn("module-coupling", self.fails("check"))

    def test_workspace_packages_and_boundary_checks(self) -> None:
        apps = self.repo / "apps"
        pkgs = self.repo / "packages"
        apps.mkdir(exist_ok=True)
        pkgs.mkdir(exist_ok=True)
        (apps / "README.md").write_text("---\nsummary: Apps.\nowner_role: builder\n---\n# apps\n")
        (pkgs / "README.md").write_text("---\nsummary: Packages.\nowner_role: builder\n---\n# packages\n")

        # Missing README inside a package subfolder fails
        (pkgs / "core").mkdir()
        self.assertIn("workspace-readme", self.fails("check"))

        # Valid package and app depending on package pass and appear in repo-map.md
        (pkgs / "core" / "README.md").write_text("---\nsummary: Core primitives.\n---\n# core\n")
        (apps / "web").mkdir()
        (apps / "web" / "README.md").write_text("---\nsummary: Web client.\ndepends_on: [core]\n---\n# web\n")
        self.ok("sync_indexes")
        self.ok("sync_agents")
        self.ok("check", "--strict")
        self.assertIn("`apps/web/`", (self.repo / "docs" / "dev" / "reference" / "repo-map.md").read_text())

        # Package depending on app fails with workspace-boundary
        (pkgs / "core" / "README.md").write_text("---\nsummary: Core primitives.\ndepends_on: [apps/web]\n---\n# core\n")
        self.ok("sync_indexes")
        self.assertIn("workspace-boundary", self.fails("check"))

        # Package dependency cycle fails with workspace-cycle
        (pkgs / "auth").mkdir()
        (pkgs / "core" / "README.md").write_text("---\nsummary: Core primitives.\ndepends_on: [auth]\n---\n# core\n")
        (pkgs / "auth" / "README.md").write_text("---\nsummary: Auth package.\ndepends_on: [core]\n---\n# auth\n")
        self.ok("sync_indexes")
        self.assertIn("workspace-cycle", self.fails("check"))


class WorkLifecycleTests(RepoTestCase):
    def test_full_lifecycle_and_guard_rails(self) -> None:
        item = self.new_item("login flow", "--title", "Login: the flow")
        self.assertRegex(item, r"^\d{4}-\d{2}-\d{2}-login-flow$")
        self.assertIn(item, (self.repo / "work" / "ACTIVE.md").read_text())
        self.ok("check")

        self.fails("transition", item, "done")  # draft -> done is illegal
        self.assertIn("--next", self.fails("transition", item, "planned"))
        self.ok("transition", item, "planned", "--next", "builder: start", "--by", "planner")
        self.ok("transition", item, "in-progress", "--next", "building", "--by", "builder")
        self.assertIn("allowed from in-progress", self.fails("transition", item, "done", "--next", "x"))
        self.assertIn("evidence", self.fails("transition", item, "in-review", "--next", "verify", "--by", "builder"))
        self.ok("transition", item, "in-review", "--next", "verify", "--evidence", "python3 tools/check.py", "--by", "builder")
        self.assertIn("review.md", self.fails("transition", item, "verified", "--next", "docs", "--by", "reviewer"))
        self.ok("item_file", item, "review")
        self.fails("item_file", item, "review")  # never overwrites
        self.ok("transition", item, "verified", "--next", "update docs", "--by", "reviewer")
        self.ok("transition", item, "done", "--by", "scribe")
        self.ok("check")
        self.ok("archive_item", item)
        self.assertFalse((self.repo / "work" / "items" / item).exists())
        self.assertTrue(list((self.repo / "work" / "archive").glob(f"*/{item}")))
        self.assertNotIn(item, (self.repo / "work" / "ACTIVE.md").read_text())
        self.ok("check")

    def test_self_review_is_refused_by_transition_and_check(self) -> None:
        item = self.new_item("self-review-guard")
        self.ok("transition", item, "planned", "--next", "build", "--by", "planner")
        self.ok("transition", item, "in-progress", "--next", "building", "--by", "builder")
        self.ok("transition", item, "in-review", "--next", "verify", "--evidence", "ran check", "--by", "builder")
        self.ok("item_file", item, "review")
        self.assertIn("independent review required",
                      self.fails("transition", item, "verified", "--next", "docs", "--by", "builder"))
        self.ok("transition", item, "verified", "--next", "docs", "--by", "reviewer")
        h = self.repo / "work" / "items" / item / "handoff.md"
        self.assertEqual(_lib.read_fm(h).get("verified_by"), "reviewer")
        self.ok("check", "--strict")
        # Hand-editing verified_by to match built_by is caught by check.py
        h.write_text(_lib.set_fm_value(h.read_text(), "verified_by", "builder"))
        self.assertIn("self-review", self.fails("check"))

    def test_status_change_requires_by(self) -> None:
        item = self.new_item("needs-actor")
        self.assertIn("--by", self.fails("transition", item, "planned", "--next", "build"))
        self.ok("transition", item, "planned", "--next", "build", "--by", "planner")
        self.assertIn("--by", self.fails("transition", item, "in-progress", "--next", "build"))

    def test_built_by_is_not_overwritten_when_reviewer_sends_back(self) -> None:
        item = self.new_item("provenance")
        self.ok("transition", item, "planned", "--next", "build", "--by", "planner")
        self.ok("transition", item, "in-progress", "--next", "build", "--by", "builder")
        self.ok("transition", item, "in-review", "--next", "verify", "--evidence", "ran check", "--by", "builder")
        self.ok("transition", item, "in-progress", "--next", "fix findings", "--owner", "builder", "--by", "reviewer")
        h = self.repo / "work" / "items" / item / "handoff.md"
        self.assertEqual(_lib.read_fm(h).get("built_by"), "builder")

    def test_verified_and_done_need_built_by(self) -> None:
        item = self.new_item("missing-builder")
        self.ok("transition", item, "planned", "--next", "build", "--by", "planner")
        self.ok("transition", item, "in-progress", "--next", "build", "--by", "builder")
        self.ok("transition", item, "in-review", "--next", "verify", "--evidence", "ran check", "--by", "builder")
        self.ok("item_file", item, "review")
        self.ok("transition", item, "verified", "--next", "docs", "--by", "reviewer")
        h = self.repo / "work" / "items" / item / "handoff.md"
        h.write_text(h.read_text().replace("built_by: builder\n", "", 1))
        self.assertIn("built_by", self.fails("check", "--strict"))

    def test_archive_refuses_unfinished_items(self) -> None:
        item = self.new_item("half-done")
        self.assertIn("only done or canceled items", self.fails("archive_item", item))

    def test_canceled_item_and_reviewer_reject_to_draft(self) -> None:
        item = self.new_item("bad-idea")
        self.ok("transition", item, "planned", "--next", "build", "--by", "planner")
        self.ok("transition", item, "in-progress", "--next", "building", "--by", "builder")
        self.ok("transition", item, "in-review", "--next", "verify", "--evidence", "ran check", "--by", "builder")
        # Reviewer rejects back to draft for re-planning
        self.ok("transition", item, "draft", "--next", "re-plan approach", "--by", "reviewer")
        # Orchestrator cancels and archives
        self.ok("transition", item, "canceled", "--next", "dropped after review rejection", "--by", "orchestrator")
        self.ok("check", "--strict")
        self.ok("archive_item", item)
        self.assertFalse((self.repo / "work" / "items" / item).exists())
        self.ok("check", "--strict")

    def test_verified_item_can_still_be_canceled(self) -> None:
        item = self.new_item("overtaken-by-events")
        self.ok("transition", item, "planned", "--next", "build", "--by", "planner")
        self.ok("transition", item, "in-progress", "--next", "building", "--by", "builder")
        self.ok("transition", item, "in-review", "--next", "verify", "--evidence", "ran check", "--by", "builder")
        self.ok("item_file", item, "review")
        self.ok("transition", item, "verified", "--next", "update docs", "--evidence", "criterion 1 checked", "--by", "reviewer")
        self.ok("transition", item, "canceled", "--next", "priorities changed before release", "--by", "orchestrator")
        self.assertEqual(_lib.read_fm(_lib.find_item(self.repo, item).handoff)["status"], "canceled")
        self.fails("transition", item, "in-progress", "--next", "reopen", "--by", "builder")  # canceled is final
        self.ok("check", "--strict")

    def test_security_review_item_file(self) -> None:
        if "security" not in _lib.load_modules(self.repo):
            self.skipTest("security module not installed")
        item = self.new_item("auth-change")
        path = self.ok("item_file", item, "security-review")
        self.assertTrue((self.repo / path).is_file())
        self.ok("check", "--strict")

    def test_blocked_needs_a_reason_and_can_resume(self) -> None:
        item = self.new_item("waits")
        self.ok("transition", item, "planned", "--next", "go", "--by", "planner")
        self.fails("transition", item, "blocked")
        self.ok("transition", item, "blocked", "--next", "waiting on Q-0001", "--by", "orchestrator")
        self.ok("transition", item, "in-progress", "--next", "resumed", "--by", "builder")

    def test_light_item_has_one_file_and_still_needs_evidence(self) -> None:
        item = self.new_item("quick-fix", "--light")
        self.assertTrue((self.repo / "work" / "items" / f"{item}.md").is_file())
        self.fails("item_file", item, "review")
        self.ok("transition", item, "planned", "--next", "go", "--by", "planner")
        self.ok("transition", item, "in-progress", "--next", "go", "--by", "builder")
        self.fails("transition", item, "in-review", "--next", "verify", "--by", "builder")
        self.ok("transition", item, "in-review", "--next", "verify", "--evidence", "ran it", "--by", "builder")
        self.ok("transition", item, "verified", "--next", "close", "--by", "reviewer")
        self.ok("transition", item, "done", "--by", "scribe")
        self.ok("check")

    def test_same_slug_twice_gets_unique_ids(self) -> None:
        a, b = self.new_item("same"), self.new_item("same")
        self.assertNotEqual(a, b)
        self.assertTrue(b.endswith("-2"))

    def test_unknown_role_is_rejected(self) -> None:
        self.assertIn("unknown role", self.fails("new_item", "x", "--owner", "wizard"))

    def test_hand_edit_with_bad_status_is_caught(self) -> None:
        item = self.new_item("sloppy")
        h = self.repo / "work" / "items" / item / "handoff.md"
        h.write_text(h.read_text().replace("status: draft", "status: finished", 1))
        self.assertIn("handoff", self.fails("check"))

    def test_done_without_review_is_caught(self) -> None:
        item = self.new_item("skipped-review")
        h = self.repo / "work" / "items" / item / "handoff.md"
        text = h.read_text().replace("status: draft", "status: done", 1).replace("evidence: []", "evidence: [x]", 1)
        h.write_text(text)
        self.assertIn("review.md", self.fails("check"))

    def test_sweep_marks_idle_items_stale_and_they_can_resume(self) -> None:
        item = self.new_item("forgotten")
        h = self.repo / "work" / "items" / item / "handoff.md"
        h.write_text(_lib.set_fm_value(h.read_text(), "updated", "2020-01-01"))
        self.assertIn("item-stale", self.fails("check", "--strict"))
        self.assertIn("stale", self.ok("archive_item", "--sweep"))
        fm = _lib.read_fm(h)
        self.assertEqual((fm["status"], fm["owner_role"]), ("stale", "orchestrator"))
        self.assertNotEqual(fm["updated"], "2020-01-01")  # marking stale resets the re-warn clock
        self.ok("check", "--strict")  # already marked stale: check --strict must not warn again
        self.ok("transition", item, "planned", "--next", "re-triaged", "--by", "orchestrator")

    def test_stale_items_rewarn_after_a_month(self) -> None:
        item = self.new_item("still-forgotten")
        h = self.repo / "work" / "items" / item / "handoff.md"
        h.write_text(_lib.set_fm_value(h.read_text(), "status", "stale"))
        old = (_lib.today() - timedelta(days=_lib.STALE_REWARN_DAYS + 1)).isoformat()
        h.write_text(_lib.set_fm_value(h.read_text(), "updated", old))
        self.assertIn("item-stale", self.fails("check", "--strict"))

    def test_same_status_transition_updates_in_place(self) -> None:
        item = self.new_item("research-handoff")
        self.ok("transition", item, "draft", "--owner", "researcher", "--next", "Investigate API limits")
        self.ok("transition", item, "draft", "--owner", "planner", "--next", "Update brief with API limits")
        fm = _lib.read_fm(_lib.find_item(self.repo, item).handoff)
        self.assertEqual((fm["status"], fm["owner_role"]), ("draft", "planner"))
        self.ok("check", "--strict")

    def test_sweep_archives_old_done_items(self) -> None:
        item = self.new_item("ancient", "--light")
        self.ok("transition", item, "planned", "--next", "g", "--by", "planner")
        self.ok("transition", item, "in-progress", "--next", "g", "--by", "builder")
        self.ok("transition", item, "in-review", "--next", "g", "--evidence", "e", "--by", "builder")
        self.ok("transition", item, "verified", "--next", "g", "--by", "reviewer")
        self.ok("transition", item, "done", "--by", "scribe")
        f = self.repo / "work" / "items" / f"{item}.md"
        f.write_text(_lib.set_fm_value(f.read_text(), "updated", "2020-01-01"))
        self.ok("archive_item", "--sweep")
        self.assertFalse(f.exists())


    def test_update_next_step_owner_and_evidence_without_moving_status(self) -> None:
        item = self.new_item("handoff-only")
        handoff = _lib.find_item(self.repo, item).handoff
        self.ok("transition", item, "--next", "Planner: write brief.md", "--owner", "planner")
        fm = _lib.read_fm(handoff)
        self.assertEqual((fm["status"], fm["owner_role"], fm["next_action"]), ("draft", "planner", "Planner: write brief.md"))
        self.ok("transition", item, "--evidence", "python3 tools/check.py")
        self.ok("transition", item, "--evidence", "second proof")
        self.assertEqual(_lib.read_fm(handoff)["evidence"], ["python3 tools/check.py", "second proof"])
        self.assertEqual(_lib.read_fm(handoff)["status"], "draft")
        self.assertIn(item, (self.repo / "work" / "ACTIVE.md").read_text())
        self.ok("check")

    def test_in_place_update_guard_rails(self) -> None:
        item = self.new_item("guarded")
        self.assertIn("nothing to change", self.fails("transition", item))
        self.assertIn("unknown role", self.fails("transition", item, "--next", "x", "--owner", "wizard"))
        quick = self.new_item("quick-one", "--light")
        self.ok("transition", quick, "planned", "--next", "go", "--by", "planner")
        self.ok("transition", quick, "in-progress", "--next", "going", "--by", "builder")
        self.ok("transition", quick, "in-review", "--next", "look", "--evidence", "ran it", "--by", "builder")
        self.ok("transition", quick, "verified", "--next", "close", "--evidence", "checked", "--by", "reviewer")
        self.ok("transition", quick, "done", "--by", "scribe")
        self.assertIn("final", self.fails("transition", quick, "--next", "too late"))

    def test_light_item_can_be_handed_straight_to_another_role(self) -> None:
        item = self.new_item("update-vision", "--light", "--status", "planned", "--owner", "planner")
        fm = _lib.read_fm(_lib.find_item(self.repo, item).handoff)
        self.assertEqual((fm["status"], fm["owner_role"]), ("planned", "planner"))
        self.ok("check")


class WorktreeTests(RepoTestCase):
    def setUp(self) -> None:
        super().setUp()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.email=t@t", "-c", "user.name=t",
                        "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "init"], check=True)

    def test_worktree_create_list_and_remove(self) -> None:
        item = self.new_item("wt-feature", "--worktree")
        wt_path = self.repo.parent / f"{self.repo.name}-{item}"
        self.assertTrue(wt_path.is_dir())
        self.assertTrue((wt_path / "work" / "items" / item / "handoff.md").is_file())
        self.assertFalse((self.repo / "work" / "items" / item).exists())
        self.assertIn(str(wt_path), self.ok("worktree", "list"))
        # Refuses to remove while still in draft without --force
        self.assertIn("only verified, done or canceled", self.fails("worktree", "remove", item))
        self.ok("worktree", "remove", item, "--force")
        self.assertFalse(wt_path.exists())
        self.assertEqual(subprocess.run(
            ["git", "-C", str(self.repo), "branch", "--list", f"item/{item}"],
            capture_output=True, text=True, check=True,
        ).stdout.strip(), "")

    def test_worktree_remove_finds_custom_path(self) -> None:
        item = self.new_item("custom-path")
        custom = self.repo.parent / f"custom-{item}"
        self.ok("worktree", "create", item, "--path", str(custom))
        self.assertTrue(custom.is_dir())
        self.ok("worktree", "remove", item, "--force")
        self.assertFalse(custom.exists())

    def test_worktree_remove_keeps_unmerged_branch(self) -> None:
        item = self.new_item("unmerged")
        wt_path = self.ok("worktree", "create", item)
        (Path(wt_path) / "scratch.txt").write_text("work\n", encoding="utf-8")
        sh = ["git", "-C", wt_path]
        subprocess.run(sh + ["-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], check=True)
        subprocess.run(sh + ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "work"], check=True)
        out = self.ok("worktree", "remove", item, "--force")
        self.assertIn("kept because it is not merged", out)
        self.assertTrue(subprocess.run(
            ["git", "-C", str(self.repo), "branch", "--list", f"item/{item}"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())

    def test_worktree_refuses_path_inside_repo_root(self) -> None:
        item = self.new_item("inside-root")
        self.assertIn("outside the repository root",
                      self.fails("worktree", "create", item, "--path", str(self.repo / "sub")))


class EvalHarnessTests(RepoTestCase):
    def test_eval_harness_lists_and_verifies_golden_tasks(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        listing = self.ok("eval_harness", "--list")
        for task_id in ("find-the-right-doc", "respect-ownership", "handoff-roundtrip", "escalation-discipline"):
            self.assertIn(task_id, listing)
        out = self.ok("eval_harness", "--verify-fixtures")
        self.assertEqual(out.count("PASS"), 4, out)
        self.assertNotIn("FAIL", out)

    def test_eval_harness_fails_closed_on_unknown_task(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        passed, reason = eval_harness.grade_task(self.repo, "bogus-task", {})
        self.assertFalse(passed)
        self.assertIn("unknown eval task", reason)

    def test_eval_harness_rejects_placeholder_adr_body(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        decisions = self.repo / "docs" / "decisions"
        existing = {p.name for p in decisions.glob("0*.md")}
        path = eval_harness.new_adr.create(self.repo, "Use SQLite", "proposed", None, "human")
        path.write_text(_lib.set_fm_value(path.read_text(), "summary", '"Use SQLite for the prototype."'))
        eval_harness.sync_indexes.write_outputs(self.repo)
        passed, reason = eval_harness.grade_task(
            self.repo, "find-the-right-doc", {"existing_adrs": existing, "docs_snap": {}},
        )
        self.assertFalse(passed)
        self.assertIn("context", reason)

    def test_eval_harness_rejects_unchanged_handoff_body(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "handoff-roundtrip")
            eval_harness.transition.transition(
                sandbox, meta["item_id"], "in-progress", "continue", "builder", [], by_role="builder",
            )
            passed, reason = eval_harness.grade_task(sandbox, "handoff-roundtrip", meta)
        self.assertFalse(passed)
        self.assertIn("body", reason)

    def test_eval_harness_rejects_wrong_escalation_target(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "escalation-discipline")
            eval_harness.run_reference_solution(sandbox, "escalation-discipline", meta)
            backup = next(i for i in eval_harness.iter_items(sandbox) if "backup" in i.id)
            eval_harness.transition.transition(
                sandbox, backup.id, "planned", "do it anyway", "builder", [], by_role="orchestrator",
            )
            passed, reason = eval_harness.grade_task(sandbox, "escalation-discipline", meta)
        self.assertFalse(passed)
        self.assertIn("not blocked", reason)


class QueueTests(RepoTestCase):
    ASK = ["ask", "Delete old backups?", "--asked-by", "orchestrator", "--recommended", "keep them",
           "--if-no-answer", "keep them", "--cost", "high: data loss"]

    def test_ask_answer_list_round_trip(self) -> None:
        self.assertEqual(self.ok("question", *self.ASK), "Q-0001")
        self.assertEqual(self.ok("question", *self.ASK[:1], "Second?", *self.ASK[2:]), "Q-0002")
        self.assertIn("Q-0001", self.ok("question", "list"))
        self.ok("check")
        self.ok("question", "answer", "Q-0001", "keep them")
        listing = self.ok("question", "list")
        self.assertNotIn("Q-0001", listing)
        self.assertIn("Q-0002", listing)
        text = (self.repo / "work" / "HUMAN.md").read_text()
        self.assertIn("- answer: keep them", text)
        self.assertLess(text.index("## Open"), text.index("### Q-0002"))
        self.assertLess(text.index("## Answered"), text.index("### Q-0001"))
        self.ok("check")

    def test_answering_everything_restores_empty_marker(self) -> None:
        self.ok("question", *self.ASK)
        self.ok("question", "answer", "Q-0001", "yes")
        self.assertIn("_None._", (self.repo / "work" / "HUMAN.md").read_text())
        self.assertEqual(self.ok("question", "list"), "no open questions")

    def test_asked_by_must_be_a_known_role(self) -> None:
        args = [a if a != "orchestrator" else "wizard" for a in self.ASK]
        self.assertIn("unknown role", self.fails("question", *args))

    def test_clone_is_isolated_from_project_data(self) -> None:
        self.assertEqual(self.ok("question", "list"), "no open questions")
        self.assertEqual([p.name for p in (self.repo / "work" / "items").iterdir()], ["README.md"])

    def test_ask_requires_recommendation_default_and_cost(self) -> None:
        self.fails("question", "ask", "Title", "--asked-by", "builder")

    def test_answering_unknown_question_fails(self) -> None:
        self.assertIn("not an open question", self.fails("question", "answer", "Q-0099", "x"))


class AdrTests(RepoTestCase):
    def test_numbers_increase_and_supersede_links_both_ways(self) -> None:
        first = self.ok("new_adr", "Use PostgreSQL")
        n1 = Path(first).name[:4]
        second = self.ok("new_adr", "Switch to SQLite", "--supersedes", n1, "--status", "accepted")
        n2 = Path(second).name[:4]
        third = self.ok("new_adr", "Switch to DuckDB", "--supersedes", f"ADR-{int(n2)}", "--status", "accepted")
        n3 = Path(third).name[:4]
        self.assertEqual(int(n2), int(n1) + 1)
        self.assertEqual(int(n3), int(n2) + 1)
        self.assertEqual(_lib.read_fm(self.repo / first)["status"], "superseded")
        self.assertEqual(str(_lib.read_fm(self.repo / first)["superseded_by"]).zfill(4), n2)
        self.assertEqual(_lib.read_fm(self.repo / second)["supersedes"], [n1])
        self.assertEqual(_lib.read_fm(self.repo / third)["supersedes"], [n2])
        self.ok("check", "--strict")

    def test_supersedes_rejects_garbage_instead_of_guessing(self) -> None:
        self.ok("new_adr", "Use PostgreSQL")
        before = sorted(p.name for p in (self.repo / "docs" / "decisions").glob("0*.md"))
        for bad in ("abc5xyz", "ADR-3-and-4", "12345", "3x"):
            self.assertIn("invalid ADR number", self.fails("new_adr", "Switch", "--supersedes", bad))
        self.assertEqual(before, sorted(p.name for p in (self.repo / "docs" / "decisions").glob("0*.md")))

    def test_parallel_agents_never_get_the_same_number(self) -> None:
        procs = [subprocess.Popen(
            [sys.executable, str(self.repo / "tools" / "new_adr.py"), f"Parallel decision {i}"],
            cwd=self.repo, env={**os.environ, "REPO_ROOT": str(self.repo)},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(8)]
        outs = [p.communicate(timeout=120) for p in procs]
        self.assertTrue(all(p.returncode == 0 for p in procs), outs)
        numbers = [Path(o[0].strip()).name[:4] for o in outs]
        self.assertEqual(len(set(numbers)), 8, numbers)
        self.ok("check")

    def test_duplicate_numbers_are_caught(self) -> None:
        d = self.repo / "docs" / "decisions"
        shutil.copy(d / "0001-split-the-repo-by-volatility.md", d / "0001-duplicate.md")
        self.assertIn("adr-number", self.fails("check"))


class DocTests(RepoTestCase):
    def test_new_doc_creates_valid_doc_and_updates_index(self) -> None:
        path = self.ok("new_doc", "how-to", "Deploy: to staging", "--summary", "How to deploy to staging.")
        self.assertEqual(path, "docs/dev/how-to/deploy-to-staging.md")
        self.assertIn("deploy-to-staging.md", (self.repo / "docs" / "INDEX.md").read_text())
        self.ok("check")
        self.fails("new_doc", "how-to", "Deploy: to staging")  # exists
        self.fails("new_doc", "poem", "Nope")

    # --- audience layout: docs/<dev|user>/<type>/, decisions shared, optional `audience:` key ---
    def _doc(self, rel: str, doc_type: str, title: str, extra: str = "") -> Path:
        p = self.repo / "docs" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"---\ntitle: {title}\ntype: {doc_type}\nstatus: active\nsummary: {title} summary.\n{extra}---\n# {title}\n",
                     encoding="utf-8")
        return p

    def _index_section(self, heading: str) -> str:
        """Text of one `## ` section of docs/INDEX.md (up to the next `## `)."""
        text = (self.repo / "docs" / "INDEX.md").read_text(encoding="utf-8")
        parts = text.split("\n## ")
        for part in parts[1:]:
            if part.startswith(heading):
                return part
        self.fail(f"no '## {heading}' section in docs/INDEX.md")

    def test_shipped_layout_has_dev_user_and_shared_decisions(self) -> None:
        docs = self.repo / "docs"
        for folder in ("tutorials", "how-to", "reference", "explanation"):
            self.assertTrue((docs / "dev" / folder).is_dir(), folder)
            self.assertFalse((docs / folder).exists(), f"docs/{folder}/ must not exist at the top level")
        self.assertTrue((docs / "user" / "README.md").exists())
        self.assertTrue((docs / "decisions").is_dir())
        self.assertIn("No documents yet", self._index_section("End users"))

    def test_new_doc_for_users_goes_to_docs_user_and_the_user_section(self) -> None:
        path = self.ok("new_doc", "how-to", "Reset your password", "--audience", "user", "--summary", "How to reset a password.")
        self.assertEqual(path, "docs/user/how-to/reset-your-password.md")
        self.assertIn("reset-your-password.md", self._index_section("End users"))
        self.assertNotIn("reset-your-password.md", self._index_section("Contributors"))
        self.ok("check")

    def test_new_doc_audience_rules(self) -> None:
        self.assertIn("unknown audience", self.fails("new_doc", "how-to", "X", "--audience", "alien"))
        modules = _lib.load_modules(self.repo)
        if "operations" in modules:
            self.assertIn("--audience applies", self.fails("new_doc", "runbook", "Restart", "--audience", "user"))
            self.assertEqual(self.ok("new_doc", "runbook", "Restart the queue"), "docs/operations/runbooks/restart-the-queue.md")

    def test_type_folder_directly_under_docs_is_a_layout_error(self) -> None:
        self._doc("how-to/old-spot.md", "how-to", "Old spot")
        out = self.fails("check")
        self.assertIn("docs-layout", out)
        self.assertIn("docs/dev/how-to/", out)

    def test_type_must_match_folder_under_an_audience(self) -> None:
        self._doc("user/reference/wrong.md", "how-to", "Wrong type")
        self.assertIn("diataxis", self.fails("check"))

    def test_audience_key_regroups_the_index_without_moving_the_file(self) -> None:
        self._doc("dev/how-to/for-users.md", "how-to", "For users", "audience: user\n")
        self.ok("sync_indexes")
        self.assertIn("dev/how-to/for-users.md", self._index_section("End users"))
        self.assertNotIn("for-users.md", self._index_section("Contributors"))
        self.ok("check")

    def test_unknown_audience_value_is_an_error(self) -> None:
        self._doc("dev/how-to/bad-audience.md", "how-to", "Bad audience", "audience: wizards\n")
        self.assertIn("doc-audience", self.fails("check"))

    def test_a_big_folder_gets_its_own_index_and_loses_it_when_small_again(self) -> None:
        import sync_indexes
        for i in range(sync_indexes.SPLIT_THRESHOLD + 1):
            self._doc(f"dev/how-to/bulk-{i:03d}.md", "how-to", f"Bulk {i:03d}")
        self.ok("sync_indexes")
        sub = self.repo / "docs" / "dev" / "how-to" / "INDEX.md"
        self.assertTrue(sub.exists(), "a folder over the threshold needs its own index")
        self.assertIn("see the section index", self._index_section("Contributors"))
        self.assertIn("bulk-000.md", sub.read_text(encoding="utf-8"))
        self.ok("check")
        for p in (self.repo / "docs" / "dev" / "how-to").glob("bulk-*.md"):
            p.unlink()
        self.ok("sync_indexes")
        self.assertFalse(sub.exists(), "the orphan section index must be removed")
        self.ok("check")


class ModuleTests(RepoTestCase):
    def test_every_installed_module_can_be_cut_cleanly(self) -> None:
        modules = _lib.load_modules(self.repo)
        if not modules:
            self.skipTest("no modules installed (lean profile)")
        for name, mod in modules.items():
            with self.subTest(module=name):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = clone(Path(tmp))
                    preview = run(repo, "remove_module", name)
                    self.assertEqual(preview.returncode, 0, preview.stderr)
                    self.assertIn("dry run", preview.stdout)
                    self.assertTrue(all((repo / p).exists() for p in mod["paths"]), "dry run must not delete")
                    res = run(repo, "remove_module", name, "--apply")
                    self.assertEqual(res.returncode, 0, f"cutting {name} left problems:\n{res.stdout}\n{res.stderr}")
                    self.assertFalse(any((repo / p).exists() for p in mod["paths"]))
                    self.assertNotIn(name, _lib.load_modules(repo))
                    again = run(repo, "check", "--strict")
                    self.assertEqual(again.returncode, 0, again.stdout)

    def test_cutting_every_module_in_turn_leaves_a_healthy_lean_repo(self) -> None:
        modules = list(_lib.load_modules(self.repo))
        for name in modules:
            res = self.sh("remove_module", name, "--apply")
            self.assertEqual(res.returncode, 0, f"{name}:\n{res.stdout}\n{res.stderr}")
        self.assertEqual(_lib.load_modules(self.repo), {})
        self.ok("check", "--strict")

    def test_cut_records_choice_in_copier_answers(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        answers = self.repo / ".copier-answers.yml"
        answers.write_text("_commit: v0\n_src_path: x\nlayout: single\nprofile: full\nproject_name: P\n")
        self.ok("remove_module", "evals", "--apply")
        text = answers.read_text()
        self.assertIn("profile: custom", text)
        self.assertNotIn("profile: full", text)
        self.assertIn("custom_modules:", text)
        self.assertNotIn("- evals", text)
        self.assertIn("- github", text)

    def test_unknown_module_is_rejected(self) -> None:
        self.assertIn("unknown module", self.fails("remove_module", "nope"))


class AdapterTests(RepoTestCase):
    def setUp(self) -> None:
        super().setUp()
        # Every test starts from "Cursor, Copilot and Gemini off", whatever this project has enabled.
        self.enable(cursor=False, copilot=False, gemini=False)
        shutil.rmtree(self.repo / ".cursor", ignore_errors=True)
        shutil.rmtree(self.repo / ".gemini", ignore_errors=True)
        (self.repo / ".github" / "copilot-instructions.md").unlink(missing_ok=True)
        self.ok("sync_agents")
        self.ok("sync_indexes")

    def test_adapters_are_generated_and_removed_with_their_source(self) -> None:
        targets = _lib.load_targets(self.repo)
        if not targets.get("claude", {}).get("enabled"):
            self.skipTest("claude adapter disabled")
        agent = self.repo / ".claude" / "agents" / "builder.md"
        self.assertTrue(agent.is_file())
        self.assertTrue((self.repo / "CLAUDE.md").read_text().strip() == "@AGENTS.md")
        self.assertIn("name: builder", agent.read_text())
        # A skill that lives under its role still lands flat in .claude/skills/.
        self.assertTrue((self.repo / ".claude" / "skills" / "verify-work" / "SKILL.md").is_file())
        shutil.rmtree(self.repo / "agents" / "roles" / "reviewer" / "skills" / "verify-work")
        (self.repo / "agents" / "roles" / "reviewer" / "skills" / ".gitkeep").write_text("")
        self.ok("sync_agents")
        self.assertFalse((self.repo / ".claude" / "skills" / "verify-work").exists())
        self.ok("sync_indexes")
        self.ok("check")

    def test_sync_refuses_to_overwrite_a_hand_written_file(self) -> None:
        targets = _lib.load_targets(self.repo)
        if not targets.get("claude", {}).get("enabled"):
            self.skipTest("claude adapter disabled")
        (self.repo / "agents" / "roles" / "reviewer" / "skills" / "verify-work" / "extra.md").write_text("x\n")
        (self.repo / ".claude" / "skills" / "verify-work" / "extra.md").write_text("mine\n")
        r = self.sh("sync_agents")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.repo / ".claude" / "skills" / "verify-work" / "extra.md").read_text(), "mine\n")

    def test_disabling_the_adapter_removes_generated_files(self) -> None:
        t = self.repo / "agents" / "adapters" / "targets.json"
        data = json.loads(t.read_text())
        if not data.get("claude", {}).get("enabled"):
            self.skipTest("claude adapter already disabled")
        data["claude"]["enabled"] = False
        t.write_text(json.dumps(data))
        self.ok("sync_agents")
        self.assertFalse((self.repo / ".claude").exists())
        self.assertFalse((self.repo / "CLAUDE.md").exists())
        self.ok("check")

    def enable(self, **targets: bool) -> None:
        t = self.repo / "agents" / "adapters" / "targets.json"
        data = json.loads(t.read_text())
        for name, on in targets.items():
            data.setdefault(name, {})["enabled"] = on
        t.write_text(json.dumps(data))

    def test_cursor_adapter_writes_role_rules_and_a_short_pointer(self) -> None:
        self.enable(cursor=True)
        self.ok("sync_agents")
        rules = self.repo / ".cursor" / "rules"
        pointer = (rules / "00-repo.mdc").read_text()
        self.assertIn("alwaysApply: true", pointer)
        self.assertIn("`AGENTS.md`", pointer)
        self.assertLess(len(pointer), 600, "the pointer must not copy AGENTS.md (the tool loads that file itself)")
        role = (rules / "role-builder.mdc").read_text()
        self.assertTrue(role.startswith("---\ndescription:"))
        self.assertIn("alwaysApply: false", role)
        self.assertIn("You are the **builder** role", role)
        self.ok("check", "--strict")
        self.ok("sync_agents", "--check")
        charter = self.repo / "agents" / "roles" / "builder" / "ROLE.md"
        charter.write_text(charter.read_text().rstrip() + "\n\nExtra rule.\n")
        self.assertIn("role-builder.mdc", self.fails("sync_agents", "--check"))
        self.ok("sync_agents")
        self.assertIn("Extra rule.", (rules / "role-builder.mdc").read_text())

    def test_claude_and_cursor_share_one_role_text(self) -> None:
        if not _lib.load_targets(self.repo).get("claude", {}).get("enabled"):
            self.skipTest("claude adapter disabled")
        self.enable(cursor=True)
        self.ok("sync_agents")
        claude = (self.repo / ".claude" / "agents" / "builder.md").read_text().split("---\n", 2)[2]
        cursor = (self.repo / ".cursor" / "rules" / "role-builder.mdc").read_text().split("---\n", 2)[2]
        self.assertEqual(claude, cursor)

    def test_copilot_adapter_writes_a_pointer_that_check_accepts(self) -> None:
        self.enable(copilot=True)
        self.ok("sync_agents")
        text = (self.repo / ".github" / "copilot-instructions.md").read_text()
        self.assertIn("`AGENTS.md`", text)
        self.assertNotIn("python3 tools/", text)
        self.ok("check", "--strict")
        self.ok("sync_agents", "--check")

    def test_gemini_adapter_writes_settings_that_check_accepts(self) -> None:
        self.enable(gemini=True)
        self.ok("sync_agents")
        cfg = json.loads((self.repo / ".gemini" / "settings.json").read_text())
        self.assertEqual(cfg["context"]["fileName"], ["AGENTS.md", "GEMINI.md"])
        self.ok("check", "--strict")
        self.ok("sync_agents", "--check")
        self.enable(gemini=False)
        self.ok("sync_agents")
        self.assertFalse((self.repo / ".gemini").exists())
        self.ok("check", "--strict")

    def test_copilot_adapter_does_not_turn_the_github_module_on(self) -> None:
        if "github" in _lib.load_modules(self.repo):
            self.ok("remove_module", "github", "--apply")
        self.enable(copilot=True)
        self.ok("sync_agents")
        self.assertTrue((self.repo / ".github" / "copilot-instructions.md").is_file())
        self.assertNotIn("github", _lib.load_modules(self.repo))
        self.ok("sync_indexes", "--check")
        self.assertNotIn("`.github/`", (self.repo / "docs" / "dev" / "reference" / "repo-map.md").read_text())
        self.ok("check", "--strict")

    def test_cutting_the_github_module_keeps_the_copilot_pointer(self) -> None:
        if "github" not in _lib.load_modules(self.repo):
            self.skipTest("github module not installed")
        self.enable(copilot=True)
        self.ok("sync_agents")
        self.ok("sync_indexes")
        self.ok("remove_module", "github", "--apply")
        self.assertTrue((self.repo / ".github" / "copilot-instructions.md").is_file())
        self.assertFalse((self.repo / ".github" / "workflows").exists())
        self.assertNotIn("github", _lib.load_modules(self.repo))
        self.ok("sync_agents", "--check")
        self.ok("sync_indexes", "--check")
        self.ok("check", "--strict")

    def test_disabling_cursor_and_copilot_removes_what_they_generated(self) -> None:
        self.enable(cursor=True, copilot=True)
        self.ok("sync_agents")
        self.enable(cursor=False, copilot=False)
        self.ok("sync_agents")
        self.assertFalse((self.repo / ".cursor").exists())
        self.assertFalse((self.repo / ".github" / "copilot-instructions.md").exists())
        self.ok("check", "--strict")

    def test_sync_never_overwrites_a_hand_written_copilot_file(self) -> None:
        mine = self.repo / ".github" / "copilot-instructions.md"
        mine.parent.mkdir(exist_ok=True)
        mine.write_text("my own instructions\n")
        self.enable(copilot=True)
        self.assertIn("SKIPPED", self.fails("sync_agents"))
        self.assertEqual(mine.read_text(), "my own instructions\n")

    def test_files_under_dot_cursor_are_not_checked_as_documentation(self) -> None:
        mine = self.repo / ".cursor" / "rules" / "mine.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("# Mine\n\n[broken](does/not/exist.md)\n")
        self.ok("check", "--strict")


if __name__ == "__main__":
    unittest.main()
