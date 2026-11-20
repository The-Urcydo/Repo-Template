"""Drift test for the governance lists that are kept in step by hand.

Several files repeat the same facts: who the owners are, which paths are protected, and which CI
checks the ruleset requires. If one is edited and the others are forgotten, nothing fails today.
This file reads them and fails when they disagree. It runs in well under a second:

Lists compared (derived from the files, never hard-coded here):
  accounts        .github/CODEOWNERS only; AGENTS.md rule 1 must not copy a handle
  protected paths the path lines of CODEOWNERS, AGENTS.md rule 3
  path kinds      a CODEOWNERS line ending in / must name a directory, and one without must name a file
  CI check names  .github/workflows/test.yml and the constants below

The ruleset itself lives in GitHub, not in this repo, so it cannot be read here. The constants
below record the names it requires.

Every check is a function that takes a repo root and returns a list of problems, so the same
checks run on the real repo and on mutated copies (see the last tests). Python 3.12 compatible.
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
CI = ".github/workflows/test.yml"
RULES = "AGENTS.md"
ADR_0011 = "docs/decisions/0011-delegate-merges-under-a-guard.md"
DECISIONS = "docs/maintainers/decisions.md"
RUNBOOK = "docs/maintainers/runbook.md"
GUARD_SCRIPT = ".github/scripts/merge_guarded.sh"
GOVERNANCE_FILES = [CODEOWNERS, CI, RULES, ADR_0011, DECISIONS, RUNBOOK, GUARD_SCRIPT]
END_DATE = "2027-02-17"

# The ruleset `protect-main` requires `ci-gate`; this set must track test.yml. If a check below fails
# because the job names changed, change the ruleset (GitHub settings) first or together with the workflow.
EXPECTED_CI_CHECKS = {"template (3.12)", "template (3.14)", "template (3.15)", "ci-gate"}

VERSION_PLACEHOLDER = "${{ matrix.python-version }}"
# Every problem that means "a file could not be read or understood" starts with this, as opposed to "two
# files disagree" (see `check`). The mutation tests assert no problem starts with it, so a mutation cannot
# pass by breaking a file, whatever the wording of the message.
FILE_PROBLEM = "file problem, not drift: "


class GovernanceError(Exception):
    """A governance file is missing or has a shape this test does not understand."""


def check(fn):
    """Turn a GovernanceError into a problem starting with FILE_PROBLEM, so an unreadable file fails the
    check loudly and can be told apart from two files that disagree."""
    @functools.wraps(fn)
    def wrapper(root: Path) -> list[str]:
        try:
            return fn(root)
        except GovernanceError as exc:
            return [FILE_PROBLEM + str(exc)]
    return wrapper


# --- readers -----------------------------------------------------------------------------------

def read(root: Path, rel: str) -> str:
    try:
        return (root / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
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
        line = raw.split("#", 1)[0].strip()  # GitHub allows a trailing comment: it is not an owner
        if not line:
            continue
        pattern, *owners = line.split()
        if not owners:
            # GitHub reads a pattern with no owner as "nobody owns this", which would lift the review requirement.
            raise GovernanceError(f"{CODEOWNERS}: the line for {pattern} has no owners, so it requires no review")
        entries.append((pattern, {o.lstrip("@").lower() for o in owners}))
    if not entries:
        raise GovernanceError(f"{CODEOWNERS} has no pattern lines")
    return entries


def codeowners_owners(root: Path) -> set[str]:
    owners = set().union(*(owners for _, owners in parse_codeowners(root)))
    if not owners:
        raise GovernanceError(f"{CODEOWNERS} names no owners, so no review could ever be required")
    return owners


def protected_paths(root: Path) -> set[str]:
    """The path lines of CODEOWNERS in the form AGENTS.md rule 3 writes them: no leading slash."""
    return {pattern.strip("/") for pattern, _ in parse_codeowners(root) if pattern != "*"}


def rule_list_line(root: Path, number: int) -> str:
    """The first line of hard rule `number`: where the rule lists its paths or handles. Its sub-bullets
    may name a path again in passing and must not stand in for the list."""
    return rule_block(root, number).splitlines()[0]


def excerpt(line: str, width: int = 110) -> str:
    """The line itself when it is short, else its start and its end, so a message shows where it stops."""
    return line if len(line) <= width else f"{line[:width // 2]} ... {line[-(width // 2):]}"


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
def check_codeowners_lines_share_one_owner_set(root: Path) -> list[str]:  # a
    entries = parse_codeowners(root)
    catch_all = [owners for pattern, owners in entries if pattern == "*"]
    if len(catch_all) != 1:
        return [f"{CODEOWNERS} needs exactly one '*' catch-all line, found {len(catch_all)}"]
    return [f"{CODEOWNERS}: the line for {pattern} has owners {sorted(owners)} but the '*' line has {sorted(catch_all[0])}"
            for pattern, owners in entries if pattern != "*" and owners != catch_all[0]]


@check
def check_rule_3_lists_the_protected_paths(root: Path) -> list[str]:  # b
    from_codeowners = protected_paths(root)
    line = rule_list_line(root, 3)
    from_rule = names_in_rule(line)
    problems = []
    if from_codeowners - from_rule:
        problems.append(f"{CODEOWNERS} has lines for {sorted(from_codeowners - from_rule)} but the first line of "
                        f"{RULES} rule 3 does not name them (as backticked paths, or 'this file' for {RULES})")
    if from_rule - from_codeowners:
        problems.append(f"the first line of {RULES} rule 3 names {sorted(from_rule - from_codeowners)} but "
                        f"{CODEOWNERS} has no line for them")
    if problems:
        problems.append(f"the list line is {excerpt(line)!r}; keep the list on that one line and do not wrap it")
    return problems


@check
def check_codeowners_path_kinds(root: Path) -> list[str]:  # c
    """GitHub reads a trailing slash as "directories only". A file written with one protects nothing."""
    problems = []
    for pattern, _ in parse_codeowners(root):
        if pattern == "*":
            continue
        plain = pattern.strip("/")
        path = root / plain
        if not path.exists():  # a mutated copy holds only the governance files
            continue
        written_as_dir = pattern.endswith("/")
        if path.is_dir() != written_as_dir:
            advice = ("A trailing slash matches directories only, so this line would protect nothing"
                      if written_as_dir else "Write the directory with a trailing slash, as GitHub documents")
            problems.append(
                f"{CODEOWNERS}: the line for {pattern} writes {plain} as a "
                f"{'directory' if written_as_dir else 'file'}, but it is a "
                f"{'file' if written_as_dir else 'directory'} in the repo. {advice}.")
    return problems


@check
def check_rule_1_does_not_name_accounts(root: Path) -> list[str]:  # d
    text = rule_block(root, 1)
    leaked = sorted(owner for owner in codeowners_owners(root)
                    if re.search(rf"(?<![\w-])@?{re.escape(owner)}(?![\w-])", text, re.IGNORECASE))
    if not leaked:
        return []
    return [f"{RULES} rule 1 names the account(s) {leaked}; the rules must not pin an account, because "
            f"who the owner is lives in the organization context. {CODEOWNERS} is the list of record."]


@check
def check_ci_job_names_match_the_ruleset(root: Path) -> list[str]:  # e
    names = ci_check_names(root)
    if names == EXPECTED_CI_CHECKS:
        return []
    return [f"{CI} produces the check names {sorted(names)} but the ruleset requires {sorted(EXPECTED_CI_CHECKS)} "
            "(EXPECTED_CI_CHECKS in tests/test_repo_governance.py): change the ruleset in GitHub, then this constant"]


@check
def check_delegation_end_date(root: Path) -> list[str]:  # f
    """The delegation has one absolute end date; the ADR, the decisions file, the runbook and the
    guard's END_DATE constant must all state it, so no stale '90 days' or 'if merged on' can survive."""
    ends = re.compile(r"\bends\s+(?:on\s+)?(\d{4}-\d{2}-\d{2})|\bend date\s*\(?(\d{4}-\d{2}-\d{2})")
    problems = []
    for rel in (ADR_0011, DECISIONS, RUNBOOK):
        text = read(root, rel)
        dates = {m.group(1) or m.group(2) for m in ends.finditer(text)}
        if END_DATE not in dates:
            problems.append(f"{rel} does not state the delegation end date {END_DATE} "
                            f"(found {sorted(dates) or 'none'})")
        others = sorted(dates - {END_DATE})
        if others:
            problems.append(f"{rel} states another end date {others}; the delegation ends on {END_DATE}")
        for stale in ("if merged on", "90 days", "90-day"):
            if re.search(re.escape(stale), text, re.IGNORECASE):
                problems.append(f"{rel} still contains {stale!r}; the end date is absolute ({END_DATE})")
    script = read(root, GUARD_SCRIPT)
    constants = set(re.findall(r'^END_DATE="(\d{4}-\d{2}-\d{2})"$', script, re.MULTILINE))
    if constants != {END_DATE}:
        problems.append(f"{GUARD_SCRIPT} must pin END_DATE=\"{END_DATE}\", found {sorted(constants) or 'none'}")
    return problems


