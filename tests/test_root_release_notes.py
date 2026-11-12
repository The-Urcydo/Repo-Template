"""GitHub builds release notes from merged pull requests using .github/release.yml. Reads one file."""
from __future__ import annotations

from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[1] / ".github" / "release.yml"


def test_release_notes_config_puts_breaking_changes_first_and_drops_nothing_else():
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["changelog"]
    cats = cfg["categories"]
    assert cats[0]["labels"] == ["breaking"], "a release that moves files must say so before anything else"
    assert cats[-1]["labels"] == ["*"], "the last category catches every unlabeled pull request"
    assert all(c["title"] and c["labels"] for c in cats)
    assert set(cfg["exclude"]) <= {"labels", "authors"}
    assert "ignore-for-release" in cfg["exclude"]["labels"]
