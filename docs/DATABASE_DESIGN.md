# Database Design

Phase 1B adds the relational PostgreSQL schema for the synthetic utility data
foundation. The design uses a unified `assets` table with type-specific detail
tables and a telemetry/event fact schema, all managed by Alembic revision
`04b9afe7bc6a`.

## Runtime topology

```text
Windows 11
  |
  +-- Docker Desktop (Linux containers)
  |     +-- FastAPI service :8000
  |     |     +-- /health
  |     |     +-- /health/db
  |     |     +-- /api/v1/assets
  |     |     +-- /api/v1/telemetry/{asset_id}
  |     |     +-- /api/v1/failures
  |     |     +-- /api/v1/work-orders
  |     |     +-- /api/v1/ingestion/runs
  |     |     +-- /api/v1/ingestion/runs/{run_id}
  |     +-- PostgreSQL 16 + pgvector :5432
  |           +-- persistent Docker volume
```

The local host database is reached through the Docker-published port. Because a
native PostgreSQL instance may already occupy the default port, the compose file
publishes the container port as `55432:5432`; the host-side connection therefore
uses port `55432` while container-internal traffic keeps using the service name
`db` on `5432`.

## Core tables

### `assets` (unified asset registry)

Single table for transformers, substations, circuit breakers, and feeders.

- Primary key: `asset_id`
- Check constraints: `asset_type` in allowed set, `status` in `{active, retired}`,
  `operating_hours_cumulative` null-or-non-negative.
- Index: `(asset_type, status)`

### Detail tables

Each type-specific detail table references its parent through the shared
`asset_id` primary key of `assets` (FK with `ON DELETE CASCADE`).

- `transformer_details(asset_id, substation_id, winding_type, rating_mva, primary_kv, secondary_kv)`
- `substation_details(asset_id, nominal_kv, area_sq_mi, equipment_count)`
- `circuit_breaker_details(asset_id, substation_id, panel_id, rated_current_a, voltage_class)`
- `feeder_details(asset_id, substation_id, voltage_kv, capacity_kva, length_km, outage_count)`

### Fact tables

- `asset_telemetry(telemetry_id, asset_id FK -> assets, asset_type, timestamp,
  temperature_c, load_pct, voltage_kv, current_a, vibration_mm_s,
  operating_hours_cumulative, synthetic)`
  - Primary key: content-hash-derived `telemetry_id`
  - FKs: `asset_id -> assets.asset_id` with `ON DELETE CASCADE`
  - Indexes: `(asset_id, timestamp)`, `(timestamp)`
- `maintenance_work_orders(work_order_id, asset_id FK -> assets, work_type,
  priority, status, opened_at, completed_at, synthetic)`
  - Primary key: `work_order_id`; FKs: `asset_id -> assets`
  - Check: `priority`, `status`, `work_type` enumerations; completion not before opening.
- `inspections(inspection_id, asset_id FK -> assets, inspection_date, condition,
  findings, severity, synthetic)`
- `failure_incidents(failure_id, asset_id FK -> assets, failure_category,
  failure_timestamp, failure_severity, downtime_hours, synthetic)`
- `weather_observations(weather_id, region, timestamp, temperature_c, wind_speed_ms,
  precipitation_mm, severe, synthetic)`

### Observability tables

- `ingestion_runs(run_id PK, source_name, started_at, completed_at, status,
  dry_run, rows_read, rows_inserted, rows_updated, rows_skipped, rows_rejected,
  error_summary, report_path)`
- `ingestion_dataset_results(id PK, run_id FK -> ingestion_runs, source_name,
  started_at, completed_at, status, dry_run, rows_read, rows_inserted,
  rows_updated, rows_skipped, rows_rejected, error_summary, report_path)`
- `data_quality_results(result_id PK, run_id FK -> ingestion_runs,
  dataset_name, check_name, severity, records_checked, records_passed,
  records_failed, details, created_at)`

## Relationships

- `assets.asset_id` <- detail tables and fact tables (one-to-many by asset type).
- `ingestion_dataset_results` and `data_quality_results` belong to one
  `ingestion_runs` row (`ON DELETE CASCADE`).

## Migration

- Revision: `04b9afe7bc6a`
- Down revision: `None` (initial schema)
- Status: head of the migration chain
- The upgrade enables the pgvector extension
  (`CREATE EXTENSION IF NOT EXISTS vector`) and creates all operational tables
  with FKs, checks, and indexes in one revision.

## Operational notes

- The API is read-only; no write endpoints exist under `/api/v1`.
- The database URL is resolved by the ETL configuration and the backend settings;
  credentials are never printed in reports or API payloads.
- Tests use a dedicated `gridops_test` database (and a separate
  `gridops_migration_scratch` database for reversible migration checks) so the
  development database is never reset or truncated by the suite.
