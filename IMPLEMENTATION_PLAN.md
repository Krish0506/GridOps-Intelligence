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

## Engineering rules

- Synthetic data only; no employer-confidential information.
- Keep model training and evaluation free of target leakage.
- Make ingestion repeatable and observable.
- Test each milestone before expanding scope.
- Do not describe planned or simulated functionality as implemented or production-deployed.
