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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import _lib  # noqa: E402


_SKIP_ANYWHERE = shutil.ignore_patterns(".git", "__pycache__", ".locks", "*.pyc", "node_modules", ".venv")
_CODE_FOLDERS = {"src", "apps", "packages", "tests"}  # product code is irrelevant here and may be huge
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

    def test_agents_md_over_budget_fails(self) -> None:
        p = self.repo / "AGENTS.md"
        p.write_text(p.read_text() + "\n".join(f"- extra rule {i}" for i in range(120)) + "\n")
        self.assertIn("agents-md-size", self.fails("check"))

    def test_broken_link_fails(self) -> None:
        p = self.repo / "docs" / "explanation" / "design-rationale.md"
        p.write_text(p.read_text() + "\nSee [nowhere](does-not-exist.md).\n")
        self.assertIn("broken-link", self.fails("check"))

    def test_missing_summary_fails(self) -> None:
        p = self.repo / "docs" / "reference" / "glossary.md"
        p.write_text(p.read_text().replace("summary:", "sumary:", 1))
        self.assertIn("front-matter", self.fails("check"))

    def test_wrong_diataxis_folder_fails(self) -> None:
        p = self.repo / "docs" / "reference" / "glossary.md"
        p.write_text(p.read_text().replace("type: reference", "type: how-to", 1))
        self.assertIn("diataxis", self.fails("check"))

    def test_hand_edited_generated_file_fails_until_synced(self) -> None:
        p = self.repo / "docs" / "INDEX.md"
        p.write_text(p.read_text() + "\nhand edit\n")
        self.assertIn("generated-drift", self.fails("check"))
        self.ok("sync_indexes")
        self.ok("check")

    def test_role_change_requires_resync(self) -> None:
        p = self.repo / "agents" / "roles" / "builder.md"
        p.write_text(p.read_text().replace("Implement work items", "Build work items", 1))
        out = self.fails("check")
        self.assertTrue("generated-drift" in out or "adapter-drift" in out)
        self.ok("sync_indexes")
        self.ok("sync_agents")
        self.ok("check")

    def test_duplicate_item_file_ownership_fails(self) -> None:
        p = self.repo / "agents" / "roles" / "builder.md"
        p.write_text(p.read_text().replace("item_files: []", "item_files: [brief.md]", 1))
        self.ok("sync_indexes")
        self.ok("sync_agents")
        self.assertIn("ownership", self.fails("check"))

    def test_unknown_owner_role_fails(self) -> None:
        p = self.repo / "work" / "inbox" / "README.md"
        p.write_text(p.read_text().replace("owner_role: orchestrator", "owner_role: ghost", 1))
        self.assertIn("ownership", self.fails("check"))

    def test_skill_name_must_match_folder(self) -> None:
        p = self.repo / "agents" / "skills" / "write-doc" / "SKILL.md"
        p.write_text(p.read_text().replace("name: write-doc", "name: Write_Doc", 1))
        self.assertIn("skill", self.fails("check"))

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
        p = self.repo / "docs" / "explanation" / "design-rationale.md"
        p.write_text(p.read_text() + f"\nSee [module](../../{target}).\n")
        self.assertIn("module-coupling", self.fails("check"))


