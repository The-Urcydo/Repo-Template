"""One source of truth for the supported Python versions: the CI matrix.

The oldest ``python-version`` in ``.github/workflows/test.yml`` is the floor. This file checks that
the places that state that floor agree with it: the README badge, the README Quick start line, the
README Tooling table row, the ``## Supported Python versions`` section of CONTRIBUTING.md, and every
``actions/setup-python`` step in the workflow that ships to generated projects.

Versions are compared numerically as ``(major, minor)``: ``3.10 > 3.6``. A lexical comparison would
put ``3.10`` below ``3.6`` and quietly pick the wrong floor.

Python 3.12 compatible.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

CI = ".github/workflows/test.yml"
SHIPPED_CI = "template/.github/workflows/check.yml"
README = "README.md"
CONTRIBUTING = "CONTRIBUTING.md"

VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)(?:\.\d+)?$")


def version_tuple(raw: object, where: str) -> tuple[int, int]:
    """``"3.12"`` -> ``(3, 12)``. Anything that is not a quoted string of this shape fails loudly."""
    if not isinstance(raw, str):
        pytest.fail(
            f"{where}: python-version {raw!r} must be a quoted string; "
            "YAML reads an unquoted 3.10 as the number 3.1"
        )
    match = VERSION_RE.match(raw)
    if match is None:
        pytest.fail(f"{where}: python-version {raw!r} is not a major.minor version")
    return int(match.group("major")), int(match.group("minor"))


def load_yaml(rel: str) -> dict:
    try:
        data = yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        pytest.fail(f"{rel} cannot be read as YAML: {exc}")
    assert isinstance(data, dict), f"{rel} is not a YAML mapping"
    return data


def matrix_versions(rel: str) -> list[str]:
    """Every ``python-version`` in every job matrix, from ``include`` entries and a plain list."""
    jobs = load_yaml(rel).get("jobs")
    assert isinstance(jobs, dict), f"{rel} has no jobs"
    versions = []
    for job in jobs.values():
        matrix = ((job or {}).get("strategy") or {}).get("matrix") or {}
        for entry in matrix.get("include") or []:
            if isinstance(entry, dict) and "python-version" in entry:
                versions.append(entry["python-version"])
        plain = matrix.get("python-version")
        if plain is not None:
            versions.extend(plain if isinstance(plain, list) else [plain])
    assert versions, f"{rel} has no matrix python-version; the floor cannot be derived"
    return versions


def floor_version() -> tuple[int, int]:
    versions = matrix_versions(CI)
    return min(version_tuple(raw, CI) for raw in versions)


def section(rel: str, heading: str) -> str:
    """The text between ``## <heading>`` and the next level-two heading."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    start = text.find(f"## {heading}\n")
    assert start != -1, f"{rel} has no '## {heading}' section"
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def readme_line(fragment: str) -> str:
    lines = [line for line in (ROOT / README).read_text(encoding="utf-8").splitlines() if fragment in line]
    assert len(lines) == 1, f"{README}: expected exactly one line containing {fragment!r}, found {len(lines)}"
    return lines[0]


def setup_python_versions(rel: str) -> list[tuple[int, int]]:
    """The literal ``with.python-version`` of every ``actions/setup-python`` step."""
    jobs = load_yaml(rel).get("jobs")
    assert isinstance(jobs, dict), f"{rel} has no jobs"
    found = []
    for job in jobs.values():
        for step in (job or {}).get("steps") or []:
            uses = step.get("uses")
            if not isinstance(uses, str) or uses.split("@", 1)[0] != "actions/setup-python":
                continue
            raw = (step.get("with") or {}).get("python-version")
            assert raw is not None, f"{rel}: an actions/setup-python step has no with.python-version"
            found.append(version_tuple(raw, rel))
    assert found, f"{rel} has no actions/setup-python step; the shipped workflow cannot be checked"
    return found


def test_version_tuple_orders_numerically():
    assert version_tuple("3.10", "test") > version_tuple("3.6", "test")
    assert version_tuple("3.13", "test") > version_tuple("3.12", "test")


def test_readme_states_the_floor():
    floor = floor_version()
    shown = f"{floor[0]}.{floor[1]}"

    badge = readme_line("img.shields.io/badge/python-")
    assert f"Python {shown}+" in badge, f"{README} badge must say 'Python {shown}+': {badge!r}"
    assert f"python-{shown}%2B" in badge, f"{README} badge must link 'python-{shown}%2B': {badge!r}"

    quick_start = section(README, "Quick start")
    requires = [line for line in quick_start.splitlines() if line.startswith("**Requires** Python")]
    assert len(requires) == 1, f"{README} Quick start must have exactly one '**Requires** Python' line"
    assert f"**Requires** Python {shown}+" in requires[0], (
        f"{README} Quick start must say '**Requires** Python {shown}+': {requires[0]!r}"
    )

    tooling = readme_line("| Tooling |")
    assert f"Standard-library Python ({shown}+)" in tooling, (
        f"{README} Tooling row must say 'Standard-library Python ({shown}+)': {tooling!r}"
    )


def test_contributing_states_the_floor():
    floor = floor_version()
    shown = f"{floor[0]}.{floor[1]}"
    text = section(CONTRIBUTING, "Supported Python versions")
    assert f"the floor today is {shown}" in text, (
        f"{CONTRIBUTING} '## Supported Python versions' must name the floor {shown}"
    )


def test_shipped_workflow_is_at_least_the_floor():
    floor = floor_version()
    versions = setup_python_versions(SHIPPED_CI)
    below = [v for v in versions if v < floor]
    assert not below, (
        f"{SHIPPED_CI} runs actions/setup-python with {below}, below the floor "
        f"{floor[0]}.{floor[1]} derived from {CI}"
    )
