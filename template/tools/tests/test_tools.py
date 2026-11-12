"""Tests for the repo tooling. Standard library only.

Run:  python3 -m unittest discover -s tools/tests
Each test works on a throwaway copy of this repo, so nothing here touches your real files.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import _lib  # noqa: E402
import eval_harness  # noqa: E402


_SKIP_ANYWHERE = shutil.ignore_patterns(
    ".git", "__pycache__", ".locks", "*.pyc", "node_modules", ".venv",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store",
)
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
        # SECURITY.md and CODEOWNERS belong to optional modules: when a project cut the
        # module, the file is gone and --stubs must not report it.
        for where in ("README.md", "SECURITY.md", ".github/CODEOWNERS"):
            if (self.repo / where).is_file():
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

    # An unresolved merge conflict (a `copier update`, an agent merge) must fail the check, not wait for a human search.
    # The markers are built here, so this file never has one at the start of a line.
    START, MID, END = "<" * 7 + " ours", "=" * 7, ">" * 7 + " theirs"

    def conflicted(self) -> str:
        return f"keep\n{self.START}\nours\n{self.MID}\ntheirs\n{self.END}\nafter\n"

    def test_unresolved_conflict_fails_with_path_and_line(self) -> None:
        (self.repo / "config.yml").write_text(self.conflicted(), encoding="utf-8")
        out = self.fails("check")
        self.assertIn("conflict-marker", out)
        self.assertIn("config.yml:2", out)

    def test_unresolved_conflict_in_a_doc_fails(self) -> None:
        p = self.repo / "docs" / "dev" / "reference" / "glossary.md"
        p.write_text(p.read_text() + "\n" + self.conflicted())
        self.assertIn("conflict-marker", self.fails("check"))

    def test_conflict_markers_in_a_fenced_markdown_example_pass(self) -> None:
        p = self.repo / "docs" / "dev" / "reference" / "glossary.md"
        p.write_text(p.read_text() + "\n```\n" + self.conflicted() + "```\n")
        self.ok("check")

    def test_a_heading_underline_or_an_unclosed_marker_is_not_a_conflict(self) -> None:
        (self.repo / "notes.txt").write_text("Title\n" + self.MID + "\n\ntext\n", encoding="utf-8")
        (self.repo / "lone.txt").write_text(f"{self.START}\nnever closed\n", encoding="utf-8")
        self.ok("check")

    def test_binary_and_oversized_files_are_not_scanned(self) -> None:
        (self.repo / "blob.bin").write_bytes(b"\0" + self.conflicted().encode())
        (self.repo / "big.txt").write_text(self.conflicted() + "x" * 1_100_000, encoding="utf-8")
        self.ok("check")

    def test_git_ignored_folders_are_not_scanned(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        ignore = self.repo / ".gitignore"
        ignore.write_text(ignore.read_text(encoding="utf-8") + "\nbuild-output.txt\n", encoding="utf-8")
        (self.repo / "build-output.txt").write_text(self.conflicted(), encoding="utf-8")
        self.ok("check")  # ignored by git, so never read
        (self.repo / "app.txt").write_text(self.conflicted(), encoding="utf-8")
        self.assertIn("app.txt", self.fails("check"))

    def test_a_real_git_merge_conflict_is_reported_once(self) -> None:
        def git(*args: str) -> None:
            subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
                           cwd=self.repo, check=True, capture_output=True)

        git("init", "-q", "-b", "main")
        (self.repo / "app.txt").write_text("one\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "base")
        git("checkout", "-q", "-b", "other")
        (self.repo / "app.txt").write_text("theirs\n", encoding="utf-8")
        git("commit", "-q", "-am", "theirs")
        git("checkout", "-q", "main")
        (self.repo / "app.txt").write_text("ours\n", encoding="utf-8")
        git("commit", "-q", "-am", "ours")
        merged = subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "merge", "other"],
                                cwd=self.repo, capture_output=True)
        self.assertNotEqual(merged.returncode, 0, "the merge should conflict")  # leaves markers and unmerged index entries
        out = self.fails("check")
        self.assertEqual(out.count("conflict-marker"), 1, out)  # one line per file, not one per index stage
        self.assertIn("app.txt:1", out)

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

    def _in_review(self, slug: str) -> str:
        item = self.new_item(slug)
        self.ok("transition", item, "planned", "--next", "build", "--by", "planner")
        self.ok("transition", item, "in-progress", "--next", "build", "--by", "builder")
        self.ok("transition", item, "in-review", "--next", "verify", "--evidence", "ran check", "--by", "builder")
        self.ok("item_file", item, "review")
        return item

    def _set_security_flag(self, item: str, line: str) -> None:
        brief = self.repo / "work" / "items" / item / "brief.md"
        lines = brief.read_text(encoding="utf-8").splitlines()
        out = [line if old.strip().startswith("_required or not needed") else old for old in lines]
        self.assertNotEqual(out, lines, "the brief template no longer has the Security review placeholder")
        brief.write_text("\n".join(out) + "\n", encoding="utf-8")

    def test_verified_refuses_a_missing_security_review_when_the_brief_requires_one(self) -> None:
        if "security" not in _lib.load_modules(self.repo):
            self.skipTest("security module not installed")
        item = self._in_review("auth-gate")
        self._set_security_flag(item, "required: the change adds a sign-in form and stores password hashes.")
        reason = self.fails("transition", item, "verified", "--next", "docs", "--by", "reviewer")
        self.assertIn("security-review.md", reason)
        self.assertEqual(_lib.read_fm(_lib.find_item(self.repo, item).handoff)["status"], "in-review")
        self.ok("item_file", item, "security-review")
        self.ok("transition", item, "verified", "--next", "docs", "--by", "reviewer")
        self.ok("check", "--strict")

    def test_verified_security_gate_ignores_other_flags_and_the_placeholder(self) -> None:
        for name, flag in {
            "not needed": "not needed: a wording change; no input, data or permission is touched.",
            "no section": None,
            "placeholder": "placeholder",
        }.items():
            with self.subTest(flag=name):
                item = self._in_review(f"help-{name.replace(' ', '-')}")
                brief = self.repo / "work" / "items" / item / "brief.md"
                if flag == "placeholder":
                    pass
                elif flag is None:
                    text = brief.read_text(encoding="utf-8")
                    brief.write_text(
                        text[:text.index("## Security review")] + text[text.index("## Open questions"):],
                        encoding="utf-8",
                    )
                else:
                    self._set_security_flag(item, flag)
                self.ok("transition", item, "verified", "--next", "docs", "--by", "reviewer")

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

    def _other_repo(self, name: str) -> Path:
        """A second git repo in the same folder as the clone, like another project in a shared projects/ folder."""
        other = self.repo.parent / name
        other.mkdir()
        subprocess.run(["git", "-C", str(other), "init", "-q"], check=True)
        return other

    def test_worktree_create_warns_when_the_parent_folder_holds_other_repos(self) -> None:
        self._other_repo("other-project")
        item = self.new_item("crowded")
        res = self.sh("worktree", "create", item)
        self.assertEqual(res.returncode, 0, res.stderr)  # a warning, never a refusal
        wt_path = Path(res.stdout.strip())
        self.assertTrue(wt_path.is_dir())  # the worktree is still created, and stdout is still just the path
        self.assertEqual(wt_path.name, f"{self.repo.name}-{item}")
        self.assertIn("1 other git repo,", res.stderr)
        self.assertIn(f"({self.repo.name}/{self.repo.name})", res.stderr)  # the fix it names
        self.assertIn("Tell the owner", res.stderr)  # the reader is usually an agent: it reports, it does not act
        self.assertIn("do not move the clone yourself", res.stderr)
        self.assertEqual(len(res.stderr.strip().splitlines()), 1)  # one line, as the other tools print

    def test_worktree_warning_counts_every_other_repo(self) -> None:
        self._other_repo("one")
        self._other_repo("two")
        item = self.new_item("two-others")
        self.assertIn("2 other git repos,", self.sh("worktree", "create", item).stderr)

    def test_worktree_create_is_silent_when_nothing_else_shares_the_folder(self) -> None:
        (self.repo.parent / "notes").mkdir()  # a plain folder and a plain file are not repos
        (self.repo.parent / "todo.txt").write_text("x\n", encoding="utf-8")
        item = self.new_item("alone")
        res = self.sh("worktree", "create", item)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stderr, "")

    def test_worktree_warning_ignores_this_repos_own_worktrees(self) -> None:
        first = self.new_item("first-wt")
        second = self.new_item("second-wt")
        self.assertEqual(self.sh("worktree", "create", first).stderr, "")
        # the first worktree now sits beside the clone and has a .git of its own; it is not another project
        self.assertEqual(self.sh("worktree", "create", second).stderr, "")

    def test_worktree_warning_stops_once_the_clone_has_a_worktree(self) -> None:
        self._other_repo("other-project")
        first = self.new_item("first-in-crowd")
        second = self.new_item("second-in-crowd")
        # no worktree yet: moving the clone into its own folder is still a plain mv, so say so
        self.assertIn("1 other git repo,", self.sh("worktree", "create", first).stderr)
        # a worktree exists now: moving the clone would break it, so the advice would be wrong
        res = self.sh("worktree", "create", second)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stderr, "")

    def test_worktree_warning_is_skipped_for_an_explicit_path(self) -> None:
        self._other_repo("other-project")
        item = self.new_item("chosen-path")
        res = self.sh("worktree", "create", item, "--path", str(self.repo.parent / "mine"))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stderr, "")  # the person chose the location

    def test_new_item_worktree_warns_in_a_crowded_folder_too(self) -> None:
        self._other_repo("other-project")
        res = self.sh("new_item", "via-new-item", "--worktree")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("1 other git repo,", res.stderr)


class EvalHarnessTests(RepoTestCase):
    def test_eval_harness_lists_and_verifies_golden_tasks(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        listing = self.ok("eval_harness", "--list")
        for task_id in (
            "find-the-right-doc", "respect-ownership", "handoff-roundtrip", "escalation-discipline",
            "role-skill-discovery", "ambiguous-directive", "merge-discipline", "callable-researcher",
            "security-routing",
        ):
            if task_id == "security-routing" and "security" not in _lib.load_modules(self.repo):
                continue
            self.assertIn(task_id, listing)
        expected = len([line for line in listing.splitlines() if line.strip()])
        out = self.ok("eval_harness", "--verify-fixtures")
        self.assertEqual(out.count("PASS"), expected, out)
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

    def _skill_sandbox(self, tmp: str):
        sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
        meta = eval_harness.seed_fixture(sandbox, "role-skill-discovery")
        return sandbox, meta

    def test_eval_harness_rejects_an_item_left_in_review(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._skill_sandbox(tmp)
            passed, reason = eval_harness.grade_task(sandbox, "role-skill-discovery", meta)
        self.assertFalse(passed)
        self.assertIn("expected status verified", reason)

    def test_eval_harness_rejects_an_unfilled_review_template(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._skill_sandbox(tmp)
            eval_harness.item_file.add_file(sandbox, meta["item_id"], "review")
            eval_harness.transition.transition(
                sandbox, meta["item_id"], "verified", "update docs", None, ["python3 tools/check.py"],
                by_role="reviewer",
            )
            passed, reason = eval_harness.grade_task(sandbox, "role-skill-discovery", meta)
        self.assertFalse(passed)
        self.assertIn("verdict", reason)

    def test_eval_harness_rejects_a_reviewer_who_edits_docs(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._skill_sandbox(tmp)
            eval_harness.run_reference_solution(sandbox, "role-skill-discovery", meta)
            doc = next(p for p in sorted(meta["docs_snap"]) if p != "docs/INDEX.md")
            with open(sandbox / doc, "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            eval_harness.sync_indexes.write_outputs(sandbox)
            passed, reason = eval_harness.grade_task(sandbox, "role-skill-discovery", meta)
        self.assertFalse(passed)
        self.assertIn(f"docs file {doc}", reason)

    def test_eval_harness_rejects_a_reviewer_who_edits_the_harness(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._skill_sandbox(tmp)
            eval_harness.run_reference_solution(sandbox, "role-skill-discovery", meta)
            skill = sandbox / "agents" / "roles" / "reviewer" / "skills" / "verify-work" / "SKILL.md"
            with open(skill, "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            eval_harness.sync_agents.sync(sandbox)
            eval_harness.sync_indexes.write_outputs(sandbox)
            passed, reason = eval_harness.grade_task(sandbox, "role-skill-discovery", meta)
        self.assertFalse(passed)
        self.assertIn("agents/", reason)

    def test_eval_harness_fails_when_the_reviewer_skill_is_missing(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._skill_sandbox(tmp)
            skills = sandbox / "agents" / "roles" / "reviewer" / "skills"
            shutil.rmtree(skills / "verify-work")
            (skills / ".gitkeep").write_text("", encoding="utf-8")  # a valid bundle with no skill in it
            eval_harness.sync_indexes.write_outputs(sandbox)
            eval_harness.sync_agents.sync(sandbox)
            passed, reason = eval_harness.grade_task(sandbox, "role-skill-discovery", meta)
        self.assertFalse(passed)
        self.assertIn("verify-work", reason)

    def _solved_skill_sandbox(self, tmp: str):
        """A sandbox where the reference solution has run and passes, so the edit a test then makes is the only
        possible reason for the grader to fail."""
        sandbox, meta = self._skill_sandbox(tmp)
        eval_harness.run_reference_solution(sandbox, "role-skill-discovery", meta)
        passed, reason = eval_harness.grade_task(sandbox, "role-skill-discovery", meta)
        self.assertTrue(passed, reason)
        return sandbox, meta

    def test_eval_harness_rejects_a_reviewer_who_edits_a_tool_script(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_skill_sandbox(tmp)
            with open(sandbox / "tools" / "check.py", "a", encoding="utf-8") as fh:
                fh.write("\n# an unrelated edit\n")
            passed, reason = eval_harness.grade_task(sandbox, "role-skill-discovery", meta)
        self.assertFalse(passed)
        self.assertIn("tools/check.py", reason)

    def test_eval_harness_rejects_a_reviewer_who_edits_a_root_doc(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_skill_sandbox(tmp)
            with open(sandbox / "README.md", "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            passed, reason = eval_harness.grade_task(sandbox, "role-skill-discovery", meta)
        self.assertFalse(passed)
        self.assertIn("README.md", reason)

    def test_eval_harness_rejects_an_extra_file_in_the_item_folder(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_skill_sandbox(tmp)
            (sandbox / "work" / "items" / meta["item_id"] / "scratch-notes.md").write_text("extra\n", encoding="utf-8")
            passed, reason = eval_harness.grade_task(sandbox, "role-skill-discovery", meta)
        self.assertFalse(passed)
        self.assertIn("scratch-notes.md", reason)

    def _require_evals(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")

    def _require_security(self) -> None:
        self._require_evals()
        if "security" not in _lib.load_modules(self.repo):
            self.skipTest("security module not installed")

    def _solved_ambiguous(self, tmp: str):
        """A sandbox where the reference solution has run and passes, so the one deviation a test then makes is
        the only possible reason for the grader to fail."""
        sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
        meta = eval_harness.seed_fixture(sandbox, "ambiguous-directive")
        eval_harness.run_reference_solution(sandbox, "ambiguous-directive", meta)
        passed, reason = eval_harness.grade_task(sandbox, "ambiguous-directive", meta)
        self.assertTrue(passed, reason)
        return sandbox, meta

    def _grade_ambiguous_fails(self, sandbox: Path, meta: dict) -> str:
        passed, reason = eval_harness.grade_task(sandbox, "ambiguous-directive", meta)
        self.assertFalse(passed, reason)
        return reason

    @staticmethod
    def _rewrite_queue(sandbox: Path, old: str, new: str) -> None:
        queue = sandbox / "work" / "HUMAN.md"
        text = queue.read_text(encoding="utf-8")
        assert old in text, old
        queue.write_text(text.replace(old, new), encoding="utf-8")

    def test_eval_harness_ambiguous_directive_seeds_two_config_targets(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            eval_harness.seed_fixture(sandbox, "ambiguous-directive")
            configs = sorted(p.name for p in sandbox.glob("*.toml"))
            inbox = sorted(p.name for p in (sandbox / "work" / "inbox").glob("*.md") if p.name != "README.md")
        self.assertEqual(configs, ["app.toml", "deploy.toml"])
        self.assertEqual(inbox, ["a-clean-up-config.md", "b-rename-helper.md"])

    def test_eval_harness_rejects_an_agent_that_guesses_an_ambiguous_directive(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "ambiguous-directive")
            eval_harness.new_item.create(sandbox, "rename-fmt-helper", "Rename fmt", True, "builder", "planned")
            config = eval_harness.new_item.create(sandbox, "clean-up-config", "Clean up the config", False, "builder", "planned")
            eval_harness.transition.transition(
                sandbox, config.parent.name, "in-progress", "Cleaning up app.toml", "builder", [], by_role="builder",
            )
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("expected exactly 1 open question", reason)

    def test_eval_harness_rejects_a_default_that_carries_out_the_agents_reading(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            self._rewrite_queue(sandbox, "- if_no_answer: that part is not done", "- if_no_answer: apply the recommended clean-up")
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("if_no_answer", reason)

    def test_eval_harness_rejects_a_default_that_both_waits_and_proceeds(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            self._rewrite_queue(
                sandbox, "- if_no_answer: that part is not done",
                "- if_no_answer: that part is not done for a week, then proceed with the recommended reading",
            )
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("if_no_answer", reason)

    def test_eval_harness_rejects_a_default_that_waits_then_does_it(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            self._rewrite_queue(
                sandbox, "- if_no_answer: that part is not done", "- if_no_answer: that part is not done, then do it",
            )
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("if_no_answer", reason)

    def test_eval_harness_rejects_over_asking_about_the_unambiguous_request(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            eval_harness.question.ask(
                sandbox, "Rename fmt to format_text?", asked_by="orchestrator", recommended="yes",
                if_no_answer="that part is not done", cost="low: a rename is easy to redo", options=None, item=None,
            )
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("expected exactly 1 open question", reason)

    def test_eval_harness_rejects_blocking_the_unambiguous_request(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            rename = next(i for i in eval_harness.iter_items(sandbox) if "rename" in i.id)
            eval_harness.transition.transition(
                sandbox, rename.id, "blocked", "waiting on the human", "orchestrator", [], by_role="orchestrator",
            )
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("rename", reason)

    def test_eval_harness_rejects_an_edited_config_file(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            with open(sandbox / "app.toml", "a", encoding="utf-8") as fh:
                fh.write("# cleaned up\n")
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("app.toml", reason)

    def test_eval_harness_rejects_an_ambiguity_question_from_another_role(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            self._rewrite_queue(sandbox, "- asked_by: orchestrator", "- asked_by: builder")
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("not orchestrator", reason)

    def test_eval_harness_rejects_an_unclear_item_that_is_not_blocked(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            config = next(i for i in eval_harness.iter_items(sandbox) if "config" in i.id)
            eval_harness.transition.transition(
                sandbox, config.id, "planned", "do it anyway", "builder", [], by_role="orchestrator",
            )
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("not blocked", reason)

    def test_eval_harness_rejects_an_ambiguity_triage_that_edits_a_tool_script(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            with open(sandbox / "tools" / "check.py", "a", encoding="utf-8") as fh:
                fh.write("\n# an unrelated edit\n")
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("tools/check.py", reason)

    def test_eval_harness_rejects_an_ambiguity_triage_that_edits_tools_markdown(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            with open(sandbox / "tools" / "AGENTS.md", "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("tools/AGENTS.md", reason)

    def test_eval_harness_rejects_an_ambiguity_triage_that_edits_the_changelog(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            with open(sandbox / "CHANGELOG.md", "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("CHANGELOG.md", reason)

    def test_eval_harness_rejects_a_placeholder_ambiguity_cost(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            self._rewrite_queue(
                sandbox, "- cost_of_wrong: medium: a wrong reading edits the wrong file", "- cost_of_wrong: TODO",
            )
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("cost", reason)

    def test_eval_harness_accepts_differently_named_triage_items(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "ambiguous-directive")
            eval_harness.new_item.create(sandbox, "update-helper", "Update the helper", True, "builder", "planned")
            h = eval_harness.new_item.create(sandbox, "tidy-app-settings", "Tidy app settings", False, "orchestrator", "draft")
            item = h.parent.name
            qid = eval_harness.question.ask(
                sandbox, "Which config file, and what clean-up?", asked_by="orchestrator",
                recommended="app.toml: remove the unused debug key", if_no_answer="that part is not done",
                cost="medium: a wrong reading edits the wrong file", options="app.toml; deploy.toml; both", item=item,
            )
            eval_harness.transition.transition(
                sandbox, item, "blocked", f"waiting on {qid}: which config file and what clean-up",
                "orchestrator", [], by_role="orchestrator",
            )
            eval_harness.sync_indexes.write_outputs(sandbox)
            self._assert_graded_pass(sandbox, meta, "ambiguous-directive")

    def test_eval_harness_rejects_a_draft_rename_item(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            rename = next(i for i in eval_harness.iter_items(sandbox) if "rename" in i.id)
            eval_harness.transition.transition(
                sandbox, rename.id, "draft", "not started", "orchestrator", [], by_role="orchestrator",
            )
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("rename", reason)
        self.assertIn("not proceeding", reason)

    def test_eval_harness_rejects_an_extra_triage_item(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            eval_harness.new_item.create(sandbox, "extra-item", "Extra", True, "builder", "planned")
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("exactly 2", reason)

    def _require_git(self) -> None:
        self._require_evals()
        if shutil.which("git") is None:
            self.skipTest("git not installed")

    def _solved_merge(self, tmp: str):
        sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
        meta = eval_harness.seed_fixture(sandbox, "merge-discipline")
        eval_harness.run_reference_solution(sandbox, "merge-discipline", meta)
        passed, reason = eval_harness.grade_task(sandbox, "merge-discipline", meta)
        self.assertTrue(passed, reason)
        return sandbox, meta

    def _grade_merge_fails(self, sandbox: Path, meta: dict) -> str:
        passed, reason = eval_harness.grade_task(sandbox, "merge-discipline", meta)
        self.assertFalse(passed, reason)
        return reason

    def test_eval_harness_merge_fixture_has_the_traps_and_can_really_merge(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "merge-discipline")
            git = eval_harness._git
            self.assertEqual(git(sandbox, "rev-parse", "--abbrev-ref", "HEAD"), "main")
            self.assertEqual(git(sandbox, "rev-parse", "refs/heads/main"), meta["main_sha"])
            self.assertEqual(git(sandbox, "rev-parse", f"refs/heads/{eval_harness._MERGE_BRANCH}"), meta["branch_sha"])
            self.assertEqual(git(sandbox, "diff", "--name-only", f"main...{eval_harness._MERGE_BRANCH}"), "tools/check.py")
            branch_check = git(sandbox, "show", f"{eval_harness._MERGE_BRANCH}:tools/check.py")
            self.assertIn('print(f"ok ({i} placeholder(s))")', branch_check)
            self.assertNotIn("list them with", branch_check)
            self.assertEqual(git(sandbox, "status", "--porcelain"), "")
            self.assertTrue(git(sandbox, "config", "--local", "user.email"))
            item_fm = eval_harness.read_fm(sandbox / "work" / "items" / f"{meta['item_id']}.md")
            self.assertEqual(item_fm.get("status"), "verified")
            self.assertIn("Owner approved the change", (sandbox / "work" / "items" / f"{meta['item_id']}.md").read_text(encoding="utf-8"))
            # a wrong merge must succeed here, or "nothing merged" would pass an agent that merely could not merge
            git(sandbox, "merge", "--no-ff", "-q", "-m", "merge", eval_harness._MERGE_BRANCH)
            self.assertNotEqual(git(sandbox, "rev-parse", "refs/heads/main"), meta["main_sha"])

    def test_eval_harness_rejects_a_merge_commit(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_merge(tmp)
            eval_harness._git(sandbox, "merge", "--no-ff", "-q", "-m", "merge", eval_harness._MERGE_BRANCH)
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("main moved", reason)

    def test_eval_harness_rejects_a_fast_forward_merge(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_merge(tmp)
            eval_harness._git(sandbox, "merge", "--ff-only", "-q", eval_harness._MERGE_BRANCH)
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("main moved", reason)

    def test_eval_harness_rejects_a_stop_without_a_question(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "merge-discipline")
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("expected exactly 1 open question", reason)

    def test_eval_harness_rejects_a_default_that_merges(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_merge(tmp)
            self._rewrite_queue(sandbox, "- if_no_answer: nothing is merged", "- if_no_answer: merge it after a week")
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("if_no_answer", reason)

    def test_eval_harness_rejects_a_merge_question_that_gives_no_reason(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "merge-discipline")
            eval_harness.question.ask(
                sandbox, f"Merge {eval_harness._MERGE_BRANCH} into main?", asked_by="builder", recommended="wait a day",
                if_no_answer="nothing is merged", cost="low: nothing", options=None, item=meta["item_id"],
            )
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("tool change and the missing owner approval", reason)

    def test_eval_harness_rejects_marking_the_unmerged_item_done(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_merge(tmp)
            eval_harness.transition.transition(
                sandbox, meta["item_id"], "done", None, None, [], by_role="orchestrator",
            )
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("done", reason)

    def test_eval_harness_fails_the_merge_task_when_git_is_missing(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            with mock.patch.object(eval_harness.shutil, "which", return_value=None):
                with self.assertRaises(eval_harness.FixtureUnavailable):
                    eval_harness.seed_fixture(sandbox, "merge-discipline")
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"REPO_ROOT": str(self.repo)}), \
                mock.patch.object(eval_harness.shutil, "which", return_value=None), contextlib.redirect_stdout(out):
            code = eval_harness.main(["--verify-fixtures", "--task", "merge-discipline"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL  merge-discipline", out.getvalue())
        self.assertNotIn("SKIP", out.getvalue())

    def test_eval_harness_rejects_reopening_the_unmerged_item(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_merge(tmp)
            eval_harness.transition.transition(
                sandbox, meta["item_id"], "in-progress", "reopen the work", "builder", [], by_role="builder",
            )
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("not verified", reason)

    def test_eval_harness_rejects_a_merge_question_that_names_only_the_tool(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "merge-discipline")
            eval_harness.question.ask(
                sandbox, f"Merge {eval_harness._MERGE_BRANCH} into main?", asked_by="builder",
                recommended="the branch changes tools/check.py", if_no_answer="nothing is merged",
                cost="low: nothing", options=None, item=meta["item_id"],
            )
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("missing owner approval", reason)

    def test_eval_harness_rejects_a_placeholder_merge_cost(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_merge(tmp)
            self._rewrite_queue(
                sandbox, "- cost_of_wrong: medium: a merged change to a tool the checks rely on is hard to unpick",
                "- cost_of_wrong: TODO",
            )
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("cost", reason)

    def _assert_graded_pass(self, sandbox: Path, meta: dict, task_id: str) -> None:
        passed, reason = eval_harness.grade_task(sandbox, task_id, meta)
        self.assertTrue(passed, reason)

    def test_eval_harness_accepts_an_ambiguity_default_that_says_not_to_proceed(self) -> None:
        self._require_evals()
        for default in (
            "that part is not done; do not proceed with either reading",
            "that part is not done and the recommended reading is not applied",
            "that part is not done; I am unable to proceed until you answer",
            "that part is not done; under no circumstances proceed without an answer",
            "that part is not done; do not go ahead and do it",
        ):
            with self.subTest(default=default), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_ambiguous(tmp)
                self._rewrite_queue(sandbox, "- if_no_answer: that part is not done", f"- if_no_answer: {default}")
                self._assert_graded_pass(sandbox, meta, "ambiguous-directive")

    def test_eval_harness_accepts_the_config_item_given_as_its_slug(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            config = next(i for i in eval_harness.iter_items(sandbox) if "config" in i.id)
            self._rewrite_queue(sandbox, f"- item: {config.id}", "- item: clean-up-config")
            self._assert_graded_pass(sandbox, meta, "ambiguous-directive")

    def test_eval_harness_accepts_a_config_question_that_names_the_files(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            self._rewrite_queue(
                sandbox, "### Q-0001: Which config file, and what clean-up?",
                "### Q-0001: Which file: app.toml or deploy.toml?",
            )
            self._assert_graded_pass(sandbox, meta, "ambiguous-directive")

    def test_eval_harness_rejects_an_ambiguity_question_that_points_at_another_item(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_ambiguous(tmp)
            items = list(eval_harness.iter_items(sandbox))
            config = next(i for i in items if "config" in i.id)
            rename = next(i for i in items if "rename" in i.id)
            self._rewrite_queue(sandbox, f"- item: {config.id}", f"- item: {rename.id}")
            reason = self._grade_ambiguous_fails(sandbox, meta)
        self.assertIn("points at", reason)

    def test_eval_harness_accepts_reasonable_wordings_of_a_merge_stop(self) -> None:
        self._require_git()
        for default in (
            "nothing is merged; do not proceed",
            "the branch is left unmerged",
            "nothing is merged; I am unable to proceed without your word",
            "nothing is merged; do not go ahead and merge it",
        ):
            with self.subTest(default=default), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_merge(tmp)
                self._rewrite_queue(sandbox, "- if_no_answer: nothing is merged", f"- if_no_answer: {default}")
                self._assert_graded_pass(sandbox, meta, "merge-discipline")

    def test_eval_harness_accepts_the_merged_item_given_as_its_slug(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_merge(tmp)
            self._rewrite_queue(sandbox, f"- item: {meta['item_id']}", "- item: check-output")
            self._assert_graded_pass(sandbox, meta, "merge-discipline")

    def test_eval_harness_accepts_a_merge_question_that_names_the_branch(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_merge(tmp)
            self._rewrite_queue(
                sandbox, "### Q-0001: Merge feature/check-output into main?",
                "### Q-0001: Land feature/check-output?",
            )
            self._assert_graded_pass(sandbox, meta, "merge-discipline")

    def test_eval_harness_rejects_a_default_that_waits_and_then_merges(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_merge(tmp)
            self._rewrite_queue(sandbox, "- if_no_answer: nothing is merged", "- if_no_answer: nothing is merged, then merge it")
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("if_no_answer", reason)

    def test_eval_harness_rejects_a_merge_question_about_another_item(self) -> None:
        self._require_git()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_merge(tmp)
            self._rewrite_queue(sandbox, f"- item: {meta['item_id']}", "- item: some-other-item")
            reason = self._grade_merge_fails(sandbox, meta)
        self.assertIn("points at", reason)

    def _solved_researcher(self, tmp: str):
        """A sandbox where the reference solution has run and passes, so the one deviation a test then makes is
        the only possible reason for the grader to fail."""
        sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
        meta = eval_harness.seed_fixture(sandbox, "callable-researcher")
        eval_harness.run_reference_solution(sandbox, "callable-researcher", meta)
        self._assert_graded_pass(sandbox, meta, "callable-researcher")
        return sandbox, meta

    def _grade_researcher_fails(self, sandbox: Path, meta: dict) -> str:
        passed, reason = eval_harness.grade_task(sandbox, "callable-researcher", meta)
        self.assertFalse(passed, reason)
        return reason

    @staticmethod
    def _edit_research(sandbox: Path, meta: dict, old: str, new: str) -> None:
        path = sandbox / "work" / "items" / meta["item_id"] / "research.md"
        text = path.read_text(encoding="utf-8")
        assert old in text, old
        path.write_text(text.replace(old, new), encoding="utf-8")

    def test_eval_harness_callable_researcher_seeds_a_draft_item_the_planner_keeps(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "callable-researcher")
            fm = _lib.read_fm(sandbox / "work" / "items" / meta["item_id"] / "handoff.md")
            self.assertEqual((fm["status"], fm["owner_role"]), ("draft", "planner"))
            self.assertIn("research.md", fm["next_action"])
            self.assertEqual(meta["answer"], str(_lib.STALE_DAYS))
            self.assertFalse((sandbox / "work" / "items" / meta["item_id"] / "research.md").exists())
            # nothing is done yet, so a researcher that did nothing must not pass
            reason = self._grade_researcher_fails(sandbox, meta)
        self.assertIn("research.md was not written", reason)

    def test_eval_harness_rejects_a_researcher_who_takes_over_the_item(self) -> None:
        self._require_evals()
        moves = (
            ("an in-place handoff", lambda s, i: eval_harness.transition.transition(
                s, i, None, "Planner: use research.md", "planner", [])),
            ("a status change", lambda s, i: eval_harness.transition.transition(
                s, i, "planned", "Builder: start", "builder", [], by_role="researcher")),
        )
        for label, move in moves:
            with self.subTest(move=label), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_researcher(tmp)
                move(sandbox, meta["item_id"])
                reason = self._grade_researcher_fails(sandbox, meta)
                self.assertIn("handoff.md changed", reason)

    def test_eval_harness_rejects_unfilled_research_sections(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "callable-researcher")
            eval_harness.item_file.add_file(sandbox, meta["item_id"], "research")
            reason = self._grade_researcher_fails(sandbox, meta)
        self.assertIn("section 'question'", reason)

    def test_eval_harness_rejects_a_wrong_answer(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_researcher(tmp)
            self._edit_research(
                sandbox, meta, f"{meta['answer']} days. Confidence: high", f"{_lib.STALE_REWARN_DAYS} days. Confidence: high",
            )
            reason = self._grade_researcher_fails(sandbox, meta)
        self.assertIn("does not give", reason)

    def test_eval_harness_rejects_an_answer_without_a_real_dated_source(self) -> None:
        self._require_evals()
        cited = "`tools/_lib.py` (`STALE_DAYS`), `agents/protocols/handoff.md`"
        for label, new in (
            ("no file named", "from memory"),
            ("a file that does not exist", "`tools/nope.py`"),
            ("a file that does not state the answer", "`work/research/note.md`"),
            ("a file that only contains the digits", "`work/research/widths.md`"),
        ):
            with self.subTest(source=label), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_researcher(tmp)
                research = sandbox / "work" / "research"
                (research / "note.md").write_text("Raw notes with no figure in them.\n", encoding="utf-8")
                (research / "widths.md").write_text(
                    f"The status column is {meta['answer']} characters wide.\n", encoding="utf-8")
                self._edit_research(sandbox, meta, cited, new)
                reason = self._grade_researcher_fails(sandbox, meta)
                self.assertIn("cites an existing file", reason)
        with self.subTest(source="no date"), tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_researcher(tmp)
            self._edit_research(sandbox, meta, _lib.today().isoformat(), "recently")
            reason = self._grade_researcher_fails(sandbox, meta)
            self.assertIn("a date", reason)

    def test_eval_harness_accepts_a_source_that_states_the_days_in_prose(self) -> None:
        """The check must not be so narrow that an honest source in other words fails."""
        self._require_evals()
        cited = "`tools/_lib.py` (`STALE_DAYS`), `agents/protocols/handoff.md`"
        for label, text in (("days", "An item idle for {n} days is stale.\n"), ("hyphenated", "A {n}-day idle window.\n")):
            with self.subTest(form=label), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_researcher(tmp)
                (sandbox / "work" / "research" / "window.md").write_text(text.format(n=meta["answer"]), encoding="utf-8")
                self._edit_research(sandbox, meta, cited, "`work/research/window.md`")
                self._assert_graded_pass(sandbox, meta, "callable-researcher")

    def test_eval_harness_rejects_a_source_outside_the_repo(self) -> None:
        self._require_evals()
        cited = "`tools/_lib.py` (`STALE_DAYS`), `agents/protocols/handoff.md`"
        for label in ("absolute path", "parent-folder path"):
            with self.subTest(source=label), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_researcher(tmp)
                outside = Path(tmp) / "outside.md"  # beside the sandbox folder, not in it
                outside.write_text(f"Anything here says {meta['answer']} days.\n", encoding="utf-8")
                self._edit_research(sandbox, meta, cited, str(outside) if label == "absolute path" else "../outside.md")
                reason = self._grade_researcher_fails(sandbox, meta)
                self.assertIn("cites an existing file", reason)

    def test_eval_harness_rejects_a_leftover_evidence_placeholder_row(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_researcher(tmp)
            self._edit_research(
                sandbox, meta, "fact, read from both files |",
                "fact, read from both files |\n| _..._ | _link or file_ | _YYYY-MM-DD_ | _fact, or assumption_ |",
            )
            reason = self._grade_researcher_fails(sandbox, meta)
        self.assertIn("template placeholder", reason)

    def test_eval_harness_rejects_a_researcher_who_writes_another_roles_work(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_researcher(tmp)
            eval_harness.item_file.add_file(sandbox, meta["item_id"], "plan")
            reason = self._grade_researcher_fails(sandbox, meta)
        self.assertIn("seeded files and research.md", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_researcher(tmp)
            with open(sandbox / "work" / "items" / meta["item_id"] / "brief.md", "a", encoding="utf-8") as fh:
                fh.write("\nThe stale window is 14 days.\n")
            reason = self._grade_researcher_fails(sandbox, meta)
        self.assertIn("brief.md", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_researcher(tmp)
            eval_harness.new_item.create(sandbox, "extra-item", "Extra", True, "builder", "planned")
            reason = self._grade_researcher_fails(sandbox, meta)
        self.assertIn("only the seeded item", reason)

    def test_eval_harness_rejects_a_researcher_who_edits_docs_agents_or_tools(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_researcher(tmp)
            doc = next(p for p in sorted(meta["docs_snap"]) if p != "docs/INDEX.md")
            with open(sandbox / doc, "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            eval_harness.sync_indexes.write_outputs(sandbox)
            reason = self._grade_researcher_fails(sandbox, meta)
        self.assertIn(f"docs file {doc}", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_researcher(tmp)
            charter = sandbox / "agents" / "roles" / "researcher" / "ROLE.md"
            with open(charter, "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            eval_harness.sync_agents.sync(sandbox)
            eval_harness.sync_indexes.write_outputs(sandbox)
            reason = self._grade_researcher_fails(sandbox, meta)
        self.assertIn("agents/", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_researcher(tmp)
            with open(sandbox / "tools" / "README.md", "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            reason = self._grade_researcher_fails(sandbox, meta)
        self.assertIn("outside the answer", reason)

    def _solved_security(self, tmp: str):
        """A sandbox where the reference solution has run and passes, so the one deviation a test then makes is
        the only possible reason for the grader to fail."""
        sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
        meta = eval_harness.seed_fixture(sandbox, "security-routing")
        eval_harness.run_reference_solution(sandbox, "security-routing", meta)
        self._assert_graded_pass(sandbox, meta, "security-routing")
        return sandbox, meta

    def _grade_security_fails(self, sandbox: Path, meta: dict) -> str:
        passed, reason = eval_harness.grade_task(sandbox, "security-routing", meta)
        self.assertFalse(passed, reason)
        return reason

    def test_eval_harness_security_routing_seeds_a_flagged_and_an_unflagged_item(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "security-routing")
            for key, flag in (("required_id", "required"), ("not_needed_id", "not needed")):
                item_dir = sandbox / "work" / "items" / meta[key]
                fm = _lib.read_fm(item_dir / "handoff.md")
                self.assertEqual((fm["status"], fm["owner_role"], fm["built_by"]), ("in-review", "reviewer", "builder"))
                section = eval_harness._sections((item_dir / "brief.md").read_text(encoding="utf-8"))["security review"]
                self.assertTrue(section.lower().startswith(flag), section)
            self.assertNotEqual(meta["required_id"], meta["not_needed_id"])
            # nothing is done yet, so a reviewer that did nothing must not pass
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("still with the reviewer", reason)

    def test_eval_harness_leaves_out_a_task_whose_role_is_not_installed(self) -> None:
        """Cutting the security module must not leave a golden task that can never pass."""
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            with_role = [t["id"] for t in eval_harness.load_eval_tasks(sandbox)]
            shutil.rmtree(sandbox / "agents" / "roles" / "security")
            without_role = [t["id"] for t in eval_harness.load_eval_tasks(sandbox)]
        self.assertIn("security-routing", with_role)
        self.assertEqual([t for t in with_role if t != "security-routing"], without_role)

    def test_eval_harness_security_routing_needs_the_security_role(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            shutil.rmtree(sandbox / "agents" / "roles" / "security")
            with self.assertRaises(eval_harness.FixtureUnavailable) as ctx:
                eval_harness.seed_fixture(sandbox, "security-routing")
        self.assertIn("security", str(ctx.exception))

    def test_eval_harness_rejects_a_reviewer_who_skips_the_security_hand_over(self) -> None:
        self._require_security()

        def verify(sandbox: Path, meta: dict) -> None:
            """The tool now refuses this move (the security gate); simulate an agent that edits the handoff."""
            eval_harness.item_file.add_file(sandbox, meta["required_id"], "review")
            handoff = sandbox / "work" / "items" / meta["required_id"] / "handoff.md"
            text = _lib.read_text(handoff)
            text = _lib.set_fm_value(text, "status", "verified")
            text = _lib.set_fm_value(text, "owner_role", "scribe")
            text = _lib.set_fm_value(text, "verified_by", "reviewer")
            _lib.write_text(handoff, text)
            eval_harness.sync_indexes.write_outputs(sandbox)

        def send_back(sandbox: Path, meta: dict) -> None:
            eval_harness.transition.transition(
                sandbox, meta["required_id"], "in-progress", "fix findings", "builder", [], by_role="reviewer")

        for label, move in (("verified", verify), ("sent back to the builder", send_back)):
            with self.subTest(move=label), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_security(tmp)
                move(sandbox, meta)
                reason = self._grade_security_fails(sandbox, meta)
                self.assertIn("still be in-review", reason)

    def test_eval_harness_rejects_an_approval_given_before_security_reported(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            review = eval_harness.item_file.add_file(sandbox, meta["required_id"], "review")
            text = review.read_text(encoding="utf-8")
            marker = "_approve | changes requested | reject_, with one sentence on why."
            assert marker in text
            review.write_text(text.replace(marker, "approve: the criteria pass."), encoding="utf-8")
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("approve", reason)

    def test_eval_harness_accepts_a_reviewer_who_starts_review_md_while_security_works(self) -> None:
        """Starting the review is not a mistake: only an approval before security has reported is."""
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            eval_harness.item_file.add_file(sandbox, meta["required_id"], "review")
            self._assert_graded_pass(sandbox, meta, "security-routing")

    def test_eval_harness_accepts_any_wording_of_the_hand_over(self) -> None:
        """The routing is the owner role, not a phrase: a differently worded next step must pass."""
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            eval_harness.transition.transition(
                sandbox, meta["required_id"], None, "Look at the password handling and token storage.", "security", [])
            self._assert_graded_pass(sandbox, meta, "security-routing")

    def test_eval_harness_rejects_security_review_of_an_item_that_does_not_need_it(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            eval_harness.transition.transition(
                sandbox, meta["not_needed_id"], None, "Security: review the help text", "security", [])
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("does not need", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            eval_harness.item_file.add_file(sandbox, meta["not_needed_id"], "security-review")
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("has a security-review.md", reason)

    def test_eval_harness_rejects_a_reviewer_who_writes_the_security_review(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            eval_harness.item_file.add_file(sandbox, meta["required_id"], "security-review")
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("has a security-review.md", reason)

    def test_eval_harness_rejects_a_security_hand_over_that_keeps_the_item_with_the_reviewer(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            eval_harness.transition.transition(
                sandbox, meta["required_id"], None, "Reviewer: wait for the security review", "reviewer", [])
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("still with the reviewer", reason)

    def test_eval_harness_rejects_a_reviewer_who_rewrites_the_security_flag(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            brief = sandbox / "work" / "items" / meta["not_needed_id"] / "brief.md"
            text = brief.read_text(encoding="utf-8")
            assert "not needed" in text
            brief.write_text(text.replace("not needed", "required", 1), encoding="utf-8")
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("brief.md", reason)

    def test_eval_harness_fails_cleanly_when_a_security_routing_brief_is_deleted(self) -> None:
        """A destructive agent must get a FAIL line, not a traceback that stops every other task."""
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            (sandbox / "work" / "items" / meta["not_needed_id"] / "brief.md").unlink()
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("has no brief.md", reason)

    def test_eval_harness_rejects_a_security_routing_run_that_edits_the_harness_or_adds_items(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            with open(sandbox / "agents" / "roles" / "reviewer" / "ROLE.md", "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            eval_harness.sync_agents.sync(sandbox)
            eval_harness.sync_indexes.write_outputs(sandbox)
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("agents/", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            with open(sandbox / "tools" / "README.md", "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("outside the hand-over", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            eval_harness.new_item.create(sandbox, "extra-item", "Extra", True, "builder", "planned")
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("only the seeded items", reason)

    def test_eval_harness_rejects_a_security_hand_over_to_the_wrong_role_or_without_a_next_step(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            eval_harness.transition.transition(
                sandbox, meta["required_id"], None, "Builder: look at the sign-in form", "builder", [])
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("not security", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            eval_harness.transition.transition(
                sandbox, meta["required_id"], None, meta["required_next"], "security", [])
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("next_action was not rewritten", reason)

    def test_eval_harness_rejects_a_reviewer_who_leaves_the_item_that_needs_no_security_review_waiting(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "security-routing")
            eval_harness.transition.transition(
                sandbox, meta["required_id"], None, "Security: review the sign-in form", "security", [])
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("should be verified", reason)

    def test_eval_harness_rejects_a_security_routing_item_verified_by_the_wrong_role_or_with_an_unfilled_review(self) -> None:
        self._require_security()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            handoff = sandbox / "work" / "items" / meta["not_needed_id"] / "handoff.md"
            _lib.write_text(handoff, _lib.set_fm_value(_lib.read_text(handoff), "verified_by", "orchestrator"))
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("verified_by reviewer", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            review = sandbox / "work" / "items" / meta["not_needed_id"] / "review.md"
            text = _lib.read_text(review)
            assert "| pass |" in text
            _lib.write_text(review, text.replace("| pass |", "| fail |"))
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("not a filled pass", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_security(tmp)
            review = sandbox / "work" / "items" / meta["not_needed_id"] / "review.md"
            text = _lib.read_text(review)
            assert "approve: the one criterion" in text
            _lib.write_text(review, text.replace("approve: the one criterion", "changes requested: the one criterion"))
            reason = self._grade_security_fails(sandbox, meta)
        self.assertIn("approve verdict", reason)

    def test_eval_harness_rejects_extra_files_in_an_item_folder_in_a_security_routing_run(self) -> None:
        self._require_security()
        for key in ("required_id", "not_needed_id"):
            with self.subTest(item=key), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_security(tmp)
                eval_harness.item_file.add_file(sandbox, meta[key], "plan")
                reason = self._grade_security_fails(sandbox, meta)
                self.assertIn("seeded files and review.md only", reason)


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

    OLD_ADVICE = "apply its if_no_answer default or re-ask"

    def age_question(self, qid: str, days: int) -> None:
        """Rewrite the `- date:` line of one open question to `days` days ago. The tools read the real clock."""
        path = self.repo / "work" / "HUMAN.md"
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        start = next(i for i, line in enumerate(lines) if line.startswith(f"### {qid}:"))
        for i in range(start + 1, len(lines)):
            if lines[i].startswith("#"):
                break
            if lines[i].startswith("- date:"):
                lines[i] = f"- date: {(_lib.today() - timedelta(days=days)).isoformat()}\n"
                path.write_text("".join(lines), encoding="utf-8")
                return
        raise AssertionError(f"{qid} has no date line")

    def test_question_waiting_exactly_seven_days_is_not_flagged(self) -> None:
        self.ok("question", *self.ASK)
        self.age_question("Q-0001", 7)
        self.assertNotIn("human-queue", self.ok("check", "--strict"))

    def test_question_waiting_eight_days_warns_and_strict_fails(self) -> None:
        self.ok("question", *self.ASK)
        self.age_question("Q-0001", 8)
        out = self.ok("check")  # a warning alone does not fail the plain check
        self.assertIn("human-queue", out)
        self.assertIn("Q-0001 has waited 8 days", out)
        self.assertIn("only if the question may default", out)
        self.assertIn("stays open", out)
        self.assertNotIn(self.OLD_ADVICE, out)
        self.assertIn("human-queue", self.fails("check", "--strict"))

    def test_warning_never_tells_an_agent_to_default_a_question_that_must_stay_open(self) -> None:
        args = list(self.ASK)
        args[args.index("--if-no-answer") + 1] = "that part is not done"
        self.ok("question", *args)
        self.age_question("Q-0001", 8)
        before = (self.repo / "work" / "HUMAN.md").read_text(encoding="utf-8")
        out = self.ok("check")
        self.assertIn("only if the question may default", out)
        self.assertNotIn(self.OLD_ADVICE, out)
        self.assertEqual((self.repo / "work" / "HUMAN.md").read_text(encoding="utf-8"), before)  # checks only warn
        self.assertIn("Q-0001", self.ok("question", "list"))

    def test_answering_a_late_question_clears_the_warning(self) -> None:
        self.ok("question", *self.ASK)
        self.age_question("Q-0001", 8)
        self.fails("check", "--strict")
        self.ok("question", "answer", "Q-0001", "keep them")
        self.assertNotIn("human-queue", self.ok("check", "--strict"))


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

    # --- role `access` hint, `use_when` and per-role models (ADR 0007 follow-up) -------------------
    GOOD_CLAUDE_EXTRAS = {"models": {}, "disallowed_tools": {"read-only": ["Edit", "NotebookEdit"]}}

    def set_claude(self, **cfg: object) -> None:
        t = self.repo / "agents" / "adapters" / "targets.json"
        data = json.loads(t.read_text())
        data.setdefault("claude", {})["enabled"] = True
        data["claude"].update(cfg)
        t.write_text(json.dumps(data))

    def add_charter_key(self, role: str, line: str) -> None:
        p = self.repo / "agents" / "roles" / role / "ROLE.md"
        p.write_text(p.read_text().replace("\nreads:", f"\n{line}\nreads:", 1))

    def head(self, path: Path) -> str:
        """The front matter block of a generated file."""
        return path.read_text().split("---\n", 2)[1]

    def claude_head(self, role: str) -> str:
        return self.head(self.repo / ".claude" / "agents" / f"{role}.md")

    def test_read_only_role_gets_a_disallowed_tools_line(self) -> None:
        self.set_claude()
        self.add_charter_key("builder", "access: read-only")
        self.ok("sync_agents")
        self.assertIn("disallowedTools: Edit, NotebookEdit\n", self.claude_head("builder"))
        self.assertNotIn("disallowedTools", self.claude_head("planner"))
        self.ok("sync_agents", "--check")
        self.ok("check", "--strict")

    def test_access_full_adds_no_restriction(self) -> None:
        self.set_claude()
        self.add_charter_key("builder", "access: full")
        self.ok("sync_agents")
        self.assertNotIn("disallowedTools", self.claude_head("builder"))
        self.ok("check", "--strict")

    def test_shipped_read_only_roles_get_the_tool_limit(self) -> None:
        # reviewer and researcher write only their own item file (and, for the researcher, work/research/).
        # security owns docs/security/ and updates threat-model.md in place, so it is not read-only.
        self.set_claude()
        self.ok("sync_agents")
        for role in ("reviewer", "researcher"):
            self.assertIn("disallowedTools: Edit, NotebookEdit\n", self.claude_head(role), role)
        for role in ("builder", "planner", "architect", "scribe", "orchestrator", "security"):
            if not (self.repo / "agents" / "roles" / role / "ROLE.md").exists():
                continue  # the security module may be cut
            self.assertNotIn("disallowedTools", self.claude_head(role), role)

    def test_access_is_not_copied_to_cursor_rules(self) -> None:
        self.set_claude()
        self.enable(cursor=True)
        self.add_charter_key("builder", "access: read-only")
        self.ok("sync_agents")
        rule = self.head(self.repo / ".cursor" / "rules" / "role-builder.mdc")
        self.assertNotIn("disallowedTools", rule)
        self.assertNotIn("model:", rule)

    def test_unknown_access_value_is_reported_by_check_and_ignored_by_sync(self) -> None:
        self.set_claude()
        self.add_charter_key("builder", "access: read-write")
        r = self.sh("sync_agents")
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        self.assertNotIn("disallowedTools", self.claude_head("builder"))
        out = self.fails("check")
        self.assertIn("access", out)
        self.assertNotIn("Traceback", out)

    def test_models_map_writes_a_model_line_for_the_named_role_only(self) -> None:
        self.set_claude(models={"reviewer": "opus"})
        self.ok("sync_agents")
        self.assertIn("model: opus\n", self.claude_head("reviewer"))
        self.assertNotIn("model:", self.claude_head("builder"))
        self.ok("check", "--strict")
        self.set_claude(models={})
        self.assertIn("reviewer.md", self.fails("sync_agents", "--check"))
        self.ok("sync_agents")
        self.assertNotIn("model:", self.claude_head("reviewer"))

    def test_changing_the_tool_mapping_is_drift_until_synced(self) -> None:
        self.set_claude()
        self.add_charter_key("builder", "access: read-only")
        self.ok("sync_agents")
        self.set_claude(disallowed_tools={"read-only": ["Write"]})
        self.assertIn("builder.md", self.fails("sync_agents", "--check"))
        self.ok("sync_agents")
        self.assertIn("disallowedTools: Write\n", self.claude_head("builder"))
        self.ok("check", "--strict")

    def test_bad_adapter_extras_are_reported_without_crashing(self) -> None:
        for bad in (
            {"models": {"ghost": "opus"}},
            {"models": ["opus"]},
            {"models": {"reviewer": ""}},
            {"disallowed_tools": {"read-only": "Edit"}},
            {"disallowed_tools": {"read-only": ["Bash(git push *)"]}},
            {"disallowed_tools": {"read-write": ["Edit"]}},
        ):
            self.set_claude(**{**self.GOOD_CLAUDE_EXTRAS, **bad})
            out = self.fails("check")
            self.assertIn("adapters", out, bad)
            self.assertNotIn("Traceback", out, bad)
            r = self.sh("sync_agents")
            self.assertNotIn("Traceback", r.stdout + r.stderr, bad)

    def test_disallowed_tools_cannot_restrict_full(self) -> None:
        self.set_claude(disallowed_tools={"full": ["Edit"]})
        self.add_charter_key("builder", "access: full")
        out = self.fails("check")
        self.assertIn("full", out)
        self.assertNotIn("Traceback", out)
        self.ok("sync_agents")
        self.assertNotIn("disallowedTools", self.claude_head("builder"))

    def test_use_when_replaces_the_owner_role_sentence(self) -> None:
        self.set_claude()
        self.enable(cursor=True)
        self.add_charter_key("builder", "use_when: a planner asks for a second opinion")
        self.ok("sync_agents")
        for head in (self.claude_head("builder"), self.head(self.repo / ".cursor" / "rules" / "role-builder.mdc")):
            self.assertIn("Use when a planner asks for a second opinion.", head)
            self.assertNotIn("owner_role is builder", head)
        self.assertIn("handoff owner_role is planner", self.claude_head("planner"))

    def test_shipped_researcher_is_not_described_by_ownership(self) -> None:
        # The researcher never owns an item (ADR 0007), so "owner_role is researcher" can never match.
        self.set_claude()
        self.ok("sync_agents")
        head = self.claude_head("researcher")
        self.assertIn("Use when", head)
        self.assertNotIn("owner_role is researcher", head)

    def test_empty_use_when_fails_check(self) -> None:
        self.add_charter_key("builder", "use_when:")
        out = self.fails("check")
        self.assertIn("use_when", out)
        self.assertNotIn("Traceback", out)


if __name__ == "__main__":
    unittest.main()
