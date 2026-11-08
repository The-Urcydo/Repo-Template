---
title: Tier the role roster and admit roles by a test
type: decision
status: proposed
summary: Roles are tiered into flow, advisory and optional, run as hats by default with a separate session only for review, and a new role must pass an admission test.
date: 2026-11-08
decision_makers: human
supersedes: []
---
# 0007: Tier the role roster and admit roles by a test

## Context and problem statement

The harness ships eight role charters: orchestrator, planner, architect, builder, reviewer, researcher, scribe and the optional security module. Each is written as a pipeline step. The work is done by one human with many fresh sessions, where every extra handoff reloads context and costs tokens. Which roles should exist, how should each one run, and what must a new role prove before it is added?

Four facts in the current harness make the question concrete:

- `agents/protocols/definition-of-done.md` asks for docs and a changelog line only "for items that change behavior", but the dispatch table and `DEFAULT_OWNER` in `tools/_lib.py` send every `verified` item to the scribe.
- The researcher's hand-back command is `transition.py <id> draft --owner planner --by researcher`. `transition.py` treats a target equal to the current status as an in-place update and rejects `--by` there, so the command fails when the item is still `draft`, which is where the planner leaves it while it waits for research.
- None of the dispatch table, `DEFAULT_OWNER`, the planner, reviewer and orchestrator charters or the brief template routes an item to the security role. It runs only if someone remembers it.
- `--by <role>` is checked only against the list of role names. `built_by` and `verified_by` stop accidents, not a session that labels itself reviewer. Independence rests on the review protocol (a fresh session) and the owner's merge gate. A fresh context removes the builder's conversation, not the model's blind spots.

## Decision drivers

- One human and many fresh sessions: a role that needs no isolation should not cost a session.
- Review needs real independence from the build, and the tools cannot prove it.
- Evidence on multi-agent work: about 15 times the tokens of chat, and a weaker fit when agents share context, as most coding does. Subagents pay off for isolated, verbose or restricted work.
- Instruction text has a cost too (`docs/dev/explanation/context-budget.md`), so remove or merge before adding.
- The harness stays tool-neutral (ADR 0002), roles stay bundles (ADR 0005) and optional parts stay cuttable (ADR 0004).
- Measure before adding: no real-agent run is recorded yet (issue #7).

## Considered options

- Keep the eight roles as pipeline steps, unchanged.
- Tier the roster, run roles as hats by default, require a separate session for review, and gate new roles with an admission test.
- Collapse to a few roles (builder, reviewer, orchestrator) and turn the rest into skills.
- Add more roles in the style of BMAD (QA engineer, UX designer, scrum master).

## Decision outcome

Chosen option: "Tier the roster, run roles as hats by default, require a separate session for review, and gate new roles with an admission test", because it removes the handoffs that carry no independence, keeps the one that does, and gives a rule for growing the roster that does not depend on anyone's taste.

1. **Tiers.** Flow roles own a status in the state machine: orchestrator, planner, builder, reviewer and the scribe (conditional, see 4). Advisory roles produce an artifact on request: architect and researcher. Optional modules are cut as one folder: security today.
2. **Hats by default.** A role runs as a hat: the session that holds the item reads the charter and acts as that role. A separate session is required only for review (and for security when installed): the reviewer never runs in the session that built the item. A role that needs its own context window, such as the researcher or a builder in a worktree, may run isolated. That is a choice of the session, not a status change.
3. **The researcher is a callable worker.** The caller (planner or architect) keeps the item's status and owner, asks a question, and receives `research.md`. The researcher runs no transition, which removes the failing hand-back. The architect's hand-over stays as it is until a later decision.
4. **The scribe is conditional.** The builder already lists affected docs in the handoff. When that list is empty and behavior did not change, the reviewer moves the item to `verified` with `--owner orchestrator` and the orchestrator marks it `done`; otherwise the scribe runs as today. `DEFAULT_OWNER` and the dispatch table keep the scribe as the default after `verified`, so no tool changes.
5. **Admission test for a new role.** A new role folder is added only if the role has at least one of: exclusive ownership of paths or item files that no role owns; a different access level than its callers; the checker half of a maker and checker pair; or work output large enough to need its own context window. Otherwise the behavior is a skill under an existing role. Existing roles are re-checked against the test in a follow-up pull request.
6. **Not added now.** A tester (QA) role waits until real-agent baselines show test quality is the failing step. How security gets triggered (by the brief or by touched paths) is a follow-up.

### Consequences

- Good: fewer forced handoffs per item; the scribe costs a session only when docs change; the researcher hand-back defect disappears; the dispatch table and the definition of done agree; new roles meet a stated bar.
- Bad: two more ideas to learn (tiers and modes); reviewer independence stays protocol-only; a role's charter now describes more than one way to run it.
- Neutral: the state machine, `tools/` and the role charter schema do not change.

### Confirmation

- `python3 tools/check.py` passes on the changed charters (the required keys do not change).
- Golden tasks, added with the charter changes: the researcher is called without taking over the item, and a docs-free item skips the scribe. Existing tasks (`respect-ownership`, `handoff-roundtrip`, `role-skill-discovery`) are re-run for regressions.
- Real-agent runs before and after are recorded in `agents/evals/results/README.md`. If a change does not move the results, question whether it should exist.
- The pull request that changes charters is a harness change and needs the owner's approval.

## Pros and cons of the options

### Keep the eight roles unchanged

- Good: no work; the state machine already enforces it.
- Bad: every item pays for a scribe hop; the researcher hand-back fails; security is unrouted.

### Tier the roster with hats, a separate review session and an admission test

- Good: keeps the one independent step, trims the rest, and needs no tool change.
- Bad: more rules to explain; independence of the reviewer is still convention.

### Collapse to builder, reviewer and orchestrator

- Good: the smallest roster and the cheapest sessions.
- Bad: loses one-writer-per-path ownership of briefs and docs; skills cannot own files.

### Add more roles in the style of BMAD

- Good: familiar names; more specialist prompts.
- Bad: more handoffs and more instruction text with no evidence they raise success here.

## More information

Related: ADR 0002, ADR 0004, ADR 0005, `agents/protocols/review.md`, `agents/protocols/handoff.md`, `docs/dev/explanation/ownership-and-handoffs.md`.

Evidence:

- [How Anthropic built its multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system): about 15 times the tokens of chat; a weaker fit for shared-context work such as most coding.
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents): isolated context, tool restrictions, and when to stay in the main conversation.
- [Evaluating AGENTS.md (arXiv 2602.11988)](https://arxiv.org/abs/2602.11988): context files gave no general gain in task success and cost over 20% more.
- [Reviewer independence: context reset or model diversity](https://agentpatterns.ai/patterns/multi-agent/context-reset-vs-model-diversity/): a fresh context is only partial independence; execution-grounded checks and model diversity help more.

Follow-ups, each its own pull request: the researcher and scribe charter and dispatch edits; security routing; a tool-neutral `access` hint in `ROLE.md` that the Claude adapter maps to a subagent `tools` list (today `sync_agents.py` writes only `name` and `description`, and a tool list limits accidents, not a determined session, because a shell can still edit files); the split of procedure between `ROLE.md` and `SKILL.md`; real-agent baselines.
