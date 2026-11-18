"""Tests for `.github/scripts/merge_guarded.sh`.

Each test runs the real script against a fake `gh` and a fake `git` placed first on `PATH`.
The fakes answer from a scenario file and record every call, so no test contacts GitHub and
no test can merge anything. A refusal test also asserts that the merge call was never made.

The script lives outside `template/`: it guards this repository's merges only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / ".github/scripts/merge_guarded.sh"
REPO = "The-Urcydo/Repo-Template"
HEAD = "0123456789abcdef0123456789abcdef01234567"
MERGE = "fedcba9876543210fedcba9876543210fedcba98"
OTHER = "9999999999999999999999999999999999999999"
BRANCH = "chore/example"
CODEOWNERS = "# owners\n*   @nguyenquocduyloc   @NguyenLoc231\n"

FAKE_GH = r'''
import json
import os
import sys
from pathlib import Path

scenario_dir = Path(os.environ["FAKE_GH_DIR"])
argv = sys.argv[1:]
with (scenario_dir / "calls.jsonl").open("a") as log:
    log.write(json.dumps(argv) + "\n")

url = next((a for a in argv if a.startswith("repos/")), "")
scenario = json.loads((scenario_dir / "scenario.json").read_text())
route = next((r for r in scenario["routes"] if r["match"] in url), None)
if route is None:
    print(f"fake gh: no route for {url}", file=sys.stderr)
    sys.exit(1)

state_path = scenario_dir / "state.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {}
key = route["match"]
index = state.get(key, 0)
state[key] = index + 1
state_path.write_text(json.dumps(state))

item = route["responses"][min(index, len(route["responses"]) - 1)]
if isinstance(item, dict) and "__fail__" in item:
    print(item["__fail__"], file=sys.stderr)
    sys.exit(1)
if isinstance(item, dict) and "__status__" in item:
    print(item.get("__body__", ""), file=sys.stderr)
    sys.exit(item["__status__"])
if "--paginate" in argv:
    for page in item:
        print(json.dumps(page))
else:
    print(json.dumps(item))
'''

FAKE_GIT = """#!/bin/sh
[ "$1" = show ] || { echo "fake git: $*" >&2; exit 1; }
cat "$FAKE_CODEOWNERS"
"""


@dataclass
class Result:
    code: int
    out: str
    err: str
    calls: list[list[str]]

    @property
    def merge_calls(self) -> list[list[str]]:
        return [c for c in self.calls if "-X" in c and any(a.endswith("/merge") for a in c)]

    @property
    def urls(self) -> list[str]:
        return [next((a for a in c if a.startswith("repos/")), "") for c in self.calls]


def head(sha: str = HEAD, ref: str = BRANCH, repo: str = REPO) -> dict:
    return {"sha": sha, "ref": ref, "label": f"The-Urcydo:{ref}", "repo": {"full_name": repo}}


def pull_request(**over) -> dict:
    value = {
        "number": 7,
        "state": "open",
        "draft": False,
        "title": "chore: example",
        "base": {"ref": "main"},
        "head": head(),
        "mergeable_state": "clean",
    }
    value.update(over)
    return value


def review(login: str = "NguyenLoc231", state: str = "APPROVED", sha: str = HEAD,
           at: str = "2026-11-18T10:00:00Z") -> dict:
    return {"user": {"login": login}, "state": state, "commit_id": sha, "submitted_at": at}


def check_run(name: str = "ci-gate", status: str = "completed", conclusion: str | None = "success",
              run_id: int = 1, app: int = 15368) -> dict:
    return {"name": name, "status": status, "conclusion": conclusion, "id": run_id, "app": {"id": app}}


def check_page(checks) -> dict:
    return {"total_count": len(checks), "check_runs": list(checks)}


def build_scenario(*, prs=None, files=("README.md",), reviews=None, checks=None, merge=None,
                   commit=None, main_checks=None, branch_exists=False, codeowners=CODEOWNERS) -> dict:
    prs = list(prs) if prs is not None else [pull_request()]
    reviews = list(reviews) if reviews is not None else [review()]
    checks = list(checks) if checks is not None else [check_run()]
    main_checks = list(main_checks) if main_checks is not None else [check_run()]
    merge = merge if merge is not None else {"merged": True, "sha": MERGE}
    commit = commit if commit is not None else {"parents": [{"sha": HEAD}, {"sha": "1" * 40}]}
    return {
        "codeowners": codeowners,
        "routes": [
            {"match": "pulls/7/files",
             "responses": [[[{"filename": name} for name in files]]]},
            {"match": "pulls/7/reviews", "responses": [[reviews]]},
            {"match": "pulls/7/merge", "responses": [merge]},
            {"match": f"commits/{HEAD}/check-runs", "responses": [[check_page(checks)]]},
            {"match": f"commits/{MERGE}/check-runs", "responses": [[check_page(main_checks)]]},
            {"match": f"commits/{MERGE}", "responses": [commit]},
            {"match": "git/ref/heads/", "responses": [{"__status__": 404} if not branch_exists else {}]},
            {"match": "pulls/7", "responses": prs},
        ],
    }


def route(scenario: dict, match: str) -> dict:
    return next(r for r in scenario["routes"] if r["match"] == match)


def run_guard(tmp_path: Path, scenario: dict | None = None, *, args=None,
              files=("README.md",), head_sha: str = HEAD, env_overrides: dict | None = None) -> Result:
    scenario = scenario if scenario is not None else build_scenario()
    bin_dir = tmp_path / "bin"
    scenario_dir = tmp_path / "scenario"
    bin_dir.mkdir(parents=True)
    scenario_dir.mkdir(parents=True)

    gh = bin_dir / "gh"
    gh.write_text(f"#!{sys.executable}\n{FAKE_GH}")
    gh.chmod(0o755)
    git = bin_dir / "git"
    git.write_text(FAKE_GIT)
    git.chmod(0o755)

    codeowners = scenario_dir / "codeowners"
    codeowners.write_text(scenario.pop("codeowners"))
    (scenario_dir / "scenario.json").write_text(json.dumps(scenario))

    if args is None:
        reviewed = tmp_path / "reviewed-files.txt"
        reviewed.write_text("".join(f"{name}\n" for name in files))
        args = ["7", head_sha, str(reviewed)]

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FAKE_GH_DIR": str(scenario_dir),
        "FAKE_CODEOWNERS": str(codeowners),
        "MERGEABLE_POLLS": "2",
        "MERGEABLE_SLEEP": "0",
        "MAIN_CI_POLLS": "2",
        "MAIN_CI_SLEEP": "0",
        **(env_overrides or {}),
    }
    proc = subprocess.run([str(GUARD), *args], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=60)
    log = scenario_dir / "calls.jsonl"
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return Result(proc.returncode, proc.stdout, proc.stderr, calls)


def assert_refused(result: Result, needle: str) -> None:
    assert result.code == 2, f"exit {result.code}\nstdout:\n{result.out}\nstderr:\n{result.err}"
    assert "REFUSE:" in result.err
    assert needle in result.err, result.err
    assert result.merge_calls == [], result.merge_calls


# ---------------------------------------------------------------- the happy path

def test_a_clean_approved_pr_merges(tmp_path):
    result = run_guard(tmp_path, build_scenario())

    assert result.code == 0, result.err
    assert "DONE: #7 merged" in result.out
    [call] = result.merge_calls
    assert "merge_method=merge" in call
    assert f"sha={HEAD}" in call
    message = next(a for a in call if a.startswith("commit_message=")).split("=", 1)[1]
    assert message.startswith("Merge pull request #7 from The-Urcydo/chore/example")
    assert message.endswith("Delegated-under: ADR-0011")
    assert f"repos/{REPO}/commits/{MERGE}/check-runs" in result.urls
    assert f"repos/{REPO}/git/ref/heads/{BRANCH}" in result.urls


def test_the_script_is_executable_and_parses(tmp_path):
    assert os.access(GUARD, os.X_OK)
    parsed = subprocess.run(["bash", "-n", str(GUARD)], capture_output=True, text=True)
    assert parsed.returncode == 0, parsed.stderr


# ---------------------------------------------------------------- PR state

def test_a_closed_pr_is_refused(tmp_path):
    assert_refused(run_guard(tmp_path, build_scenario(prs=[pull_request(state="closed")])),
                   "the PR is not open")


def test_a_draft_is_refused(tmp_path):
    assert_refused(run_guard(tmp_path, build_scenario(prs=[pull_request(draft=True)])),
                   "the PR is a draft")


def test_a_fork_is_refused(tmp_path):
    pr = pull_request(head=head(repo="someone/fork"))
    assert_refused(run_guard(tmp_path, build_scenario(prs=[pr])), "not a branch of")


def test_a_base_other_than_main_is_refused(tmp_path):
    pr = pull_request(base={"ref": "develop"})
    assert_refused(run_guard(tmp_path, build_scenario(prs=[pr])), "the base is develop, not main")


def test_a_moved_head_is_refused(tmp_path):
    assert_refused(run_guard(tmp_path, build_scenario(prs=[pull_request(head=head(sha=OTHER))])),
                   "not the reviewed")


# ---------------------------------------------------------------- the reviewed file list

def test_an_extra_live_file_is_refused(tmp_path):
    scenario = build_scenario(files=("README.md", "AGENTS.md"))
    assert_refused(run_guard(tmp_path, scenario, files=("README.md",)),
                   "the changed-file list differs from the reviewed list")


def test_a_missing_live_file_is_refused(tmp_path):
    scenario = build_scenario(files=("README.md",))
    assert_refused(run_guard(tmp_path, scenario, files=("README.md", "AGENTS.md")),
                   "the changed-file list differs from the reviewed list")


def test_the_reviewed_file_order_does_not_matter(tmp_path):
    scenario = build_scenario(files=("README.md", "AGENTS.md"))
    result = run_guard(tmp_path, scenario, files=("AGENTS.md", "README.md"))
    assert result.code == 0, result.err
    assert len(result.merge_calls) == 1


def test_a_pr_at_the_file_list_cap_is_refused(tmp_path):
    capped = tuple(f"file-{number:04d}.txt" for number in range(3000))
    result = run_guard(tmp_path, build_scenario(files=capped), files=capped)
    assert_refused(result, "3000 or more files")


# ---------------------------------------------------------------- approvals

def test_no_approval_is_refused(tmp_path):
    assert_refused(run_guard(tmp_path, build_scenario(reviews=[])),
                   "no CODEOWNERS login has approved the latest commit")


def test_an_approval_of_an_older_commit_is_refused(tmp_path):
    assert_refused(run_guard(tmp_path, build_scenario(reviews=[review(sha=OTHER)])),
                   "no CODEOWNERS login has approved the latest commit")


def test_a_non_owner_approval_is_refused(tmp_path):
    assert_refused(run_guard(tmp_path, build_scenario(reviews=[review(login="shiniroku")])),
                   "no CODEOWNERS login has approved the latest commit")


def test_a_comment_after_an_approval_does_not_cancel_it(tmp_path):
    later = review(state="COMMENTED", at="2026-11-18T11:00:00Z")
    result = run_guard(tmp_path, build_scenario(reviews=[review(), later]))
    assert result.code == 0, result.err


def test_a_change_request_after_an_approval_cancels_it(tmp_path):
    later = review(state="CHANGES_REQUESTED", at="2026-11-18T11:00:00Z")
    assert_refused(run_guard(tmp_path, build_scenario(reviews=[review(), later])),
                   "a CODEOWNERS login has a change request on the head")


def test_a_dismissal_after_an_approval_cancels_it(tmp_path):
    later = review(state="DISMISSED", at="2026-11-18T11:00:00Z")
    assert_refused(run_guard(tmp_path, build_scenario(reviews=[review(), later])),
                   "no CODEOWNERS login has approved the latest commit")


def test_one_owner_blocking_another_owners_approval_cancels_it(tmp_path):
    blocking = review(login="nguyenquocduyloc", state="CHANGES_REQUESTED", at="2026-11-18T11:00:00Z")
    assert_refused(run_guard(tmp_path, build_scenario(reviews=[review(), blocking])),
                   "a CODEOWNERS login has a change request on the head")


def test_a_non_owner_change_request_does_not_cancel_an_owner_approval(tmp_path):
    # GitHub's own mergeability blocks a change request from anyone; the guard only judges owners and
    # leaves that part to mergeable_state (which a real blocked PR reports as "blocked").
    other = review(login="shiniroku", state="CHANGES_REQUESTED", at="2026-11-18T11:00:00Z")
    result = run_guard(tmp_path, build_scenario(reviews=[review(), other]))
    assert result.code == 0, result.err


def test_logins_match_without_case(tmp_path):
    result = run_guard(tmp_path, build_scenario(reviews=[review(login="nguyenloc231")]))
    assert result.code == 0, result.err


def test_codeowners_comments_blanks_duplicates_and_case_are_handled(tmp_path):
    text = "# owners\n\n* @NguyenQuocDuyLoc @nguyenquocduyloc @NguyenLoc231\n/AGENTS.md @NguyenLoc231\n"
    result = run_guard(tmp_path, build_scenario(codeowners=text,
                                               reviews=[review(login="nguyenquocduyloc")]))
    assert result.code == 0, result.err


def test_codeowners_without_an_owner_is_refused(tmp_path):
    assert_refused(run_guard(tmp_path, build_scenario(codeowners="# nobody\n*")),
                   "CODEOWNERS names no owners")


# ---------------------------------------------------------------- mergeability

def test_mergeable_state_is_polled_until_clean(tmp_path):
    prs = [pull_request(mergeable_state="unknown"), pull_request(mergeable_state="clean")]
    result = run_guard(tmp_path, build_scenario(prs=prs))
    assert result.code == 0, result.err
    reads = [u for u in result.urls if u == f"repos/{REPO}/pulls/7"]
    assert len(reads) == 2, result.urls


def test_mergeable_state_that_stays_unknown_is_refused(tmp_path):
    assert_refused(run_guard(tmp_path, build_scenario(prs=[pull_request(mergeable_state="unknown")])),
                   "mergeable_state is unknown, not clean")


def test_a_dirty_mergeable_state_is_refused(tmp_path):
    assert_refused(run_guard(tmp_path, build_scenario(prs=[pull_request(mergeable_state="dirty")])),
                   "mergeable_state is dirty, not clean")


# ---------------------------------------------------------------- checks

def test_a_pending_check_is_refused(tmp_path):
    checks = [check_run(status="in_progress", conclusion=None)]
    assert_refused(run_guard(tmp_path, build_scenario(checks=checks)),
                   "the latest run of a check is not completed green")


def test_a_failed_check_is_refused(tmp_path):
    assert_refused(run_guard(tmp_path, build_scenario(checks=[check_run(conclusion="failure")])),
                   "the latest run of a check is not completed green")


def test_a_failed_non_required_check_is_refused(tmp_path):
    checks = [check_run(), check_run(name="optional", conclusion="failure", run_id=2)]
    assert_refused(run_guard(tmp_path, build_scenario(checks=checks)),
                   "the latest run of a check is not completed green")


def test_neutral_and_skipped_checks_merge(tmp_path):
    checks = [check_run(), check_run(name="optional", conclusion="neutral", run_id=2),
              check_run(name="docs", conclusion="skipped", run_id=3)]
    result = run_guard(tmp_path, build_scenario(checks=checks))
    assert result.code == 0, result.err


def test_an_older_failed_run_of_a_green_rerun_is_ignored(tmp_path):
    checks = [check_run(conclusion="failure", run_id=1), check_run(conclusion="success", run_id=2)]
    result = run_guard(tmp_path, build_scenario(checks=checks))
    assert result.code == 0, result.err


def test_a_newer_failed_rerun_of_a_green_check_is_refused(tmp_path):
    checks = [check_run(conclusion="success", run_id=1), check_run(conclusion="failure", run_id=2)]
    assert_refused(run_guard(tmp_path, build_scenario(checks=checks)),
                   "the latest run of a check is not completed green")


def test_paginated_files_reviews_and_checks_are_read(tmp_path):
    scenario = build_scenario(files=("README.md", "AGENTS.md"))
    route(scenario, "pulls/7/files")["responses"] = [[
        [{"filename": "README.md"}], [{"filename": "AGENTS.md"}],
    ]]
    route(scenario, "pulls/7/reviews")["responses"] = [[
        [review()], [review(state="COMMENTED", at="2026-11-18T11:00:00Z")],
    ]]
    route(scenario, f"commits/{HEAD}/check-runs")["responses"] = [[
        check_page([check_run()]), check_page([check_run(name="optional", run_id=2)]),
    ]]
    result = run_guard(tmp_path, scenario, files=("README.md", "AGENTS.md"))
    assert result.code == 0, result.err
    files_calls = [c for c in result.calls if any("pulls/7/files" in a for a in c)]
    assert files_calls and "--paginate" in files_calls[0]


# ---------------------------------------------------------------- the merge call and after it

def test_a_merge_refused_by_github_exits_2(tmp_path):
    merge = {"merged": False, "message": "Pull request is not mergeable"}
    result = run_guard(tmp_path, build_scenario(merge=merge))
    assert result.code == 2, (result.code, result.err)
    assert "GitHub did not merge: Pull request is not mergeable" in result.err
    assert len(result.merge_calls) == 1
    assert f"repos/{REPO}/commits/{MERGE}" not in result.urls


def test_a_merge_http_error_exits_1(tmp_path):
    merge = {"__status__": 422, "__body__": "not mergeable"}
    result = run_guard(tmp_path, build_scenario(merge=merge))
    assert result.code == 1, (result.code, result.err)
    assert "ERROR: the merge call failed" in result.err


def test_a_one_parent_merge_exits_3(tmp_path):
    result = run_guard(tmp_path, build_scenario(commit={"parents": [{"sha": HEAD}]}))
    assert result.code == 3, (result.code, result.err)
    assert "parents, not 2" in result.err


def test_a_branch_left_behind_exits_3(tmp_path):
    result = run_guard(tmp_path, build_scenario(branch_exists=True))
    assert result.code == 3, (result.code, result.err)
    assert "still exists" in result.err


def test_failed_main_ci_exits_3(tmp_path):
    result = run_guard(tmp_path, build_scenario(main_checks=[check_run(conclusion="failure")]))
    assert result.code == 3, (result.code, result.err)
    assert "main ci-gate is completed failure" in result.err


def test_main_ci_that_never_finishes_exits_3(tmp_path):
    pending = check_run(status="in_progress", conclusion=None)
    result = run_guard(tmp_path, build_scenario(main_checks=[pending]))
    assert result.code == 3, (result.code, result.err)
    assert "did not finish green" in result.err


def test_main_ci_is_polled_until_green(tmp_path):
    pending = check_run(status="in_progress", conclusion=None)
    green = check_run()
    scenario = build_scenario()
    route(scenario, f"commits/{MERGE}/check-runs")["responses"] = [
        [check_page([pending])], [check_page([green])],
    ]
    result = run_guard(tmp_path, scenario)
    assert result.code == 0, result.err
    assert "main ci-gate: completed success" in result.out


# ---------------------------------------------------------------- arguments and reads

def test_usage_errors_exit_2(tmp_path):
    cases = ([], ["seven", HEAD, "/dev/null"], ["7", "abc", "/dev/null"],
             ["7", HEAD.upper(), "/dev/null"], ["7", HEAD, "/nonexistent/files.txt"])
    for index, args in enumerate(cases):
        result = run_guard(tmp_path / f"case-{index}", build_scenario(), args=args)
        assert result.code == 2, (args, result.code, result.err)
        assert "REFUSE:" in result.err


def test_a_bad_poll_setting_is_refused(tmp_path):
    result = run_guard(tmp_path, build_scenario(), env_overrides={"MERGEABLE_POLLS": "0"})
    assert result.code == 2, (result.code, result.err)
    assert "MERGEABLE_POLLS must be a positive integer" in result.err


def test_a_failed_pr_read_exits_1(tmp_path):
    prs = [{"__fail__": "HTTP 500: server error"}]
    result = run_guard(tmp_path, build_scenario(prs=prs))
    assert result.code == 1, (result.code, result.err)
    assert "ERROR: cannot read PR #7" in result.err
    assert result.merge_calls == []


def test_a_failed_file_read_exits_1(tmp_path):
    scenario = build_scenario()
    route(scenario, "pulls/7/files")["responses"] = [{"__fail__": "HTTP 502"}]
    result = run_guard(tmp_path, scenario)
    assert result.code == 1, (result.code, result.err)
    assert "ERROR: cannot read the PR files" in result.err


def test_a_failed_review_read_exits_1(tmp_path):
    scenario = build_scenario()
    route(scenario, "pulls/7/reviews")["responses"] = [{"__fail__": "HTTP 502"}]
    result = run_guard(tmp_path, scenario)
    assert result.code == 1, (result.code, result.err)
    assert "ERROR: cannot read the reviews" in result.err


def test_a_failed_check_read_exits_1(tmp_path):
    scenario = build_scenario()
    route(scenario, f"commits/{HEAD}/check-runs")["responses"] = [{"__fail__": "HTTP 502"}]
    result = run_guard(tmp_path, scenario)
    assert result.code == 1, (result.code, result.err)
    assert "ERROR: cannot read the check runs" in result.err


def test_the_guard_only_reads_and_merges(tmp_path):
    result = run_guard(tmp_path, build_scenario())
    assert result.code == 0, result.err
    writes = [c for c in result.calls
              if "-X" in c and c[c.index("-X") + 1] != "PUT"]
    assert writes == [], writes
    merges = [c for c in result.merge_calls]
    assert len(merges) == 1
