# Decision Audit and Governance

## Governance principles

- The system never autonomously approves or executes maintenance.
- Model predictions are recommendations, not decisions.
- Engineer decisions are separate records with explicit reasons.
- Evidence supports but does not prove a decision.
- All state transitions are auditable.

## Audit trail

`decision_events` is append-only. Each event records previous state, new state,
action, reviewer, reason, timestamp, prediction snapshot, and evidence snapshot.

## Immutability

Decision history cannot be deleted or overwritten through the public API.
Ordinary update operations are not exposed. Corrections require a new explicit
action recorded as a new event.