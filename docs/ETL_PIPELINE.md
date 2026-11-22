# ETL Pipeline

Phase 1B implements the validated, idempotent CSV-to-PostgreSQL ingestion
pipeline under `data_engineering/etl/`.

## Stages

```text
source CSVs (data/generated)
  -> read + validate (RowValidator, QualityTracker, DuplicateTracker)
  -> transform (per-dataset transformers)
  -> load (PostgreSQL upserts with conflict handling)
  -> persist observability (ingestion_runs, dataset results, quality results)
  -> write reports (JSON report + rejected rows)
```

1. **Read**: CSV readers stream source rows with 1-based source row numbers
   (header is row 1).
2. **Validate**: per-dataset checks emit `ERROR` issues that reject a row and
   `WARNING` issues that preserve it. Checks include required fields, identifier
   format, timestamps, numeric ranges, category values, asset references, asset
   types, synthetic markers, and dataset-specific transitions.
3. **Transform**: per-dataset value mappers produce relational row payloads.
4. **Load**: batched PostgreSQL upserts.
   - Telemetry uses deterministic content-hash keys with conflict skip.
   - Registry/detail/event datasets use source keys with conflict-based updates.
5. **Persist**: run, dataset-result, and quality-check rows.
6. **Report**: structured JSON report plus rejected-row JSON file.

## Idempotency

- Telemetry: content-hash primary key; exact duplicates skipped.
- Registry/detail/event datasets: source primary key plus conflict comparison;
  identical conflicts are skipped, changed conflicts are updated.

## Commands

```bash
# Full ingestion into the configured database
python -m data_engineering.etl --input-dir data/generated --batch-size 1000

# Dry run (validate + report, no writes)
python -m data_engineering.etl --dry-run

# Fail fast when validation rejects rows
python -m data_engineering.etl --fail-on-rejected

# Custom report / rejected directories
python -m data_engineering.etl --report-dir data/reports --rejected-dir data/rejected
```

The CLI prints run ID, status, totals, per-dataset summaries, report path, and
rejected path.

## Statuses

- `dry_run`
- `completed`
- `completed_with_rejections`
- `failed`
