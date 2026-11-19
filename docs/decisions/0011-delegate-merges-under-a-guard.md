---
title: Delegate merges to the orchestrator under a guard
type: decision
status: accepted
summary: The orchestrator may press merge without a per-PR chat go-ahead, but only through a guard that requires the owner's in-person approval of the latest commit; every other irreversible action stays with the owner.
date: 2026-11-18
decision_makers: human
supersedes: []
---
# 0011: Delegate merges to the orchestrator under a guard

## Context and problem statement

This repository has one human owner with four accounts, one per home machine. The organization
context (`The-Urcydo/.github/AGENTS.md`) and [ADR 0008 in
Agents-Skills-Roles-Oriented](https://github.com/The-Urcydo/Agents-Skills-Roles-Oriented/blob/main/docs/decisions/0008-single-owner-organization-access.md)
record that the accounts are the same human and that roles are defined by use, not by account name.

Three rules about merging conflict today:

1. The organization context says accounts driving unattended agent sessions **never approve and
   never merge**.
2. `AGENTS.md` rule 1 and `docs/maintainers/decisions.md` say an agent merges only after the owner's
   approval **and** the owner has said in the session that the PR may merge.
3. The orchestrator brief used for this repository (2026-11-18) says the orchestrator creates
   branches, opens PRs, runs independent reviews and **presses merge through a guard** after the
   owner's in-person approval, without asking again per PR.

The second rule adds a chat round-trip after the approval that checks nothing the guard cannot
check: the approval, the reviewed head, the file list, `mergeable_state` and the checks. The first
rule is an organization default; the organization file itself says a repository's rules win for that
repository, and to raise the conflict rather than guess. Which merge rule applies to this repository?

## Decision drivers

- The owner is the only approver; an unattended session must never be able to approve.
- A merge must be pinned to the commit the owner approved, so a later push cannot ride on it.
- The merge should be auditable from the history alone.
- Routine merges should not need a second confirmation after the approval.
- Irreversible actions outside a routine PR merge stay with the owner.

## Considered options

- Keep the per-PR chat go-ahead; the owner presses every merge.
- Let the orchestrator merge whenever the owner has approved on GitHub.
- Let the orchestrator merge only when a guard proves the approval, head, files, mergeability and
  checks, and record the delegation in the merge commit.

## Decision outcome

Chosen option: "Merge only through a guard", because it removes the redundant chat round-trip while
keeping the owner as the only approver and making every delegated merge checkable and auditable.

### Phase 1: delegated merges

The orchestrator may, without asking per PR:

- create branches, commit and open pull requests;
- run independent reviews and the repository's checks;
- prepare the review pack for the owner;
- press merge, using a merge commit pinned to the reviewed head, **only after the guard passes**.

Every PR, harness paths included, still needs the owner's **in-person approving review of its latest
commit**. Agents never approve. A push after the approval makes it stale; the PR needs a new approval.

The guard is `.github/scripts/merge_guarded.sh`. It enforces, in this order, and refuses with a reason
if any fails:

1. the PR is open, not a draft, and its head is a branch of this repository (a fork is out of scope);
2. its base is `main`;
3. its head is the reviewed commit;
4. its changed-file list equals the reviewed list, has no file name containing a newline or carriage
   return (a line-per-file list cannot represent one), and has fewer than 3000 entries (GitHub
   truncates the list there, so a longer one cannot be verified);
5. at least one `CODEOWNERS` login's latest decisive review (approval, change request or dismissal) is
   an APPROVED review of exactly that head, and no `CODEOWNERS` login's latest decisive review is a
   change request (whatever commit it names); a later comment does not cancel an approval, as on
   GitHub itself; the guard also refuses if that approving login is the credential running it
   (compared case-insensitively), except that a GitHub App token whose user lookup returns
   `Resource not accessible by integration` is allowed through because it has no user login;
6. `mergeable_state` is `clean` (polled while it reads `unknown` or null);
7. the latest run of every check is completed with `success`, `neutral` or `skipped`.

Only then does it merge with `merge_method=merge`, `sha=<head>` and a commit message ending
`Delegated-under: ADR-0011`. Afterwards it verifies that the merge commit has two parents, that the
branch was deleted, and that `ci-gate` on `main` succeeded.

### Reserved to the owner at all times

The owner keeps, and no delegation covers: rulesets and repository or organization settings; tags and
releases; `.github/CODEOWNERS`; this ADR and any access ADR; secrets, tokens and GitHub Apps; billing;
changing repository visibility; choosing a licence for a repository; deleting repositories; and
anything irreversible.

### Phase 2 gate

Approval by an unattended account is **not** granted. It needs a new owner-approved PR, and this ADR
must state its evidence criteria first. Proposed criteria for the owner to edit:

- at least 10 PRs merged under Phase 1 with no violation of this ADR or the repository rules;
- a seeded-defect trial in which an independent reviewer catches every planted defect across at
  least 5 PRs.

### Term and revocation

The delegation ends on 2027-02-17. A new PR can renew it. After that date, the guard refuses a
delegated merge and the owner merges. The owner can audit the end date from this ADR and the merge
history.

The owner revokes it by reverting or superseding this ADR. In an emergency he toggles the ruleset in
the GitHub UI and revokes the credential the orchestrator uses; those actions take effect without a
PR.

### Organization-level conflict

This narrows the organization rule "unattended accounts never merge" for this repository, under the
organization file's own clause that the repository's rules win and the conflict must be raised. The
proposed organization-level wording is in the PR description under "Decisions only the owner can
make". No other repository is edited by this decision.

### Consequences

- Good: one fewer chat round-trip per PR; the guard checks what a chat message could not; the
  `Delegated-under` trailer makes every delegated merge visible in the history.
- Bad: the guard is code and can have defects; the owner's approval is still a human judgment; the
  organization rule is narrowed for this repository, which needs an organization-level decision.
- Neutral: the ruleset, Code Owner review and the owner's approval are unchanged.

### Confirmation

- `tests/test_merge_guard.py` exercises every refusal against a stubbed `gh`; no test merges anything.
- `tests/test_repo_governance.py` keeps the guard path protected and fails if `AGENTS.md` rule 1 names
  an owner account again.
- The first Phase 1 merge carries `Delegated-under: ADR-0011`, and the owner can audit it from
  `git log`.
- Branch deletion is a repository setting (on today). A post-merge check that fails (two parents,
  deletion, `ci-gate` on `main`) makes the guard exit 3 after the merge stands: the orchestrator
  reports it and does not retry or force anything.

## Pros and cons of the options

### Keep the per-PR chat go-ahead

- Good: no new code; the owner presses every merge.
- Bad: a second confirmation after the approval checks nothing new; routine work waits on chat.

### Merge whenever the owner has approved on GitHub

- Good: no guard to maintain.
- Bad: nothing pins the merge to the reviewed head or the reviewed files; a later push could ride on
  an earlier approval if the platform rules are misconfigured.

### Merge only through a guard

- Good: the approval, head, files, mergeability and checks are checked in one place; the merge is
  pinned; the trailer records the delegation.
- Bad: the guard itself needs tests and maintenance; a bug can refuse a good merge or, worse, allow a
  bad one.

## More information

- Organization context: [The-Urcydo/.github/AGENTS.md](https://github.com/The-Urcydo/.github/blob/main/AGENTS.md).
- [ADR 0008 in Agents-Skills-Roles-Oriented](https://github.com/The-Urcydo/Agents-Skills-Roles-Oriented/blob/main/docs/decisions/0008-single-owner-organization-access.md).
- `docs/maintainers/runbook.md`, section "Merge".
- The orchestrator brief of 2026-11-18 and the owner's chat approval of this PR.