CHECKS = {
    "a_codeowners_lines": check_codeowners_lines_share_one_owner_set,
    "b_rule_3_paths": check_rule_3_lists_the_protected_paths,
    "c_codeowners_path_kinds": check_codeowners_path_kinds,
    "d_rule_1_accounts": check_rule_1_does_not_name_accounts,
    "e_ci_job_names": check_ci_job_names_match_the_ruleset,
    "f_delegation_end_date": check_delegation_end_date,
}


# --- the real repo -------------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(CHECKS))
def test_governance_lists_agree(name):
    problems = CHECKS[name](ROOT)
    assert not problems, "\n".join(problems)


# --- the helpers themselves ----------------------------------------------------------------------

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


def drop_an_owner_on_one_codeowners_line(root: Path) -> None:
    for raw in (root / CODEOWNERS).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and not line.startswith("*"):
            replace_once(root, CODEOWNERS, raw, " ".join(line.split()[:-1]))
            return
    pytest.fail("no non-catch-all CODEOWNERS line to mutate")


def add_a_path_to_codeowners(root: Path) -> None:
    owners = " ".join("@" + o for o in sorted(codeowners_owners(root)))
    with (root / CODEOWNERS).open("a", encoding="utf-8") as fh:
        fh.write(f"/docs/maintainers/runbook.md {owners}\n")


