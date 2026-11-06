"""Drift test for the governance lists that are kept in step by hand.

Several files repeat the same facts: who the owners are, which paths are protected, and which CI
checks the ruleset requires. If one is edited and the others are forgotten, nothing fails today.
This file reads them and fails when they disagree. It reads five files and runs in well under a
second:  python -m pytest tests/test_repo_governance.py -q

Lists compared (derived from the files, never hard-coded here, so the test is correct before and
after the CI files join the protected set):
  owners          .github/CODEOWNERS, OWNERS in .github/workflows/owner-approval.yml, AGENTS.md rule 1
  protected paths the protected='^(...)$' regex in the workflow, the path lines of CODEOWNERS,
                  AGENTS.md rule 3
  CI check names  .github/workflows/test.yml, owner-approval/review, and the constants below

The ruleset itself lives in GitHub, not in this repo, so it cannot be read here. The constants
below record the names it requires.

Every check is a function that takes a repo root and returns a list of problems, so the same
checks run on the real repo and on mutated copies (see the last tests). Python 3.9 compatible.
"""
from __future__ import annotations

import functools
import re
import shutil
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

CODEOWNERS = ".github/CODEOWNERS"
GUARD = ".github/workflows/owner-approval.yml"
CI = ".github/workflows/test.yml"
RULES = "AGENTS.md"
GOVERNANCE_FILES = [CODEOWNERS, GUARD, CI, RULES]

# The ruleset `protect-main` requires these three check names. If a check below fails because the
# job names changed, change the ruleset (GitHub settings) first or together with the workflow.
EXPECTED_CI_CHECKS = {"template (3.9)", "template (3.13)"}
STATUS_CONTEXT = "owner-approval/review"

VERSION_PLACEHOLDER = "${{ matrix.python-version }}"
PROTECTED_LINE = re.compile(r"protected='\^\((?P<body>[^']*)\)\$'")
ESCAPED_PATH = re.compile(r"(?:[A-Za-z0-9_/-]|\\\.)+")


class GovernanceError(Exception):
    """A governance file is missing or has a shape this test does not understand."""


def check(fn):
    """Turn a GovernanceError into a problem, so an unreadable file fails the check loudly."""
    @functools.wraps(fn)
    def wrapper(root: Path) -> list[str]:
        try:
            return fn(root)
        except GovernanceError as exc:
            return [str(exc)]
    return wrapper


# --- readers -----------------------------------------------------------------------------------

def read(root: Path, rel: str) -> str:
    try:
        return (root / rel).read_text(encoding="utf-8")
    except OSError as exc:
        raise GovernanceError(f"{rel} cannot be read: {exc}") from exc


