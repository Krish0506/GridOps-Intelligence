# Decision Workflow Design

## State machine

```
PENDING_REVIEW -> IN_REVIEW -> APPROVED
                            -> REJECTED
                            -> OVERRIDDEN
                            -> ESCALATED
                            -> DEFERRED
```

Transitions are enforced by `decisions.service`. Invalid transitions raise
`DecisionError`.

## Business rules

- APPROVE requires a reason.
- REJECT requires a reason.
- OVERRIDE requires a reason and an explicit replacement risk category.
- ESCALATE requires a reason.
- DEFER requires a reason and an optional review date.
- REVIEW requires an identifiable reviewer.
- No decision may silently change the original model prediction; `risk_category`
  (model) and `replacement_risk_category` (human) remain separate.

## Evidence

Evidence is associated only after validation against the knowledge base (chunk
existence and checksum match). Evidence records preserve document ID, chunk ID,
title, revision, page number, excerpt, and source checksum.

## Audit trail

`DecisionEvent` records are append-only. Each records previous status, new
status, action, reviewer, reason, timestamp, prediction snapshot, and evidence
snapshot. Ordinary updates never erase history.