def unbacktick_a_path_in_rule_3(root: Path) -> None:
    first = rule_list_line(root, 3)
    protected = protected_paths(root)
    victim = next(t for t in sorted(backticked(first)) if t.strip("/") in protected)
    # Only the list line. A sub-bullet may name the same path again (`.github/CODEOWNERS` is), and that
    # must not rescue a path that dropped out of the list.
    replace_once(root, RULES, first, first.replace(f"`{victim}`", victim, 1))


def drop_the_end_date(root: Path, rel: str) -> None:
    """Remove every end date in `rel`, so the presence branch (not the another-date branch) must fire."""
    text = (root / rel).read_text(encoding="utf-8")
    if END_DATE not in text:
        pytest.fail(f"mutation target {END_DATE!r} not found in {rel}: the file changed, update this mutation")
    (root / rel).write_text(text.replace(END_DATE, "soon"), encoding="utf-8")


def add_a_path_to_rule_3(root: Path) -> None:
    first = rule_list_line(root, 3)
    replace_once(root, RULES, first, first.replace("`template/agents/`", "`template/agents/`, `docs/maintainers/runbook.md`", 1))


def write_a_file_as_a_directory_in_codeowners(root: Path) -> None:
    replace_once(root, CODEOWNERS, "/AGENTS.md ", "/AGENTS.md/ ")


def name_an_account_in_rule_1(root: Path) -> None:
    block = rule_block(root, 1)
    handle = sorted(codeowners_owners(root))[0]
    replace_once(root, RULES, block,
                 block.replace("An unattended session never approves.",
                               f"An unattended session never approves; {handle} is exempt.", 1))