def load_yaml(root: Path, rel: str) -> dict:
    try:
        data = yaml.safe_load(read(root, rel))
    except yaml.YAMLError as exc:
        raise GovernanceError(f"{rel} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise GovernanceError(f"{rel} is not a YAML mapping")
    return data


def parse_codeowners(root: Path) -> list[tuple[str, set[str]]]:
    """(pattern, owner handles lower-cased without @) for every pattern line."""
    entries = []
    for raw in read(root, CODEOWNERS).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pattern, *owners = line.split()
        entries.append((pattern, {o.lstrip("@").lower() for o in owners}))
    if not entries:
        raise GovernanceError(f"{CODEOWNERS} has no pattern lines")
    return entries


def guard_step(root: Path) -> dict:
    """The one step of the guard workflow that has a run block and an OWNERS variable."""
    jobs = load_yaml(root, GUARD).get("jobs")
    if not isinstance(jobs, dict):
        raise GovernanceError(f"{GUARD} has no jobs")
    found = []
    for job in jobs.values():
        for step in (job or {}).get("steps") or []:
            if "run" in step and "OWNERS" in (step.get("env") or {}):
                found.append(step)
    if len(found) != 1:
        raise GovernanceError(f"{GUARD}: expected exactly one step with a run block and env OWNERS, found {len(found)}")
    return found[0]


def guard_owners(root: Path) -> set[str]:
    return {h.lower() for h in str(guard_step(root)["env"]["OWNERS"]).split()}


def guard_regex_entries(root: Path) -> list[str]:
    run = str(guard_step(root)["run"])
    found = PROTECTED_LINE.findall(run)
    if len(found) != 1:
        raise GovernanceError(f"{GUARD}: expected exactly one protected='^(...)$' line in the run block, found {len(found)}")
    return found[0].split("|")


def to_codeowners_form(entry: str) -> str:
    """Map one regex entry to the path CODEOWNERS uses for it, or fail loudly.

    `template/agents/.*` -> `/template/agents/`, `AGENTS\\.md` -> `/AGENTS.md`. Anything else (another
    backslash, a group, a bracket, an unescaped dot, a `.*` that does not follow a slash) is refused,
    so a new kind of pattern can never pass unnoticed.
    """
    path = entry
    if entry.endswith(".*"):
        path = entry[:-2]
        if not path.endswith("/"):
            raise GovernanceError(f"{GUARD}: the regex entry {entry!r} ends in .* but not after a slash; "
                                  "extend to_codeowners_form in tests/test_repo_governance.py")
    if not ESCAPED_PATH.fullmatch(path):
        raise GovernanceError(f"{GUARD}: cannot map the regex entry {entry!r} to a CODEOWNERS path; "
                              "extend to_codeowners_form in tests/test_repo_governance.py")
    return "/" + path.replace("\\.", ".")


def rule_block(root: Path, number: int) -> str:
    """The text of hard rule `number` in AGENTS.md: its line plus its sub-bullets."""
    lines = read(root, RULES).splitlines()
    try:
        heading = next(i for i, line in enumerate(lines) if line.strip() == "## Hard rules")
    except StopIteration:
        raise GovernanceError(f"{RULES}: no '## Hard rules' heading found") from None
    start = next((i for i in range(heading + 1, len(lines)) if lines[i].startswith(f"{number}. ")), None)
    if start is None:
        raise GovernanceError(f"{RULES}: no rule {number} under '## Hard rules'")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith(f"{number + 1}. ")), None)
    if end is None:
        raise GovernanceError(f"{RULES}: no rule {number + 1} after rule {number}, so rule {number} has no end")
    return "\n".join(lines[start:end])


def backticked(text: str) -> set[str]:
    return {t.strip() for t in re.findall(r"`([^`]+)`", text)}


def names_in_rule(block: str) -> set[str]:
    """Backticked tokens, plus AGENTS.md when the rule says 'this file' (the rules file names itself so)."""
    names = {t.strip("/") for t in backticked(block)}
    if re.search(r"\bthis file\b", block, re.IGNORECASE):
        names.add(RULES)
    return names


def ci_check_names(root: Path) -> set[str]:
    """The check names test.yml produces: each job name with every matrix python-version filled in."""
    jobs = load_yaml(root, CI).get("jobs")
    if not isinstance(jobs, dict):
        raise GovernanceError(f"{CI} has no jobs")
    names = set()
    for key, job in jobs.items():
        job = job or {}
        template = str(job.get("name", key))
        matrix = (job.get("strategy") or {}).get("matrix") or {}
        versions = [e["python-version"] for e in matrix.get("include") or []
                    if isinstance(e, dict) and "python-version" in e]
        plain = matrix.get("python-version")
        if plain is not None:
            versions += plain if isinstance(plain, list) else [plain]
        unquoted = [v for v in versions if not isinstance(v, str)]
        if unquoted:
            raise GovernanceError(f"{CI}: python-version {unquoted!r} must be a quoted string "
                                  "(YAML reads an unquoted 3.10 as the number 3.1)")
        if VERSION_PLACEHOLDER in template:
            if not versions:
                raise GovernanceError(f"{CI}: job {key!r} uses {VERSION_PLACEHOLDER} but has no matrix python-version")
            names.update(template.replace(VERSION_PLACEHOLDER, v) for v in versions)
        else:
            names.add(template)
    return names


# --- the checks: each returns a list of problems, empty when the files agree --------------------

@check
def check_owner_handles_agree(root: Path) -> list[str]:  # a
    listed = set().union(*(owners for _, owners in parse_codeowners(root)))
    guard = guard_owners(root)
    if listed == guard:
        return []
    return [f"{CODEOWNERS} names owners {sorted(listed)} but OWNERS in {GUARD} is {sorted(guard)} "
            f"(only in CODEOWNERS: {sorted(listed - guard)}; only in OWNERS: {sorted(guard - listed)})"]


