[CmdletBinding()]
param(
    [string]$ProjectPath = (Get-Location).Path
)

$ErrorActionPreference = "Stop"
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path

Write-Host "GridOps Phase 1 bootstrap" -ForegroundColor Cyan
Write-Host "Target: $ProjectPath"

$files = [ordered]@{}

$files[".gitignore"] = @'
# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/

# Environment and secrets
.env
.env.*
!.env.example

# IDE / OS
.vscode/
.idea/
.DS_Store
Thumbs.db
*.log

# Generated datasets and artifacts
data/generated/
data/processed/
models/
mlruns/

# Node
node_modules/
dist/
'@

$files[".env.example"] = @'
APP_NAME=GridOps Intelligence API
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql+psycopg://gridops:gridops_dev_only@db:5432/gridops
POSTGRES_DB=gridops
POSTGRES_USER=gridops
POSTGRES_PASSWORD=gridops_dev_only
'@

$files["requirements.txt"] = @'
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
sqlalchemy>=2.0,<3.0
psycopg[binary]>=3.2,<4.0
pydantic-settings>=2.5,<3.0
alembic>=1.13,<2.0
pytest>=8.0,<9.0
httpx>=0.27,<1.0
'@

$files["Dockerfile"] = @'
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY tests ./tests

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
'@

$files["docker-compose.yml"] = @'
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: gridops-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-gridops}
      POSTGRES_USER: ${POSTGRES_USER:-gridops}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-gridops_dev_only}
    ports:
      - "5432:5432"
    volumes:
      - gridops_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-gridops} -d ${POSTGRES_DB:-gridops}"]
      interval: 5s
      timeout: 5s
      retries: 10

  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: gridops-api
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

volumes:
  gridops_postgres_data:
'@

$files["backend/__init__.py"] = ""
$files["backend/app/__init__.py"] = ""
$files["backend/app/main.py"] = @'
from fastapi import FastAPI
from sqlalchemy import text

from backend.app.database import engine

app = FastAPI(
    title="GridOps Intelligence API",
    description="Synthetic utility asset intelligence and decision-support platform.",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Basic process health check."""
    return {"status": "ok", "service": "gridops-api"}


@app.get("/health/db", tags=["health"])
def database_health() -> dict[str, str]:
    """Verify that the API can reach PostgreSQL."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
'@

$files["backend/app/database.py"] = @'
import os

from sqlalchemy import create_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://gridops:gridops_dev_only@localhost:5432/gridops",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
'@

$files["tests/test_health.py"] = @'
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "gridops-api"}
'@

$files["README.md"] = @'
# GridOps Intelligence

Explainable AI and predictive maintenance platform combining classical machine learning, retrieval-augmented generation (RAG), utility asset risk intelligence, and human-in-the-loop decision support.

> **Project status:** Initial development scaffold. This is an independent portfolio project using synthetic data only. It is not a DTE system, is not connected to utility operational systems, and does not make real maintenance decisions.

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

5. Open API documentation:

   http://localhost:8000/docs

## Run tests locally

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
```

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
'@

$files["IMPLEMENTATION_PLAN.md"] = @'
# Implementation Plan

## Current milestone: Phase 1 foundation

- [x] Create initial project structure and API health endpoint.
- [x] Add Docker Compose with PostgreSQL + pgvector.
- [x] Add a minimal automated API test.
- [ ] Verify Docker build and service startup.
- [ ] Add SQLAlchemy models and Alembic migrations.
- [ ] Generate reproducible synthetic utility datasets.
- [ ] Implement validated, idempotent ETL ingestion.
- [ ] Add data-quality checks and reports.
- [ ] Add unit and integration tests for ingestion and persistence.

## Engineering rules

- Synthetic data only; no employer-confidential information.
- Keep model training and evaluation free of target leakage.
- Make ingestion repeatable and observable.
- Test each milestone before expanding scope.
- Do not describe planned or simulated functionality as implemented or production-deployed.
'@

$files["ARCHITECTURE.md"] = @'
# Architecture

## Initial runtime

```text
Windows 11
  |
  +-- Docker Desktop (Linux containers)
        |
        +-- FastAPI service :8000
        |     +-- /health
        |     +-- /health/db
        |
        +-- PostgreSQL 16 + pgvector :5432
              +-- persistent Docker volume
```

## Planned data flow

Synthetic source data -> validation -> transformation -> PostgreSQL -> feature engineering -> ML risk scoring -> evidence retrieval -> grounded recommendation -> human review -> audit event.

The planned workflow is decision support only. It will not autonomously execute maintenance actions.

## Planned boundaries

- `backend/`: API, configuration, database access, and domain services.
- `data_engineering/`: synthetic data generation, ingestion, transformations, and quality checks.
- `ml/`: features, training, evaluation, inference, and explainability.
- `rag/`: document ingestion, embeddings, retrieval, reranking, and generation.
- `frontend/`: operational dashboard.
- `tests/`: unit, integration, and evaluation tests.
- `infra/`: container and deployment configuration.
- `docs/`: data dictionary, design decisions, and operating guides.
'@

$files[".dockerignore"] = @'
.git
.venv
__pycache__
.pytest_cache
.ruff_cache
.env
data/generated
data/processed
models
node_modules
'@

$directories = @(
    "backend/app",
    "data_engineering/generators",
    "data_engineering/etl",
    "data_engineering/quality",
    "ml/features",
    "ml/training",
    "ml/evaluation",
    "rag/ingestion",
    "rag/retrieval",
    "frontend",
    "tests",
    "infra",
    "docs",
    "scripts",
    "data/raw",
    "data/generated"
)

foreach ($directory in $directories) {
    $fullPath = Join-Path $ProjectPath $directory
    New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
}

$created = @()
$skipped = @()

foreach ($entry in $files.GetEnumerator()) {
    $path = Join-Path $ProjectPath $entry.Key
    if (Test-Path -LiteralPath $path) {
        $skipped += $entry.Key
        continue
    }

    $parent = Split-Path -Parent $path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    Set-Content -LiteralPath $path -Value $entry.Value -Encoding utf8
    $created += $entry.Key
}

Write-Host "`nCreated files:" -ForegroundColor Green
$created | ForEach-Object { Write-Host "  + $_" }

if ($skipped.Count -gt 0) {
    Write-Host "`nSkipped existing files (not overwritten):" -ForegroundColor Yellow
    $skipped | ForEach-Object { Write-Host "  - $_" }
}

Write-Host "`nBootstrap complete. No Git repository, GitHub remote, or published content was created." -ForegroundColor Cyan
Write-Host "Next: Copy-Item .env.example .env; then docker compose up --build -d"
