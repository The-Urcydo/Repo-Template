---
title: Escalation protocol
type: reference
status: active
summary: When an agent must stop and ask the human, how to ask so the human can answer in seconds, and what to do while waiting.
owner_role: architect
---
# Escalation protocol

The human is the scarcest resource. Ask rarely, ask well, never block everything on an answer.

## Stop and ask when the decision is

- **Irreversible**: deleting data or history, force-pushing, dropping tables, publishing, sending messages to real people.
- **Costly or risky**: spends money, touches production, credentials or personal data, or changes access.
- **A scope or goal change**: the work would now do something the brief did not ask for.
- **Ambiguous in a way that changes the outcome**, and you cannot resolve it from the repo.
- **A conflict**: two accepted ADRs disagree, or the request contradicts one.
- **An ADR the human must accept**: a significant, costly or irreversible decision. Ask through the queue (see `docs/dev/how-to/write-an-adr.md`).

Do **not** ask about reversible, low-cost choices inside your role. Decide, record it in the handoff ("Decisions made"), and move on.

## How to ask

```
python3 tools/question.py ask "Short title" --asked-by <role> \
  --recommended "the option you would pick" \
  --if-no-answer "what will happen by default" \
  --cost "low|medium|high: what guessing wrong costs" \
  --options "A; B; C" --item <item-id>
```

A good question can be answered with one word. It always has a recommendation, a default, and a cost of being wrong. For anything irreversible, the default is "nothing changes". The question goes into `work/HUMAN.md`; the human clears the whole queue in one sitting.

If the human raised it in chat, reply there in one line: the question id, that nothing was done, and what you are doing meanwhile. The queue is the record; chat is only the pointer.

## While waiting

1. If there is an item, move it to `blocked` with `--next "waiting on Q-0007: <what unblocks it>"`, unless you can continue on a part that does not depend on the answer. With no item, carry on with your other work.
2. Pick up another item. Never idle on one question.
3. If the question outlives its default horizon (7 days; `check.py` warns), the orchestrator applies `if_no_answer`, records the answer with `question.py answer`, and notes it in the handoff. Irreversible decisions never auto-default: they wait.

## Never

- Ask the human in chat or in a handoff instead of the queue (a one-line pointer in chat is fine).
- Smuggle a risky change into a "small fix" to avoid asking.
- Guess on anything listed above.