@check
def check_codeowners_lines_share_one_owner_set(root: Path) -> list[str]:  # b
    entries = parse_codeowners(root)
    catch_all = [owners for pattern, owners in entries if pattern == "*"]
    if len(catch_all) != 1:
        return [f"{CODEOWNERS} needs exactly one '*' catch-all line, found {len(catch_all)}"]
    return [f"{CODEOWNERS}: the line for {pattern} has owners {sorted(owners)} but the '*' line has {sorted(catch_all[0])}"
            for pattern, owners in entries if pattern != "*" and owners != catch_all[0]]


@check
def check_protected_paths_agree(root: Path) -> list[str]:  # c
    from_guard = {to_codeowners_form(e) for e in guard_regex_entries(root)}
    from_codeowners = {pattern for pattern, _ in parse_codeowners(root) if pattern != "*"}
    problems = []
    if from_guard - from_codeowners:
        problems.append(f"{GUARD} protects {sorted(from_guard - from_codeowners)} but {CODEOWNERS} has no line for them")
    if from_codeowners - from_guard:
        problems.append(f"{CODEOWNERS} has lines for {sorted(from_codeowners - from_guard)} but the regex in {GUARD} "
                        "does not protect them")
    return problems


@check
def check_rule_3_names_every_protected_path(root: Path) -> list[str]:  # d
    protected = {to_codeowners_form(e) for e in guard_regex_entries(root)}
    protected |= {pattern for pattern, _ in parse_codeowners(root) if pattern != "*"}
    named = names_in_rule(rule_block(root, 3))
    missing = sorted(p for p in protected if p.strip("/") not in named)
    if not missing:
        return []
    return [f"{RULES} rule 3 does not name {missing} (as a backticked path, or 'this file' for {RULES}), "
            f"but {GUARD} or {CODEOWNERS} protects them"]


@check
def check_rule_1_names_every_owner(root: Path) -> list[str]:  # d
    named = {t.lower() for t in backticked(rule_block(root, 1))}
    missing = sorted(guard_owners(root) - named)
    if not missing:
        return []
    return [f"{RULES} rule 1 does not name the owners {missing} (as backticked handles), but OWNERS in {GUARD} lists them"]


@check
def check_ci_job_names_match_the_ruleset(root: Path) -> list[str]:  # e
    names = ci_check_names(root)
    if names == EXPECTED_CI_CHECKS:
        return []
    return [f"{CI} produces the check names {sorted(names)} but the ruleset requires {sorted(EXPECTED_CI_CHECKS)} "
            "(EXPECTED_CI_CHECKS in tests/test_repo_governance.py): change the ruleset in GitHub, then this constant"]


@check
def check_guard_posts_the_required_status(root: Path) -> list[str]:  # e
    needle = f'context="{STATUS_CONTEXT}"'
    if needle in str(guard_step(root)["run"]):
        return []
    return [f"{GUARD} does not post {needle}, but the ruleset requires the status {STATUS_CONTEXT!r}"]


CHECKS = {
    "a_owner_handles": check_owner_handles_agree,
    "b_codeowners_lines": check_codeowners_lines_share_one_owner_set,
    "c_protected_paths": check_protected_paths_agree,
    "d_rule_3_paths": check_rule_3_names_every_protected_path,
    "d_rule_1_handles": check_rule_1_names_every_owner,
    "e_ci_job_names": check_ci_job_names_match_the_ruleset,
    "e_status_context": check_guard_posts_the_required_status,
}


# --- the real repo -------------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(CHECKS))
def test_governance_lists_agree(name):
    problems = CHECKS[name](ROOT)
    assert not problems, "\n".join(problems)


# --- the helpers themselves ----------------------------------------------------------------------

@pytest.mark.parametrize("entry, expected", [
    ("AGENTS\\.md", "/AGENTS.md"),
    ("template/AGENTS\\.md\\.jinja", "/template/AGENTS.md.jinja"),
    ("template/agents/.*", "/template/agents/"),
    ("\\.github/workflows/.*", "/.github/workflows/"),
])
def test_regex_entries_map_to_codeowners_paths(entry, expected):
    assert to_codeowners_form(entry) == expected


