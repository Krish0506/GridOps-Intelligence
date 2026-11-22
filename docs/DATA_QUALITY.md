# Data Quality

Phase 1B records data-quality results for every ingestion run.

## Checks

| Check | Severity | Applies to | Meaning |
| --- | --- | --- | --- |
| identifier_format | ERROR | all datasets | Identifier matches expected pattern. |
| required_field_completeness | ERROR | all datasets | Required fields are present. |
| timestamp_format | ERROR | all datasets | Timestamps parse and stay within reference bounds. |
| numeric_ranges | ERROR | all datasets | Numeric values within configured ranges. |
| category_values | ERROR | all datasets | Enum values are expected. |
| valid_asset_references | ERROR | all datasets | Referenced assets exist. |
| valid_asset_types | ERROR | all datasets | Referenced asset type is expected. |
| synthetic_marker_presence | ERROR | all datasets | Rows are marked synthetic. |
| asset_id_uniqueness | WARNING | assets | Identifier uniqueness warning. |
| duplicate_detection | WARNING | telemetry/events | Exact duplicate source records skipped. |
| telemetry_completeness | WARNING | telemetry | Optional sensor cells may be intentionally empty. |
| work_order_status_transitions | ERROR | work orders | Status transitions are coherent. |
| completed_at_order | ERROR | work orders | Completion is not before opening. |
| failure_severity | ERROR | failures | Severity within 1-5. |

## Outcomes

- `ERROR` issues reject the source row (and are recorded in the rejected report).
- `WARNING` issues preserve the row (for example, intentional missing telemetry
  sensors or exact source duplicates).

## Observed Phase 1B results (synthetic bundle)

- Full ingestion: validation errors 0, warnings 12 (source duplicates).
- Telemetry completeness warning: 764 intentionally missing sensor cells.
- Rejected rows: 0 for the clean synthetic bundle.
- Failed/invalid-row paths are covered by integration tests with forced defects.

## Persistence

Quality results are stored per run and dataset in `data_quality_results` and
returned through `GET /api/v1/ingestion/runs/{run_id}`.
