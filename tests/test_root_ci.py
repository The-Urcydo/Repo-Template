"""The root CI must give the tests what they need. Reads one workflow file; runs in well under a second."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_root_ci_fetches_full_history_and_tags_so_the_upgrade_test_can_run():
    """tests/test_template.py generates a project at the previous release tag with `git archive <tag>`. On a shallow
    checkout the tag is missing and that test skips, so the upgrade path would go untested without anyone noticing."""
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8"))
    checkouts = [step for job in wf["jobs"].values() for step in job["steps"]
                 if str(step.get("uses", "")).startswith("actions/checkout@")]
    assert checkouts, "test.yml has no checkout step"
    for step in checkouts:
        assert step.get("with", {}).get("fetch-depth") == 0, "checkout needs fetch-depth: 0 (all history and tags)"
