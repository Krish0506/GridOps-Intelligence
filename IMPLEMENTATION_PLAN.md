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

- [ ] Not started. Blocked on Phase 2B modeling readiness.

## Engineering rules

- Synthetic data only; no employer-confidential information.
- Keep model training and evaluation free of target leakage.
- Make ingestion repeatable and observable.
- Test each milestone before expanding scope.
- Do not describe planned or simulated functionality as implemented or production-deployed.
