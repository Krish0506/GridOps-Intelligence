# GridOps Intelligence — Interview Preparation Notes

How to talk about this project in a senior data science / full-stack interview, and what a reviewer should probe.

## Why the stack was chosen

- FastAPI + SQLAlchemy + Alembic + PostgreSQL: typed Python backend, migration discipline, relational integrity for assets/features/decisions/evidence.
- React + TypeScript + Vite + Tailwind + Recharts: strong typing end-to-end, component design system rather than ad-hoc CSS, chart library with real SVG output.
- Docker Compose: single-command local runtime; Postgres host port 55432 for host access, container networking for API.

## Architectural decisions worth explaining

1. **Derived risk records.** Risk outputs are derived artifacts persisted per snapshot; source facts are never mutated by risk generation. Idempotent full rebuild at cutoff.
2. **Deterministic ranking.** Percentiles via tie-broken ranks because saturated probabilities (1.0) made naive percentile maps unusable.
3. **Robust anomaly baseline.** Median + robust scale (MAD/IQR/std fallback) with feature-scale floor and z-score cap; anomaly magnitude is not a failure probability.
4. **Explainability without SHAP.** Used robust z-score deviations + global coefficient importance; explicitly avoided claiming SHAP. Global importance is model behaviour, not local attribution, and not causation.
5. **Structured vs document evidence.** Count/status questions routed to SQL aggregations; open-ended questions to hybrid retrieval. No fabricated answers; insufficiency surfaced.
6. **Human-in-the-loop.** Mandatory rationale before transitions; append-only audit events; no auto-approve/auto-execute.

## Data engineering tradeoffs

- Synthetic generation designed to be realistic enough to exercise the pipeline but clearly labeled synthetic.
- Quality checks persisted per ingestion run; governance surfaces failures.
- Idempotency: ingest + risk rebuild + knowledge forced re-ingestion designed to avoid destructive duplicate seeds while tolerating reruns.

## Feature leakage prevention

- Feature snapshots built from historical windows only; labels constructed from post-event outcomes without leakage into features; training/inference feature consistency; evaluation on an independent cohort.

## Model evaluation methodology

- Logistic regression persisted; metrics (ROC AUC, precision, recall, F1, avg precision, Brier) over independent synthetic cohort; evaluation context explicitly synthetic; near-perfect metrics explained as deliberately separable synthetic outcomes.

## Model limitations

- Saturated probabilities, deterministic tie-breaking, no drift monitoring, no auto-retraining, synthetic metrics.

## Risk prioritization

- Combination of probability percentile, anomaly deviation, criticality, data quality; no arbitrary composite score invented.

## Explainability

- Robust z-score; global importance; no SHAP (documented); methodology limits surfaced.

## RAG and citations

- Deterministic embeddings (mock embeddings) + hybrid retrieval; citations with doc identity/revision/page/checksum; limitations surfaced.

## Human-in-the-loop decisions

- State machine: create → in_review → approved/rejected/escalated/deferred/overridden; rationale mandatory; audit events.

## DB/API design

- Star schema-ish fact tables + dimension; typed API responses; pagination/search/sort on assets; risk detail with explanation; governance aggregates.

## Scaling considerations / production-readiness gaps

- Single-node local demo; no authN/AuthZ; no drift; no retraining automation; no compliance cert; no real data; no LLM backend required (structured/rag path is local deterministic); no persistence beyond local Docker volume.

## Talking points from the final hardening pass

- Root cause of “cannot open localhost:5173”: Vite not running + proxy target using `localhost` (IPv6) causing ~2s per-request latency; startup scripts hardened.
- Governance rendering crash fixed (JSONB details rendered as React child) + duplicate React keys fixed via result_id.
- Live end-to-end browser journey completed on all eight pages; console clean after fixes; refresh/back/forward verified.
