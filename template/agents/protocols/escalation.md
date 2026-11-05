---
title: Escalation protocol
type: reference
status: active
summary: When an agent must ask the human (always for an ambiguous directive, and for risky decisions), how to ask so they can answer in seconds, and what to do while waiting.
owner_role: architect
---
# Escalation protocol

The human's words outrank your inference: ask about what they meant. The human's time is scarce: decide what is yours to decide. Never block everything on an answer.

## Ambiguous directives: always ask

This section outranks every "ask rarely" and "decide and move on" line in this repo.

A directive is ambiguous when any of these is true:

- A word or phrase has two plausible meanings or targets ("the config", "clean up", "the old one").
- The scope is not bounded: which files, how many, whether X is included.
- The success condition is missing, or two stated conditions disagree.
- It conflicts with the brief, an accepted ADR or an earlier directive.
- You would have to invent a requirement to proceed.

Writing "I assume", "probably means" or "I interpreted" in your own reasoning means the same: stop and ask. A guess marked "assumed" in the handoff is still a guess.

Make one lookup first (the brief, the handoff, `docs/INDEX.md`, the ADRs). Do not ask what they already answer, and do not ask what the human cannot know (how the code works, say). Do ask when they leave it open.

How to ask:

1. One message with every open point, not one at a time. For each point: the question and your best reading as the suggested answer. A good question can be answered with one word.
2. Do not start the unclear part. Keep working on the parts that are clear.
3. The human is in the session: ask in chat, right away. Write their answer in the item's handoff under "Decisions made" so the next session does not ask again.
4. The human is not in the session (inbox, scheduled or unattended work): use the queue below, with `--recommended` set to your best reading and `--if-no-answer "that part is not done"`. Nobody, the orchestrator included, applies your reading in the human's place.

## Other decisions: stop and ask when the decision is

- **Irreversible**: deleting data or history, force-pushing, dropping tables, publishing, sending messages to real people.
- **Costly or risky**: spends money, touches production, credentials or personal data, or changes access.
- **A scope or goal change**: the work would now do something the brief did not ask for.
- **A conflict**: two accepted ADRs disagree, or the request contradicts one.
- **An ADR the human must accept**: a significant, costly or irreversible decision. Ask through the queue (see `docs/dev/how-to/write-an-adr.md`).

Do **not** ask about reversible, low-cost choices inside your role that nobody spoke about. Decide, record it in the handoff ("Decisions made"), and move on. This covers your own choices, never what the human said.

## The queue

```
python3 tools/question.py ask "Short title" --asked-by <role> \
  --recommended "the option you would pick" \
  --if-no-answer "what will happen by default" \
  --cost "low|medium|high: what guessing wrong costs" \
  --options "A; B; C" --item <item-id>
```

A good question can be answered with one word. It always has a recommendation, a default, and a cost of being wrong. For anything irreversible, the default is "nothing changes"; for an ambiguous directive it is "that part is not done". The question goes into `work/HUMAN.md`; the human clears the whole queue in one sitting.

If the human raised a decision from the list above in chat, reply there in one line: the question id, that nothing was done, and what you are doing meanwhile. The queue is the record; chat is only the pointer.

## While waiting

1. If there is an item, move it to `blocked` with `--next "waiting on Q-0007: <what unblocks it>"`, unless you can continue on a part that does not depend on the answer. With no item, carry on with your other work.
2. Pick up another item. Never idle on one question.
3. If the question outlives its default horizon (7 days; `check.py` warns), the orchestrator applies `if_no_answer`, records the answer with `question.py answer`, and notes it in the handoff. Irreversible decisions and questions about an ambiguous directive never auto-default: they wait, and that part stays not done.

## Never

- Put a question only in a handoff: it records, it does not reach the human.
- Raise a risky decision only in chat while the human is away: the queue is the record.
- Resolve an unclear directive yourself and note "assumed" in the handoff.
- Smuggle a risky change into a "small fix" to avoid asking.
- Guess on an ambiguous directive or on anything listed above.
