# Architecture

## Current runtime

```text
Windows 11
  |
  +-- Docker Desktop (Linux containers)
        |
        +-- FastAPI service :8000
        |     +-- /health
        |     +-- /health/db
        |     +-- /api/v1/assets
        |     +-- /api/v1/telemetry/{asset_id}
        |     +-- /api/v1/failures
        |     +-- /api/v1/work-orders
        |     +-- /api/v1/ingestion/runs
        |     +-- /api/v1/ingestion/runs/{run_id}
        |
        +-- PostgreSQL 16 + pgvector :5432
              +-- persistent Docker volume
```

## Phase 1B data flow

```text
data/generated/*.csv
  -> data_engineering/etl validation + transformation
  -> PostgreSQL (assets, details, telemetry, events, observability)
  -> ingestion reports + data-quality results
  -> FastAPI read-only queries (/api/v1)
```

The planned workflow is decision support only. It will not autonomously execute maintenance actions.

## Phase 1B boundaries

- `backend/`: FastAPI app, read-only CRUD/query helpers, Pydantic schemas, SQLAlchemy models, database session.
- `data_engineering/`: synthetic data generation, CSV validation, transformation, loading, quality checks, reporting, and CLI orchestration.
- `alembic/`: schema migrations (`04b9afe7bc6a` is current head).
- `tests/`: unit, integration, and evaluation tests.

## Planned boundaries

- `ml/`: features, training, evaluation, inference, and explainability.
- `rag/`: document ingestion, embeddings, retrieval, reranking, and generation.
- `frontend/`: operational dashboard.
- `infra/`: container and deployment configuration.
- `docs/`: data dictionary, design decisions, and operating guides.
