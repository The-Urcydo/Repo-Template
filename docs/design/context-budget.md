---
title: Context budget and why AGENTS.md is short
type: explanation
status: active
summary: What research says about repository instruction files, and how that shaped the three-tier loading, the line budgets and the evals.
---
# Context budget and why AGENTS.md is short

## What the evidence says

Studies of repository-level instruction files (`AGENTS.md`, `CLAUDE.md`) disagree in ways that matter for this design:

- An ETH Zurich study (arXiv:2602.11988) found that context files did not significantly improve task success across several agents and models, and raised inference cost by roughly 20%. Agents followed the instructions faithfully, but repository overviews did not help them find files faster. The files were most useful for specifying non-standard practices. LLM-generated context files performed worst; hand-written ones fared slightly better.
- A separate efficiency study (arXiv:2601.20404) found that having an `AGENTS.md` was associated with about 29% lower median runtime and about 17% fewer output tokens on a small sample, without evaluating patch correctness.
- Vendor guidance for Claude Code recommends keeping instruction files under about 200 lines, because longer files reduce adherence. The Agent Skills specification recommends skill instructions under about 5,000 tokens and loads only each skill's name and description at startup.

These are benchmark results on particular repositories and models, so treat them as pressure toward restraint, not as laws. They are the reason this repo measures its own harness (the optional `evals` module) instead of assuming it helps.

## What this repo does about it

1. **Three tiers.** Tier 0 is the root `AGENTS.md`, always loaded, limited to 100 lines by `check.py`. Tier 1 is the indexes (`docs/INDEX.md`, `work/ACTIVE.md`, `agents/README.md`, `agents/ROSTER.md`), loaded when needed. Tier 2 is the content itself, opened only when a task requires it. A group in `docs/INDEX.md` with more than 40 entries gets its own section index, so the root index stays small.
2. **Only non-discoverable facts in `AGENTS.md`.** Build commands, hard rules, the definition of done. No directory trees (`check.py` warns), no restating what the code or `README.md` already says.
3. **Summaries instead of reading.** Every doc has a one-sentence `summary`; agents can grep summaries instead of opening files.
4. **Nested, scoped rules.** Folder-specific rules live in a short `AGENTS.md` in that folder (limit 60 lines), loaded when an agent works there, not in every session.
5. **Skills for methods.** The step-by-step method for a task lives in a skill, which costs about a hundred tokens until a task matches. A role's routing and limits stay in its charter, because that is always read.
6. **Hand-written, then tested.** The root `AGENTS.md` is hand-written. Changes to it, to roles or to skills should be checked with the golden tasks in the `evals` module when it is installed, comparing behavior before and after.

## When to break the rules

If an agent keeps making the same mistake, add one line for it to the nearest `AGENTS.md` and check that the mistake stops. If a line has not changed behavior for a long time, delete it. A short file of real constraints beats a long file of descriptions.