@pytest.mark.parametrize("entry", ["foo.*", ".*", "", "a(b)", "x[y]", "AGENTS.md", "a|b", "a\\d"])
def test_unknown_regex_shapes_are_refused_not_guessed(entry):
    with pytest.raises(GovernanceError):
        to_codeowners_form(entry)


def test_this_file_in_a_rule_counts_for_the_rules_file():
    assert RULES in names_in_rule("3. Edits need approval: `template/agents/`, this file, `CLAUDE.md`.")
    assert RULES not in names_in_rule("3. Edits need approval: `template/agents/`, `CLAUDE.md`.")
    assert {"template/agents", "CLAUDE.md"} <= names_in_rule("3. `template/agents/` and `CLAUDE.md`")


# --- the checks catch drift: one mutation per check, applied to a temporary copy ------------------

def copy_governance_files(dest: Path) -> Path:
    for rel in GOVERNANCE_FILES:
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest / rel)
    return dest


def replace_once(root: Path, rel: str, old: str, new: str) -> None:
    text = (root / rel).read_text(encoding="utf-8")
    if old not in text:
        pytest.fail(f"mutation target {old!r} not found in {rel}: the file changed, update this mutation")
    (root / rel).write_text(text.replace(old, new, 1), encoding="utf-8")


def drop_last_owner_in_guard(root: Path) -> None:
    owners = str(guard_step(root)["env"]["OWNERS"])
    replace_once(root, GUARD, f"OWNERS: {owners}", "OWNERS: " + " ".join(owners.split()[:-1]))


def drop_an_owner_on_one_codeowners_line(root: Path) -> None:
    for raw in (root / CODEOWNERS).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and not line.startswith("*"):
            replace_once(root, CODEOWNERS, raw, " ".join(line.split()[:-1]))
            return
    pytest.fail("no non-catch-all CODEOWNERS line to mutate")


def drop_first_path_from_the_regex(root: Path) -> None:
    first = guard_regex_entries(root)[0]
    replace_once(root, GUARD, f"protected='^({first}|", "protected='^(")


def unbacktick_a_path_in_rule_3(root: Path) -> None:
    block = rule_block(root, 3)
    victim = next(t for t in sorted(backticked(block)) if "/" in t or t.endswith((".md", ".jinja")))
    # Every occurrence: a path can be named twice in the rule (the list and a sub-bullet).
    replace_once(root, RULES, block, block.replace(f"`{victim}`", victim))


def unbacktick_an_owner_in_rule_1(root: Path) -> None:
    block = rule_block(root, 1)
    handle = sorted(guard_owners(root))[0]
    new_block = re.sub(f"`{re.escape(handle)}`", handle, block, count=1, flags=re.IGNORECASE)
    replace_once(root, RULES, block, new_block)


MUTATIONS = {
    "guard_loses_an_owner": (drop_last_owner_in_guard, "a_owner_handles"),
    "one_codeowners_line_loses_an_owner": (drop_an_owner_on_one_codeowners_line, "b_codeowners_lines"),
    "regex_loses_a_path": (drop_first_path_from_the_regex, "c_protected_paths"),
    "rule_3_loses_a_path": (unbacktick_a_path_in_rule_3, "d_rule_3_paths"),
    "rule_1_loses_an_owner": (unbacktick_an_owner_in_rule_1, "d_rule_1_handles"),
    "ci_matrix_version_changes": (
        lambda r: replace_once(r, CI, 'python-version: "3.13"', 'python-version: "3.14"'), "e_ci_job_names"),
    "guard_posts_another_status": (
        lambda r: replace_once(r, GUARD, f'context="{STATUS_CONTEXT}"', 'context="owner-approval/reviewed"'),
        "e_status_context"),
}


def test_an_unmutated_copy_passes_every_check(tmp_path):
    root = copy_governance_files(tmp_path)
    assert {name: fn(root) for name, fn in CHECKS.items() if fn(root)} == {}


@pytest.mark.parametrize("mutation", list(MUTATIONS))
def test_each_check_fails_alone_on_its_own_kind_of_drift(tmp_path, mutation):
    edit, expected = MUTATIONS[mutation]
    root = copy_governance_files(tmp_path)
    edit(root)
    failing = {name: fn(root) for name, fn in CHECKS.items() if fn(root)}
    assert set(failing) == {expected}, f"mutation {mutation!r} should fail only {expected!r}, got: {failing}"
