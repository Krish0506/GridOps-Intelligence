# Data Dictionary

Phase 1B documents the synthetic source fields and their relational target
columns for the initial data foundation.

## Source datasets (`data/generated/`)

### Asset datasets (unified target: `assets` + detail tables)

| Dataset | Source file | Source key | Notes |
| --- | --- | --- | --- |
| transformers | `transformers.csv` | `transformer_id` | Detail in `transformer_details` |
| substations | `substations.csv` | `substation_id` | Detail in `substation_details` |
| circuit breakers | `circuit_breakers.csv` | `breaker_id` | Detail in `circuit_breaker_details` |
| feeders | `feeders.csv` | `feeder_id` | Detail in `feeder_details` |

Shared asset columns across all four datasets: `asset_type`, `name`,
`install_date`, `operating_hours_cumulative`, `status`, `synthetic`.

Type-specific columns: `substation_id` plus type attributes (for example
`winding_type`, `rating_mva`, `primary_kv`, `secondary_kv` for transformers).

### Telemetry

`asset_telemetry.csv`: `asset_id`, `asset_type`, `timestamp`,
`temperature_c`, `load_pct`, `voltage_kv`, `current_a`, `vibration_mm_s`,
`operating_hours_cumulative`, `synthetic`.

### Events

- `work_orders.csv`: `work_order_id`, `asset_ref`, `work_type`, `priority`,
  `status`, `opened_at`, `completed_at`, `synthetic`.
- `inspections.csv`: `inspection_id`, `inspection_date`, `asset_ref`, `condition`,
  `findings`, `severity`, `synthetic`.
- `failures.csv`: `failure_id`, `asset_ref`, `failure_category`,
  `failure_timestamp`, `failure_severity`, `downtime_hours`, `synthetic`.
- `weather.csv`: `weather_id`, `region`, `timestamp`, `temperature_c`,
  `wind_speed_ms`, `precipitation_mm`, `severe`, `synthetic`.

## Target mapping highlights

- Asset registry: source identifiers become `asset_id` values.
- Details: detail rows are keyed by the parent `asset_id`.
- Telemetry: `telemetry_id` is a deterministic SHA-256 content hash of the
  normalized reading; exact duplicates are skipped.
- Events: source identifiers (for example `work_order_id`) are used as primary
  keys with conflict-based upsert semantics.

## Observability payloads

- Ingestion report: run status, totals, per-dataset results, database row counts,
  rejected count, error summary, report path.
- Rejected-row record: dataset, source file, source row, identifier, field, check,
  severity, reason.
- Quality check result: dataset, check name, severity, records checked/passed/failed,
  failure rate, samples.