class WorkLifecycleTests(RepoTestCase):
    def test_full_lifecycle_and_guard_rails(self) -> None:
        item = self.new_item("login flow", "--title", "Login: the flow")
        self.assertRegex(item, r"^\d{4}-\d{2}-\d{2}-login-flow$")
        self.assertIn(item, (self.repo / "work" / "ACTIVE.md").read_text())
        self.ok("check")

        self.fails("transition", item, "done")  # draft -> done is illegal
        self.assertIn("--next", self.fails("transition", item, "planned"))
        self.ok("transition", item, "planned", "--next", "builder: start")
        self.ok("transition", item, "in-progress", "--next", "building")
        self.assertIn("allowed from in-progress", self.fails("transition", item, "done", "--next", "x"))
        self.assertIn("evidence", self.fails("transition", item, "in-review", "--next", "verify"))
        self.ok("transition", item, "in-review", "--next", "verify", "--evidence", "python3 tools/check.py")
        self.assertIn("review.md", self.fails("transition", item, "verified", "--next", "docs"))
        self.ok("item_file", item, "review")
        self.fails("item_file", item, "review")  # never overwrites
        self.ok("transition", item, "verified", "--next", "update docs")
        self.ok("transition", item, "done")
        self.ok("check")
        self.ok("archive_item", item)
        self.assertFalse((self.repo / "work" / "items" / item).exists())
        self.assertTrue(list((self.repo / "work" / "archive").glob(f"*/{item}")))
        self.assertNotIn(item, (self.repo / "work" / "ACTIVE.md").read_text())
        self.ok("check")

    def test_archive_refuses_unfinished_items(self) -> None:
        item = self.new_item("half-done")
        self.assertIn("only done items", self.fails("archive_item", item))

    def test_blocked_needs_a_reason_and_can_resume(self) -> None:
        item = self.new_item("waits")
        self.ok("transition", item, "planned", "--next", "go")
        self.fails("transition", item, "blocked")
        self.ok("transition", item, "blocked", "--next", "waiting on Q-0001")
        self.ok("transition", item, "in-progress", "--next", "resumed")

    def test_light_item_has_one_file_and_still_needs_evidence(self) -> None:
        item = self.new_item("quick-fix", "--light")
        self.assertTrue((self.repo / "work" / "items" / f"{item}.md").is_file())
        self.fails("item_file", item, "review")
        self.ok("transition", item, "planned", "--next", "go")
        self.ok("transition", item, "in-progress", "--next", "go")
        self.fails("transition", item, "in-review", "--next", "verify")
        self.ok("transition", item, "in-review", "--next", "verify", "--evidence", "ran it")
        self.ok("transition", item, "verified", "--next", "close")
        self.ok("transition", item, "done")
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
        self.assertIn("stale", self.ok("archive_item", "--sweep"))
        fm = _lib.read_fm(h)
        self.assertEqual((fm["status"], fm["owner_role"]), ("stale", "orchestrator"))
        self.ok("transition", item, "planned", "--next", "re-triaged")

    def test_sweep_archives_old_done_items(self) -> None:
        item = self.new_item("ancient", "--light")
        self.ok("transition", item, "planned", "--next", "g")
        self.ok("transition", item, "in-progress", "--next", "g")
        self.ok("transition", item, "in-review", "--next", "g", "--evidence", "e")
        self.ok("transition", item, "verified", "--next", "g")
        self.ok("transition", item, "done")
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
        self.ok("transition", quick, "planned", "--next", "go")
        self.ok("transition", quick, "in-progress", "--next", "going")
        self.ok("transition", quick, "in-review", "--next", "look", "--evidence", "ran it")
        self.ok("transition", quick, "verified", "--next", "close", "--evidence", "checked")
        self.ok("transition", quick, "done")
        self.assertIn("final", self.fails("transition", quick, "--next", "too late"))

    def test_light_item_can_be_handed_straight_to_another_role(self) -> None:
        item = self.new_item("update-vision", "--light", "--status", "planned", "--owner", "planner")
        fm = _lib.read_fm(_lib.find_item(self.repo, item).handoff)
        self.assertEqual((fm["status"], fm["owner_role"]), ("planned", "planner"))
        self.ok("check")


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
        second = self.ok("new_adr", "Switch to SQLite", "--supersedes", Path(first).name[:4], "--status", "accepted")
        n1, n2 = Path(first).name[:4], Path(second).name[:4]
        self.assertEqual(int(n2), int(n1) + 1)
        self.assertEqual(_lib.read_fm(self.repo / first)["status"], "superseded")
        self.assertEqual(str(_lib.read_fm(self.repo / first)["superseded_by"]).zfill(4), n2)
        self.assertEqual([str(x).zfill(4) for x in _lib.read_fm(self.repo / second)["supersedes"]], [n1])
        self.ok("check")

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
        self.assertEqual(path, "docs/how-to/deploy-to-staging.md")
        self.assertIn("deploy-to-staging.md", (self.repo / "docs" / "INDEX.md").read_text())
        self.ok("check")
        self.fails("new_doc", "how-to", "Deploy: to staging")  # exists
        self.fails("new_doc", "poem", "Nope")


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
    def test_adapters_are_generated_and_removed_with_their_source(self) -> None:
        targets = _lib.load_targets(self.repo)
        if not targets.get("claude", {}).get("enabled"):
            self.skipTest("claude adapter disabled")
        agent = self.repo / ".claude" / "agents" / "builder.md"
        self.assertTrue(agent.is_file())
        self.assertTrue((self.repo / "CLAUDE.md").read_text().strip() == "@AGENTS.md")
        self.assertIn("name: builder", agent.read_text())
        shutil.rmtree(self.repo / "agents" / "skills" / "write-doc")
        self.ok("sync_agents")
        self.assertFalse((self.repo / ".claude" / "skills" / "write-doc").exists())
        self.ok("sync_indexes")
        self.ok("check")

    def test_sync_refuses_to_overwrite_a_hand_written_file(self) -> None:
        targets = _lib.load_targets(self.repo)
        if not targets.get("claude", {}).get("enabled"):
            self.skipTest("claude adapter disabled")
        (self.repo / "agents" / "skills" / "write-doc" / "extra.md").write_text("x\n")
        (self.repo / ".claude" / "skills" / "write-doc" / "extra.md").write_text("mine\n")
        r = self.sh("sync_agents")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.repo / ".claude" / "skills" / "write-doc" / "extra.md").read_text(), "mine\n")

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

    def test_cursor_and_copilot_are_disabled_by_default(self) -> None:
        targets = _lib.load_targets(self.repo)
        self.assertFalse(targets["cursor"]["enabled"])
        self.assertFalse(targets["copilot"]["enabled"])
        self.assertFalse((self.repo / ".cursor").exists())
        self.assertFalse((self.repo / ".github" / "copilot-instructions.md").exists())

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
        charter = self.repo / "agents" / "roles" / "builder.md"
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

    def test_copilot_adapter_does_not_turn_the_github_module_on(self) -> None:
        if "github" in _lib.load_modules(self.repo):
            self.ok("remove_module", "github", "--apply")
        self.enable(copilot=True)
        self.ok("sync_agents")
        self.assertTrue((self.repo / ".github" / "copilot-instructions.md").is_file())
        self.assertNotIn("github", _lib.load_modules(self.repo))
        self.ok("sync_indexes", "--check")
        self.assertNotIn("`.github/`", (self.repo / "docs" / "reference" / "repo-map.md").read_text())
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
