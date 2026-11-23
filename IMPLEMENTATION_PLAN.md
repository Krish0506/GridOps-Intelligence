# Implementation Plan

## Current milestone: Phase 1 foundation

- [x] Create initial project structure and API health endpoint.
- [x] Add Docker Compose with PostgreSQL + pgvector.
- [x] Add a minimal automated API test.
- [x] Verify Docker build and service startup (`docker compose up --build -d`; both services healthy; `/health` and `/health/db` return ok).
- [x] Generate reproducible synthetic utility datasets (`data_engineering/generators/`; CSVs in `data/generated/`).
- [x] Add SQLAlchemy models and Alembic migrations (revision `04b9afe7bc6a`).
- [x] Implement validated, idempotent ETL ingestion.
- [x] Add data-quality checks and reports.
- [x] Add unit and integration tests for ingestion and persistence.

## Current milestone: Phase 1B API and persistence layer

- [x] Add read-only FastAPI endpoints under `/api/v1` with pagination and Pydantic response schemas.
- [x] Add integration tests for database, Alembic, ETL, and API (suite passes: `python -m pytest -q`).

## Current milestone: Phase 2A leakage-safe feature engineering

- [x] Add typed feature-input records and strict prediction-cutoff helpers (`ml/features/types.py`, `ml/features/cutoff.py`).
- [x] Implement static asset, telemetry, maintenance, inspection, weather, and data-quality feature groups.
- [x] Implement combined asset-level feature records and deterministic batch building.
- [x] Enforce exclusive cutoffs and optional post-failure bounds for every source table.
- [x] Add three-state outcome labelling that keeps censored assets `UNKNOWN` instead of negative.
- [x] Add batched repository loaders with a constant number of queries per batch.
- [x] Add focused unit and integration tests (46 new tests; full suite passes).
- [x] Remediate review findings: historical work-order completion now derives from `completed_at < cutoff`; model-feature contract separates identifiers/metadata/categoricals/numerics/booleans from model inputs; per-asset event bounds supported in pure and DB paths; group functions are asset-scoped; training cohort refuses unconfirmed negatives.
- [x] Document feature definitions, cutoff semantics, and limitations in `docs/PHASE_2A_FEATURE_ENGINEERING.md`.

### Modeling readiness

**BLOCKED — synthetic label construction is circular and confirmed negatives are unavailable.**

The feature-engineering milestone is leakage-safe with respect to *timestamps*, but the
synthetic failure labels are constructed from the same telemetry-derived risk features that
the pipeline exposes, and no defensible confirmed-negative cohort exists. Predictive-model
validation must wait for a future synthetic-data milestone that decouples failure generation
from feature construction and provides an independent observation/follow-up process.

## Current milestone: Phase 2B independent synthetic evaluation data

- [x] Add an independent synthetic evaluation-data generator
  (`data_engineering/generators/independent_evaluation.py`) whose failure events
  follow hidden degradation processes independent of the telemetry risk score.
- [x] Generate historical telemetry as noisy observations of the hidden
  degradation process, strictly before failures and before the prediction cutoff.
- [x] Generate maintenance, inspections, and weather records independently of
  future failure labels.
- [x] Apply the Milestone 2A three-state label contract (positive / negative /
  unknown) to the independent dataset.
- [x] Run the shared synthetic-data validation suite on the new dataset.
- [x] Add feature snapshots through the existing Milestone 2A feature builders
  with per-asset event bounds.
- [x] Add focused tests for the independent generator, labels, temporal
  safeguards, reproducibility, and feature integration (8 new tests; full suite
  passes).
- [x] Document methodology, parameters, limitations, and usage in
  `docs/PHASE_2B_INDEPENDENT_EVALUATION_DATA.md`.

### Modeling readiness

**BLOCKED** — the independent evaluation dataset removes the circularity in failure
selection, but predictive-model training and evaluation remain blocked on the
remaining synthetic-data limitations (transparent degradation-threshold
simulation, confirmed-negative follow-up process, sufficient positive/negative
volume).

## Next milestone: Phase 3 model training and evaluation

- [x] Implement data-readiness gate (`ml/data/readiness.py`, `ml/data/cohort.py`).
- [x] Raise independent-evaluation default population to 1500 assets (configurable).
- [x] Implement logistic regression, Random Forest, and HistGradientBoosting baselines (`ml/models/`).
- [x] Implement metrics, training/inference workflows, artifact persistence (`ml/evaluation/`, `ml/pipelines/`, `ml/artifacts/`).
- [x] Implement anomaly detection via robust z-scores (`ml/anomaly/`).
- [x] Implement risk-prioritization schema (`ml/risk/`).
- [x] Add CLI workflows (`data_engineering/cli.py`).
- [x] Add focused tests (31 new tests; full suite green).
- [x] Document in `docs/PHASE_3_PREDICTIVE_MODELING.md`.

### Data readiness

**READY** — default dataset: 1500 assets, 176 confirmed positives, 1181 confirmed negatives, 143 unknown.

### Modeling readiness

**READY** — three-way split 60/20/20; logistic regression, Random Forest, and HistGradientBoosting all implemented and trained. All validation and final-test metrics are 1.0 (synthetic data — not a real-world claim).

## Current milestone: Phase 4 Evidence Intelligence

- [x] Synthetic engineering document corpus generator (TXT/DOCX/PDF).
- [x] Document ingestion pipeline with idempotency and partial-failure handling.
- [x] Hybrid retrieval with reranking.
- [x] Grounded answer generation with citation validation.
- [x] Asset-aware evidence integration.
- [x] Knowledge API endpoints.
- [x] CLI commands for knowledge workflows.
- [x] Database migration 0a1b2c3d4e5f.
- [x] Documentation in docs/PHASE_4_EVIDENCE_INTELLIGENCE.md and related.

## Current milestone: Phase 5 Engineering Decision Workflow

- [x] Decision state machine and business rules.
- [x] Database models and migration 2b3c4d5e6f7a.
- [x] Decision evidence association with validation.
- [x] Append-only audit history.
- [x] Decision API endpoints.
- [x] CLI commands for decision workflows.
- [x] Tests (14 new; full suite green).
- [x] Documentation in docs/PHASE_5_ENGINEERING_DECISION_WORKFLOW.md and related.

## Current milestone: Phase 6/7 Frontend and Platform Integration

- [x] React + TypeScript + Vite + Tailwind frontend scaffold.
- [x] Shared application shell with sidebar navigation.
- [x] Pages: Overview, Asset Explorer, Predictive Analytics, Risk Prioritization, Explainability, Evidence Intelligence, Engineering Decision Review, Governance and Audit.
- [x] Frontend wired to backend APIs (no hardcoded metrics).
- [x] TypeScript type checking passes.
- [x] Production build succeeds.
- [x] Smoke test passes.
- [x] Documentation: PHASE_6, PHASE_7, DEMO_RUNBOOK, KNOWN_LIMITATIONS.

## Engineering rules

- Synthetic data only; no employer-confidential information.
- Keep model training and evaluation free of target leakage.
- Make ingestion repeatable and observable.
- Test each milestone before expanding scope.
- Do not describe planned or simulated functionality as implemented or production-deployed.