MUTATIONS = {
    "one_codeowners_line_loses_an_owner": (drop_an_owner_on_one_codeowners_line, "a_codeowners_lines"),
    "codeowners_gains_a_path": (add_a_path_to_codeowners, "b_rule_3_paths"),
    "rule_3_loses_a_path": (unbacktick_a_path_in_rule_3, "b_rule_3_paths"),
    "rule_3_gains_a_path": (add_a_path_to_rule_3, "b_rule_3_paths"),
    "codeowners_writes_a_file_as_a_directory": (write_a_file_as_a_directory_in_codeowners, "c_codeowners_path_kinds"),
    "rule_1_names_an_account": (name_an_account_in_rule_1, "d_rule_1_accounts"),
    "ci_matrix_version_changes": (
        lambda r: replace_once(r, CI, 'python-version: "3.14"', 'python-version: "3.13"'), "e_ci_job_names"),
    "delegation_end_date_moves": (
        lambda r: replace_once(r, ADR_0011, END_DATE, "2027-02-16"), "f_delegation_end_date"),
    "delegation_end_date_moves_in_decisions": (
        lambda r: replace_once(r, DECISIONS, END_DATE, "2027-02-16"), "f_delegation_end_date"),
    "delegation_end_date_removed_from_adr": (
        lambda r: drop_the_end_date(r, ADR_0011), "f_delegation_end_date"),
    "delegation_end_date_removed_from_decisions": (
        lambda r: drop_the_end_date(r, DECISIONS), "f_delegation_end_date"),
    "delegation_end_date_moves_in_script": (
        lambda r: replace_once(r, GUARD_SCRIPT, f'END_DATE="{END_DATE}"', 'END_DATE="2027-02-16"'),
        "f_delegation_end_date"),
    "delegation_end_date_moves_in_runbook": (
        lambda r: replace_once(r, RUNBOOK, END_DATE, "2027-02-16"), "f_delegation_end_date"),
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
    broken = [p for problems in failing.values() for p in problems if p.startswith(FILE_PROBLEM)]
    assert not broken, f"mutation {mutation!r} broke a file instead of making two files disagree: {broken}"


# --- loud failures: a file that is missing, unreadable or empty must fail, never be skipped ---------

def all_problems(root: Path) -> list[str]:
    return [p for fn in CHECKS.values() for p in fn(root)]


@pytest.mark.parametrize("rel, content, expected", [
    (CODEOWNERS, None, "cannot be read"),
    (CI, None, "cannot be read"),
    (RULES, None, "cannot be read"),
    (RULES, b"\xff\xfe\x00", "cannot be read"),
    (CI, "jobs: [unclosed", "not valid YAML"),
    (CI, "", "is not a YAML mapping"),
    (CODEOWNERS, "# only a comment\n", "no pattern lines"),
    (RULES, "# no rules here\n", "no '## Hard rules'"),
    (RULES, "## Hard rules\n1. a\n2. b\n", "no rule 3 under"),
    (RULES, "## Hard rules\n1. a\n2. b\n3. c\n", "no rule 4 after rule 3"),
    (CI, "jobs:\n  t:\n    name: t (${{ matrix.python-version }})\n", "has no matrix python-version"),
])
def test_a_missing_or_unreadable_file_fails_loudly(tmp_path, rel, content, expected):
    root = copy_governance_files(tmp_path)
    target = root / rel
    if content is None:
        target.unlink()
    elif isinstance(content, bytes):
        target.write_bytes(content)
    else:
        target.write_text(content, encoding="utf-8")
    hits = [p for p in all_problems(root) if expected in p]
    assert hits, f"expected a problem containing {expected!r}, got: {all_problems(root)}"
    assert all(rel in p for p in hits), hits
    assert all(p.startswith(FILE_PROBLEM) for p in hits), hits  # a broken file is never reported as drift


# --- the vacuous direction: no owners anywhere must fail, not pass as an empty set equal to an empty set

def test_codeowners_lines_with_no_owners_fail(tmp_path):
    root = copy_governance_files(tmp_path)
    lines = (root / CODEOWNERS).read_text(encoding="utf-8").splitlines()
    stripped = [l if not l.strip() or l.lstrip().startswith("#") else l.split()[0] for l in lines]
    (root / CODEOWNERS).write_text("\n".join(stripped) + "\n", encoding="utf-8")
    assert any("has no owners" in p for p in check_codeowners_lines_share_one_owner_set(root))


# --- things that are valid and must not be reported as drift ------------------------------------

def test_a_trailing_comment_on_a_codeowners_line_is_not_an_owner(tmp_path):
    root = copy_governance_files(tmp_path)
    lines = (root / CODEOWNERS).read_text(encoding="utf-8").splitlines()
    lines = [l + "  # harness file" if l.startswith("/CLAUDE.md") else l for l in lines]
    (root / CODEOWNERS).write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert any(l.endswith("# harness file") for l in lines), "the test did not edit the CLAUDE.md line"
    assert check_codeowners_lines_share_one_owner_set(root) == []
    assert check_rule_3_lists_the_protected_paths(root) == []


def test_rule_1_must_not_name_an_account(tmp_path):
    root = copy_governance_files(tmp_path)
    name_an_account_in_rule_1(root)
    assert any("names the account(s)" in p for p in check_rule_1_does_not_name_accounts(root))


@pytest.mark.parametrize("rel", [ADR_0011, DECISIONS])
@pytest.mark.parametrize("stale", ["if merged on", "90 days", "90-day"])
def test_the_end_date_check_refuses_stale_relative_wording(tmp_path, rel, stale):
    root = copy_governance_files(tmp_path)
    with (root / rel).open("a", encoding="utf-8") as fh:
        fh.write(f"\nThe delegation lasts {stale}.\n")
    assert any(stale in p for p in check_delegation_end_date(root))


def test_the_merge_guard_is_a_protected_path():
    assert GUARD_SCRIPT in protected_paths(ROOT)
    assert GUARD_SCRIPT in names_in_rule(rule_list_line(ROOT, 3))


def test_a_codeowners_line_must_match_the_file_or_directory_on_disk(tmp_path):
    root = copy_governance_files(tmp_path)
    (root / "template" / "agents").mkdir(parents=True)
    replace_once(root, CODEOWNERS, "/template/agents/", "/template/agents")
    assert any("writes template/agents as a file" in p for p in check_codeowners_path_kinds(root))
    replace_once(root, CODEOWNERS, "/AGENTS.md ", "/AGENTS.md/ ")
    assert any("writes AGENTS.md as a directory" in p for p in check_codeowners_path_kinds(root))
