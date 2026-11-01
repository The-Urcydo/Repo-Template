---
title: Human decision queue
type: meta
status: active
summary: The single queue of decisions only the human can make, each with a recommendation, a default and the cost of guessing wrong.
owner_role: orchestrator
---
# Human decision queue

Clear this in one sitting. Each entry has a recommendation: answering "go with the recommendation" is a valid answer.
Agents add entries with `python3 tools/question.py ask` and the orchestrator records answers with `python3 tools/question.py answer`. Do not edit entries by hand.

## Open

_None._

## Answered
