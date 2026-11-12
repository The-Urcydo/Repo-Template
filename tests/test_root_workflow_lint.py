"""This repo lints its own workflows the way the template ships to projects, and Dependabot waits a week.
Reads three files; runs in well under a second."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "workflow-lint.yml"


def test_dependabot_waits_a_week_for_every_ecosystem():
    data = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    for entry in data["updates"]:
        assert entry["cooldown"]["default-days"] >= 7, entry["package-ecosystem"]


def test_workflow_lint_runs_both_linters_pinned_and_with_least_privilege():
    text = WORKFLOW.read_text(encoding="utf-8")
    wf = yaml.safe_load(text)
    triggers = wf.get("on", wf.get(True))
    assert {"push", "pull_request"} <= set(triggers)
    assert wf["permissions"] == {"contents": "read"}
    (job,) = wf["jobs"].values()
    assert 0 < job["timeout-minutes"] <= 15
    assert set(job.get("permissions", {}).values()) <= {"read"}
    uses = [s["uses"] for s in job["steps"] if "uses" in s]
    assert uses and all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", u) for u in uses), uses
    assert any(u.startswith("zizmorcore/zizmor-action@") for u in uses)
    assert re.search(r"^\s*sha256=[0-9a-f]{64}\s*$", text, re.M) and "sha256sum -c" in text
    assert re.search(r"^\s*version=\d+\.\d+\.\d+\s*$", text, re.M)
    assert all(s.get("with", {}).get("persist-credentials") is False for s in job["steps"]
               if str(s.get("uses", "")).startswith("actions/checkout@"))
