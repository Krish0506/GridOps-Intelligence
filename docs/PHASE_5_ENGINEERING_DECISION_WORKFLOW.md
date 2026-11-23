# Phase 5 — Engineering Decision Workflow

Status: **Implemented**.

## Summary

Milestone 5 adds a human-in-the-loop engineering decision workflow on top of
Milestone 3 risk outputs and Milestone 4 evidence retrieval. Engineers can
review predictive risk information, associate supporting evidence, record a
decision, and inspect an append-only audit history.

## Decision lifecycle

`PENDING_REVIEW → IN_REVIEW → APPROVED / REJECTED / OVERRIDDEN / ESCALATED / DEFERRED`

- `REVIEW` moves `PENDING_REVIEW` to `IN_REVIEW`.
- `APPROVE`, `REJECT`, `OVERRIDE`, `ESCALATE`, `DEFER` require `IN_REVIEW`.
- No silent overwrites; every transition appends a `DecisionEvent`.
- `OVERRIDE` requires a reason and a replacement risk category; the original
  model prediction is preserved in `risk_category`.

## Database

- `engineering_decisions` — decision record with asset, model prediction,
  anomaly score, status, reason, reviewer, timestamps.
- `decision_evidence` — associated knowledge chunks (validated against the
  knowledge base).
- `decision_events` — append-only audit history.

Migration revision: `2b3c4d5e6f7a` (revises `0a1b2c3d4e5f`).

## API endpoints

- `GET/POST /api/v1/decisions`
- `GET /api/v1/decisions/{decision_id}`
- `POST /api/v1/decisions/{decision_id}/review|approve|reject|override|escalate|defer`
- `GET /api/v1/decisions/{decision_id}/history`
- `GET/POST /api/v1/decisions/{decision_id}/evidence`

## CLI commands

- `list-pending-decisions`
- `get-decision <id>`
- `show-decision-history <id>`

## Tests

Decision workflow tests: 14 (creation, transitions, required reasons, override
validation, evidence association, history immutability, prediction snapshot
preservation). Full suite: 173 passed.

## Limitations

- No real authentication; uses a documented demonstration reviewer identity.
- No frontend integration in this milestone.
- Human approval does not execute maintenance actions.