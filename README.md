# GridOps Intelligence

Explainable AI and predictive maintenance platform combining classical machine learning, retrieval-augmented generation (RAG), utility asset risk intelligence, and human-in-the-loop decision support.

> **Project status:** Phase 1B complete. The synthetic data foundation is implemented and verified: PostgreSQL schema via Alembic, validated idempotent ETL, data-quality reporting, read-only API, and integration tests. This is an independent portfolio project using synthetic data only. It is not a DTE system, is not connected to utility operational systems, and does not make real maintenance decisions.

## Phase 1B delivered capabilities

- SQLAlchemy 2.x models for assets, type-specific details, telemetry, events, and ingestion/quality observability tables.
- Initial Alembic migration `04b9afe7bc6a` (head) creating the operational schema.
- Validated, idempotent CSV-to-PostgreSQL ETL with structured ingestion reports and rejected-row reporting.
- Data-quality checks persisted per ingestion run.
- Read-only FastAPI endpoints under `/api/v1` with pagination and Pydantic response schemas.
- Integration tests for database schema, Alembic migration, ETL, and API.

## Initial technology foundation

- Python 3.11 and FastAPI
- PostgreSQL 16 with pgvector
- SQLAlchemy 2.x and Alembic
- Docker Compose
- Pytest

## Prerequisites

- Docker Desktop with Linux containers enabled
- Git
- Python 3.11+ (for running tests locally)

## Quick start

1. Copy `.env.example` to `.env`:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Start PostgreSQL and the API:

   ```powershell
   docker compose up --build -d
   ```

3. Check service status:

   ```powershell
   docker compose ps
   ```

4. Check API health:

   ```powershell
   Invoke-RestMethod http://localhost:8000/health
   Invoke-RestMethod http://localhost:8000/health/db
   ```

5. Apply the database schema:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   alembic upgrade head
   ```

6. Run the synthetic ingestion:

   ```powershell
   python -m data_engineering.etl
   ```

7. Open API documentation:

   http://localhost:8000/docs

## Run tests locally

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
```

The integration tests use a dedicated `gridops_test` PostgreSQL database and a
separate `gridops_migration_scratch` database for reversible migration checks; they
do not reset the development database.

## Read-only API endpoints

- `GET /health` and `GET /health/db`
- `GET /api/v1/assets` (filters: `asset_type`, `status`, `region`; pagination: `limit`, `offset`)
- `GET /api/v1/assets/{asset_id}` (includes type-specific detail when present)
- `GET /api/v1/telemetry/{asset_id}` (optional `start`/`end` window; pagination: `limit`, `offset`)
- `GET /api/v1/failures` (filters: `failure_category`, `failure_severity`, `asset_id`; pagination: `limit`, `offset`)
- `GET /api/v1/work-orders` (filters: `work_type`, `priority`, `status`, `asset_id`; pagination: `limit`, `offset`)
- `GET /api/v1/ingestion/runs` (pagination: `limit`, `offset`)
- `GET /api/v1/ingestion/runs/{run_id}` (dataset results and quality results)

## Planned development phases

1. Data foundation: synthetic datasets, PostgreSQL schema, repeatable ETL, and data-quality checks.
2. Predictive analytics: failure-risk classification, anomaly detection, and asset prioritization.
3. Explainability: global and local model explanations.
4. Evidence intelligence: local RAG, hybrid retrieval, reranking, citations, and evaluation.
5. Human review: approve, reject, override, escalate, and audit workflows.
6. Application experience: operational dashboard and decision-review UI.
7. Hardening: security, monitoring, model/data governance, and CI.

## Data and security

Use synthetic or explicitly licensed public data only. Never commit credentials, private documents, employer data, customer information, or operational infrastructure details. The default database password is for local development only and must be changed before any shared or deployed environment.
