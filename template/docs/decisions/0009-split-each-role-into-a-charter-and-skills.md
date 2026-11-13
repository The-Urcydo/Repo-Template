---
title: Split each role into a charter and skills
type: decision
status: accepted
summary: A role's ROLE.md holds its routing and limits and its skills hold the method, each fact has one home, and the role's tier decides whether it needs a skill.
date: 2026-11-13
decision_makers: human
supersedes: []
---
# 0009: Split each role into a charter and skills

## Context and problem statement

ADR 0005 put each role and the skills only it uses in one folder. ADR 0007 left one question open: how a role's procedure is divided between `ROLE.md` and its `SKILL.md`. Four facts make the question concrete:

- The reviewer's `ROLE.md` and its `verify-work` skill gave the same steps in the same order. Every change to the review flow was made in both files, and a test required the same strings in both.
- The Claude adapter copies the body of `ROLE.md` into the role's subagent file, so everything in `ROLE.md` is read on every run of that role.
- A Claude subagent preloads only the skills listed in its own `skills` field. It does not see the skills the main session has invoked, and it finds other project skills only if it decides to use the Skill tool. The adapter wrote no such field.
- Only a skill's name and description are loaded at startup. Its body is read when a task matches (`docs/dev/explanation/context-budget.md`).

Which text belongs in the charter, which in a skill, and which roles need a skill at all?

## Decision drivers

- One fact, one place: a change to a flow should be one edit.
- What must never be skipped has to be in the file an agent always reads.
- A role run as a hat in the main session finds a skill by its description. A subagent gets only what it lists.
- Instruction text has a cost (ADR 0007), so remove or merge before adding.
- Measure before adding: no real-agent baseline is recorded yet, so move existing text rather than write new text.

## Considered options

- Keep both files and test that they agree.
- Keep all procedure in `ROLE.md` and drop the role skills.
- Charter for routing and limits, skill for method, one home for each fact, the adapter preloads a role's skills, and the tier decides whether a role has a skill.
- Keep all procedure in the skill and leave `ROLE.md` as front matter and a pointer.

## Decision outcome

Chosen option: "Charter for routing and limits, skill for method", because it removes the duplicated text, keeps the parts that must not be skipped in the always-read file, and still delivers the method to a Claude subagent.

1. **`ROLE.md` is the charter.** Front matter, when the role runs or is called, the routing, the quality bar, and a pointer to the role's skills (a Procedure line, or the step that uses one). Routing means every command that changes who owns an item or what its status is, with the condition for using it.
2. **A skill is the method for one task.** The read order, the checks, the templates, the evidence, and the commands that do not move the item. It may be long and may use `references/`.
3. **One fact, one home.** When both need a fact, the charter states the rule and the skill points to it. A command is written in exactly one of the two.
4. **The tier decides whether a role has a skill.** A flow role owns a status, so its charter is mostly routing and it gets a skill only for a task with its own method (the reviewer). An advisory role or an optional module produces an artifact and runs no status commands, so its method dominates and it gets a skill. A role with nothing to split has none. A skill that only restates its charter is not added.
5. **The Claude adapter lists a role's own skills in the subagent's `skills` field.** Shared skills are not listed. A skill that sets `disable-model-invocation` is left out, because Claude Code does not preload it.

### Consequences

- Good: a change to a flow is one edit; routing sits in the file that is always read; in the main session the method loads only when the task matches; a subagent still gets it through the preload.
- Bad: a charter alone no longer shows the whole procedure; an agent that skips the skill misses the method; a subagent preloads the method on top of the charter, so a subagent run reads more text than before, and only the main session saves anything (the skill loads when the task matches); the check below looks at commands only, so a repeated sentence is not caught.
- Neutral: the state machine, the other tools and the `ROLE.md` front matter schema do not change.

### Confirmation

- The template's own test suite (it is not shipped to projects) fails when a command appears in both a role's charter and one of its own skills. A second test shows the check does fail on a repeat.
- Shipped tests assert the `skills` line for a role's own skills, and its absence for shared skills, for a role with no skill, for a skill that cannot be preloaded, and in Cursor rules.
- The `role-skill-discovery` golden task still passes on its fixtures. Whether a real agent opens the skill is checked by hand on a transcript.
- Not verified: that Claude Code loads the generated `skills` line. It follows the form in Claude Code's documentation, and an unknown or mistyped field is ignored without an error.

## Pros and cons of the options

### Keep both files and test that they agree

- Good: no restructuring.
- Bad: every change is still two edits; the test pins the duplication.

### Keep all procedure in `ROLE.md` and drop the role skills

- Good: one file per role, always read.
- Bad: every run pays for method it may not need; the role bundles of ADR 0005 lose their skills.

### Charter for routing and limits, skill for method

- Good: one home per fact; the always-read file is short and holds what must not be skipped.
- Bad: two files to read for the whole procedure.

### Keep all procedure in the skill

- Good: the shortest charter.
- Bad: a rule that must not be skipped depends on an agent finding a skill.

## More information

Accepted by the owner in chat on 2026-11-13, after reviewing the pull request that adds this record.

Related: ADR 0002, ADR 0005, ADR 0007, `agents/AGENTS.md`, `docs/dev/how-to/add-a-skill.md`, `agents/adapters/README.md`.

Evidence:

- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents): a subagent preloads the skills listed in its `skills` field with their full content, and the field controls what is preloaded. A skill that sets `disable-model-invocation` cannot be preloaded.
