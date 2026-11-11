---
title: Ownership and handoffs
type: explanation
status: active
summary: Why every path has one writer, how independent review is enforced, and how a handoff file lets a fresh session continue without memory.
---
# Ownership and handoffs

## One writer per path

When several agents run at once, the damage comes from overlap: two agents rewriting the same file, or an agent "helpfully" fixing something in another role's area. The rule is simple: every path has exactly one owner.

- A folder's `README.md` names its owner in `owner_role`. The nearest ancestor wins, so `docs/` belongs to the scribe while `docs/decisions/` belongs to the architect.
- Inside a work item, each role writes specific files (`item_files` in its charter): the planner writes `brief.md`, `plan.md`, `tasks.md`; the reviewer writes `review.md`.
- Ownership is declared next to the thing owned, so cutting a folder or module removes its claim automatically, with no central list to update.
- `check.py` fails when two roles claim the same item file, or a README names a role that does not exist. It cannot see who edited what; the rule is enforced by the charters, by review, and by the diff.

If you need a change in a path you do not own, write it in the handoff `next_action` for the owner. Do not make the change yourself.

`handoff.md` is the exception to one writer per path: whoever holds the item keeps it current, because the memory must be writable by the role that has the context. To change something you do not own, name the owner and the change in the handoff, or give the owner a light item (see `agents/protocols/handoff.md`). The root `AGENTS.md` has no role owner: it belongs to the human.

## Independent review

The role that built an item never verifies it. This is enforced mechanically where it can be: every status change passes `--by <role>`, `transition.py` records `built_by` once and refuses `verified` or `done` from that role, and it refuses those states without `review.md` (full items) and evidence. It is enforced by protocol where it cannot be: a single model playing both roles should use a fresh session that has not seen the build. The point is a second mind that must be convinced, not a ceremony.

When the `security` module is installed, a third mind is added for the changes that carry the most risk. The planner records in the brief's Security review section whether one is `required`. The reviewer reads that line before any verdict and, if it says `required`, lends the item to the security role (`transition.py <id> --owner security`; the status stays `in-review`). Security writes `security-review.md` in its own session and hands the item back with `--owner reviewer`. The reviewer then decides: a blocker or major finding means `changes requested`. `transition.py` enforces the last step: it refuses `verified` when the brief says `required` and `security-review.md` is missing (the template placeholder is not a decision, and a brief with no section does not block). The routing itself is carried by the charters and checked by the `security-routing` golden task.

## Handoffs are the memory

A session ends and the next one starts with nothing. The `handoff.md` front matter carries state a machine can read (`status`, `owner_role`, `next_action`, `do_not`, `evidence`); the body carries what a human or agent needs (current state, decisions made, dead ends). Three details make it trustworthy:

- **Typed state.** A fixed state machine, with moves enforced by `transition.py`, means a status always means the same thing.
- **Staleness is explicit.** An item idle for 14 days becomes `stale`, and a stale handoff is treated as unverified until someone re-checks it. A file that pretends to be current is worse than none.
- **Current state, not a diary.** The body stays under about 60 lines. Long histories hide the one line that matters.

## Asking the human

The human is the scarcest resource, so risky decisions go to one queue (`work/HUMAN.md`), each with a recommendation, a default and the cost of guessing wrong. The human clears the queue in one sitting; agents move on to other items meanwhile and apply the default if a reversible question waits too long. Irreversible decisions never auto-default. What the human meant is a different matter: their words outrank an agent's inference, so an unclear directive is always asked (in chat while the human is in the session, in the queue otherwise) and never defaults to the agent's reading. Rules: `agents/protocols/escalation.md`.
