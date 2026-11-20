"""The eval-harness golden-task tests.

Split from test_tools.py so a project that cuts the evals module does not
carry them. RepoTestCase and its helpers stay in test_tools.py.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# In a generated project these tests are copied to tools/tests/; in this repo they live in tool-tests/.
# Put the tools/ directory on sys.path in both layouts before importing the tools.
_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent if _HERE.parent.name == "tools" else _HERE.parent / "tools"
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(_HERE))
import _lib  # noqa: E402
import eval_harness  # noqa: E402
from test_tools import RepoTestCase, run  # noqa: E402


class EvalHarnessTests(RepoTestCase):
    def test_eval_harness_lists_and_verifies_golden_tasks(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        listing = self.ok("eval_harness", "--list")
        for task_id in (
            "find-the-right-doc", "respect-ownership", "handoff-roundtrip", "escalation-discipline",
            "role-skill-discovery", "ambiguous-directive", "merge-discipline", "callable-researcher",
            "security-routing", "conditional-scribe",
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

    def test_find_the_right_doc_seeds_one_existing_project_adr(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        adr_glob = "[0-9][0-9][0-9][0-9]-*.md"
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "find-the-right-doc")
            decisions = sandbox / "docs" / "decisions"
            existing = sorted(p.name for p in decisions.glob(adr_glob))
            self.assertEqual(len(existing), 1, "the fixture must seed exactly one existing ADR")
            self.assertEqual(meta["existing_adrs"], set(existing), "existing_adrs must include the seeded ADR")
            eval_harness.run_reference_solution(sandbox, "find-the-right-doc", meta)
            passed, reason = eval_harness.grade_task(sandbox, "find-the-right-doc", meta)
            self.assertTrue(passed, reason)
        with tempfile.TemporaryDirectory() as tmp:
            other = eval_harness._clone_sandbox(self.repo, Path(tmp))
            eval_harness.seed_fixture(other, "handoff-roundtrip")
            self.assertEqual(sorted(p.name for p in (other / "docs" / "decisions").glob(adr_glob)), [],
                             "other tasks must not gain an existing ADR")

    def test_find_the_right_doc_seed_is_a_healthy_project(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "find-the-right-doc")
            check = run(sandbox, "check", "--strict")
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            sync = run(sandbox, "sync_indexes", "--check")
            self.assertEqual(sync.returncode, 0, sync.stdout + sync.stderr)
            text = (sandbox / meta["seeded_adr"]).read_text(encoding="utf-8")
            self.assertIsNone(eval_harness._PLACEHOLDER_RE.search(text),
                              "the seeded ADR still contains placeholder markers")
            heading = text.split("---", 2)[2].lstrip().splitlines()[0]
            self.assertRegex(heading, r"^# \d{4}: ")
            number = Path(meta["seeded_adr"]).name.split("-", 1)[0]
            self.assertEqual(heading.split(":", 1)[0], f"# {number}")

    def test_find_the_right_doc_grader_protects_the_seeded_adr(self) -> None:
        if "evals" not in _lib.load_modules(self.repo):
            self.skipTest("evals module not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "find-the-right-doc")
            eval_harness.run_reference_solution(sandbox, "find-the-right-doc", meta)
            passed, reason = eval_harness.grade_task(sandbox, "find-the-right-doc", meta)
            self.assertTrue(passed, reason)
            without = {k: v for k, v in meta.items() if k != "seeded_adr"}
            passed, reason = eval_harness.grade_task(sandbox, "find-the-right-doc", without)
            self.assertFalse(passed, "grading must fail closed when seeded_adr is missing")
            self.assertIn("seeded ADR", reason)
            seeded = sandbox / meta["seeded_adr"]
            text = seeded.read_text(encoding="utf-8")
            self.assertIn('Chosen option: "UTC"', text)
            seeded.write_text(text.replace('Chosen option: "UTC"', 'Chosen option: "local time"', 1), encoding="utf-8")
            passed, reason = eval_harness.grade_task(sandbox, "find-the-right-doc", meta)
            self.assertFalse(passed, reason)
            self.assertIn("seeded ADR", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "find-the-right-doc")
            eval_harness.run_reference_solution(sandbox, "find-the-right-doc", meta)
            (sandbox / meta["seeded_adr"]).unlink()
            passed, reason = eval_harness.grade_task(sandbox, "find-the-right-doc", meta)
            self.assertFalse(passed, reason)
            self.assertIn("seeded ADR", reason)

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

    def _solved_scribe(self, tmp: str):
        """A sandbox where the reference solution has run and passes, so the one deviation a test then makes is
        the only possible reason for the grader to fail."""
        sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
        meta = eval_harness.seed_fixture(sandbox, "conditional-scribe")
        eval_harness.run_reference_solution(sandbox, "conditional-scribe", meta)
        self._assert_graded_pass(sandbox, meta, "conditional-scribe")
        return sandbox, meta

    def _grade_scribe_fails(self, sandbox: Path, meta: dict) -> str:
        passed, reason = eval_harness.grade_task(sandbox, "conditional-scribe", meta)
        self.assertFalse(passed, reason)
        return reason

    def test_eval_harness_conditional_scribe_seeds_a_docs_free_and_a_docs_listed_item(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = eval_harness._clone_sandbox(self.repo, Path(tmp))
            meta = eval_harness.seed_fixture(sandbox, "conditional-scribe")
            self.assertNotEqual(meta["skip_id"], meta["listed_id"])
            for key in ("skip", "listed"):
                item_dir = sandbox / "work" / "items" / meta[f"{key}_id"]
                fm = _lib.read_fm(item_dir / "handoff.md")
                self.assertEqual((fm["status"], fm["owner_role"], fm["built_by"]), ("in-review", "reviewer", "builder"))
                self.assertIn(meta[f"{key}_line"], (item_dir / "handoff.md").read_text(encoding="utf-8"))
            self.assertTrue(meta["skip_line"].startswith("Docs for the scribe: none"), meta["skip_line"])
            self.assertFalse(meta["listed_line"].startswith("Docs for the scribe: none"), meta["listed_line"])
            # nothing is routed yet, so a reviewer that did nothing must not pass
            reason = self._grade_scribe_fails(sandbox, meta)
        self.assertIn("should be verified", reason)

    def test_eval_harness_rejects_a_reviewer_who_sends_the_docs_free_item_to_the_scribe(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_scribe(tmp)
            eval_harness.transition.transition(sandbox, meta["skip_id"], None, "Scribe: update docs", "scribe", [])
            reason = self._grade_scribe_fails(sandbox, meta)
        self.assertIn("scribe is skipped", reason)

    def test_eval_harness_rejects_a_reviewer_who_skips_the_scribe_for_the_item_that_lists_docs(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_scribe(tmp)
            eval_harness.transition.transition(
                sandbox, meta["listed_id"], None, "Orchestrator: mark done", "orchestrator", [])
            reason = self._grade_scribe_fails(sandbox, meta)
        self.assertIn("must go to the scribe", reason)

    def test_eval_harness_rejects_a_reviewer_who_marks_a_conditional_scribe_item_done(self) -> None:
        self._require_evals()
        for key in ("skip_id", "listed_id"):
            with self.subTest(item=key), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_scribe(tmp)
                eval_harness.transition.transition(sandbox, meta[key], "done", None, None, [], by_role="reviewer")
                reason = self._grade_scribe_fails(sandbox, meta)
                self.assertIn("should be verified", reason)

    def test_eval_harness_rejects_a_reviewer_who_rewrites_the_scribe_docs_line(self) -> None:
        """Editing the builder's claim is the cheap way to skip the scribe, so the grader pins the line."""
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_scribe(tmp)
            handoff = sandbox / "work" / "items" / meta["listed_id"] / "handoff.md"
            text = _lib.read_text(handoff)
            assert meta["listed_line"] in text
            _lib.write_text(handoff, text.replace(meta["listed_line"], "Docs for the scribe: none, behavior unchanged."))
            eval_harness.transition.transition(
                sandbox, meta["listed_id"], None, "Orchestrator: mark done", "orchestrator", [])
            reason = self._grade_scribe_fails(sandbox, meta)
        self.assertIn("was changed", reason)

    def test_eval_harness_rejects_a_conditional_scribe_item_verified_by_the_wrong_role_or_with_an_unfilled_review(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_scribe(tmp)
            handoff = sandbox / "work" / "items" / meta["skip_id"] / "handoff.md"
            _lib.write_text(handoff, _lib.set_fm_value(_lib.read_text(handoff), "verified_by", "orchestrator"))
            reason = self._grade_scribe_fails(sandbox, meta)
        self.assertIn("verified_by reviewer", reason)
        for key in ("skip_id", "listed_id"):
            with self.subTest(item=key), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_scribe(tmp)
                review = sandbox / "work" / "items" / meta[key] / "review.md"
                text = _lib.read_text(review)
                assert "| pass |" in text
                _lib.write_text(review, text.replace("| pass |", "| fail |"))
                reason = self._grade_scribe_fails(sandbox, meta)
                self.assertIn("not a filled pass", reason)

    def test_eval_harness_rejects_a_conditional_scribe_run_that_edits_the_harness_the_docs_or_adds_items(self) -> None:
        self._require_evals()
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_scribe(tmp)
            with open(sandbox / "agents" / "roles" / "scribe" / "ROLE.md", "a", encoding="utf-8") as fh:
                fh.write("\nAn unrelated edit.\n")
            eval_harness.sync_agents.sync(sandbox)
            eval_harness.sync_indexes.write_outputs(sandbox)
            reason = self._grade_scribe_fails(sandbox, meta)
        self.assertIn("agents/", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_scribe(tmp)
            with open(sandbox / "CHANGELOG.md", "a", encoding="utf-8") as fh:
                fh.write("\n- A line the reviewer must not write.\n")
            reason = self._grade_scribe_fails(sandbox, meta)
        self.assertIn("outside the review", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_scribe(tmp)
            with open(sandbox / "docs" / "README.md", "a", encoding="utf-8") as fh:
                fh.write("\nA sentence the reviewer must not write: docs are the scribe's.\n")
            reason = self._grade_scribe_fails(sandbox, meta)
        self.assertIn("scribe's files", reason)
        with tempfile.TemporaryDirectory() as tmp:
            sandbox, meta = self._solved_scribe(tmp)
            eval_harness.new_item.create(sandbox, "extra-item", "Extra", True, "builder", "planned")
            reason = self._grade_scribe_fails(sandbox, meta)
        self.assertIn("only the seeded items", reason)
        for key in ("skip_id", "listed_id"):
            with self.subTest(item=key), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_scribe(tmp)
                eval_harness.item_file.add_file(sandbox, meta[key], "plan")
                reason = self._grade_scribe_fails(sandbox, meta)
                self.assertIn("seeded files and review.md only", reason)
        for key in ("skip", "listed"):
            with self.subTest(brief=key), tempfile.TemporaryDirectory() as tmp:
                sandbox, meta = self._solved_scribe(tmp)
                brief = sandbox / "work" / "items" / meta[f"{key}_id"] / "brief.md"
                brief.write_text(brief.read_text(encoding="utf-8") + "\nAn edit.\n", encoding="utf-8")
                reason = self._grade_scribe_fails(sandbox, meta)
                self.assertIn("brief.md", reason)


if __name__ == "__main__":
    unittest.main()
