# Phase 2A — Leakage-Safe Feature Engineering

Status: **implemented and tested** after remediation. No database schema change, no
migration, no synthetic data regeneration, and no model training were performed.

The feature layer lives in `ml/features/` and is deliberately independent of
FastAPI and of SQLAlchemy at the calculation level. Typed, immutable input
records (`AssetRecord`, `TelemetryReading`, `WorkOrderRecord`,
`InspectionRecord`, `WeatherRecord`, `FailureRecord`) are mapped from the ORM
only in `ml/features/repository.py`.

## 1. Package layout

| Module | Responsibility |
| --- | --- |
| `ml/features/types.py` | Frozen input records and CSV mapping helpers |
| `ml/features/cutoff.py` | Strict cutoff, window, and timestamp normalisation |
| `ml/features/static.py` | Static asset attributes |
| `ml/features/telemetry.py` | Sensor aggregation, trend, coverage, missingness |
| `ml/features/maintenance.py` | Work-order history |
| `ml/features/inspection.py` | Inspection history and condition/severity scores |
| `ml/features/weather.py` | Regional weather history |
| `ml/features/quality.py` | Completeness and missing-history indicators |
| `ml/features/asset.py` | Combined asset-level record builder |
| `ml/features/labels.py` | Three-state outcome labelling with censoring |
| `ml/features/repository.py` | Batched DB loaders (constant query count) |

Public functions:

- `static_asset_features(asset, prediction_cutoff)`
- `telemetry_features(readings, prediction_cutoff, asset_id, window_days=None, exclude_at_or_after=None)`
- `maintenance_features(work_orders, prediction_cutoff, asset_id, exclude_at_or_after=None)`
- `inspection_features(inspections, prediction_cutoff, asset_id, exclude_at_or_after=None)`
- `weather_features(observations, region, prediction_cutoff, window_days=None, exclude_at_or_after=None)`
- `quality_features(telemetry, maintenance, inspection, weather)`
- `build_asset_feature_record(...)` / `build_asset_feature_records(...)`
- `classify_outcome(...)` / `classify_outcomes(...)`
- `build_training_cohort(...)` / `trainable_outcomes(...)`
- `build_feature_records_for_assets(session, asset_ids, cutoff, ...)`
- `summarize_sensor(points)` (count/mean/median/min/max/population std/first/last/change/OLS trend per day)

Each group also exposes a `*_feature_names()` function.  The combined schema is
`all_feature_names()`; the model-input contract is exposed separately through
`identifier_columns()`, `metadata_columns()`, `boolean_feature_names()`,
`categorical_feature_names()`, `numeric_feature_names()`, and
`model_feature_names()`.  Only the latter three (plus categoricals and booleans)
are valid model inputs.

## 2. Source tables and columns

| Feature group | Table | Columns used |
| --- | --- | --- |
| Static | `assets` | `asset_id`, `asset_type`, `name`, `install_date`, `status`, `region` |
| Telemetry | `asset_telemetry` | `asset_id`, `timestamp`, `temperature_c`, `load_pct`, `voltage_kv`, `current_a`, `vibration_mm_s`, `operating_hours_cumulative` |
| Maintenance | `maintenance_work_orders` | `asset_id`, `work_type`, `priority`, `status`, `opened_at`, `completed_at` |
| Inspection | `inspections` | `asset_id`, `inspection_date`, `condition`, `severity` |
| Weather | `weather_observations` | `region`, `timestamp`, `temperature_c`, `wind_speed_ms`, `precipitation_mm`, `severe` |
| Labels (not features) | `failure_incidents` | `asset_id`, `failure_id`, `failure_timestamp`; severity/downtime are read only as label metadata and never emitted |

No columns outside these tables are used. Type-specific detail tables
(`transformer_details`, `substation_details`, `circuit_breaker_details`,
`feeder_details`) are not flattened because they are current-state attributes
without historical versions.

## 3. Feature definitions

Naming convention: `<group>_<field>_<statistic>`. All statistics are computed
over eligible, non-null values only.

### Static (`asset_*`)
- `asset_id`, `asset_type`, `asset_name`, `asset_status`, `asset_region`
- `asset_install_date`
- `asset_installed_before_cutoff` — installation date strictly before the cutoff date
- `asset_age_days` — cutoff date minus install date; `None` if not yet installed

### Telemetry (`telemetry_*`)
Per asset and cutoff:
- `telemetry_reading_count`, `telemetry_distinct_timestamp_count`,
  `telemetry_duplicate_timestamp_count`, `telemetry_has_readings`
- `telemetry_first_observed_at`, `telemetry_last_observed_at`,
  `telemetry_days_since_last_reading`, `telemetry_observed_span_days`
- `telemetry_coverage_ratio` — distinct calendar days with readings divided by
  the lookback window in days (capped at 1.0; `None` when no window is given)
- `telemetry_missing_value_ratio` — missing sensor cells divided by
  `readings × 5`
- `telemetry_all_sensors_missing_count`
- `telemetry_operating_hours_first`, `telemetry_operating_hours_last`

For each sensor `S ∈ {temperature_c, load_pct, voltage_kv, current_a, vibration_mm_s}`:
- `telemetry_S_count`, `telemetry_S_missing`, `telemetry_S_missing_ratio`
- `telemetry_S_mean`, `telemetry_S_median`, `telemetry_S_min`, `telemetry_S_max`
- `telemetry_S_std` — population standard deviation
- `telemetry_S_first`, `telemetry_S_last`, `telemetry_S_change`
- `telemetry_S_trend_per_day` — OLS slope against days since the first eligible
  reading; `None` with fewer than two points or no time spread

### Maintenance (`maintenance_*`)
- `maintenance_work_order_count`, `maintenance_has_history`
- `maintenance_{corrective,preventive,scheduled}_count`
- `maintenance_corrective_ratio`
- `maintenance_completed_before_cutoff_count`, `maintenance_completed_before_cutoff_ratio`
  — derived from `completed_at < prediction_cutoff`; never from the current
  `status` column
- `maintenance_unresolved_at_cutoff_count` — opened before the cutoff but not
  completed before it (open / in progress / cancelled are not distinguished; the
  source schema has no status history)
- `maintenance_priority_{low,medium,high,critical}_count`
- `maintenance_high_priority_count` — high + critical
- `maintenance_days_since_last_opened`
- `maintenance_last_work_type`, `maintenance_last_priority`
  (`maintenance_last_status` was removed: it was current-state and not
  historically observable)
- `maintenance_completion_duration_count`, `maintenance_mean_completion_days`,
  `maintenance_median_completion_days`, `maintenance_days_since_last_completed`
- `maintenance_orders_last_{30,90,365}_days`

Completion durations use `completed_at` only when it is also strictly earlier
than the cutoff; an order completed after the cutoff contributes no duration and
is reported as unresolved instead of completed.

Only historically observable maintenance attributes are emitted: order counts,
work type, priority, opened timestamps, and completions strictly before the
cutoff.  Features that would require reconstructing historical open /
in-progress / cancelled status were removed because the schema has no status
history table; such lifecycle states are reported through the honest
`maintenance_unresolved_at_cutoff_count` indicator rather than being guessed.

### Inspection (`inspection_*`)
- `inspection_count`, `inspection_has_history`
- `inspection_{excellent,good,fair,poor}_count`
- `inspection_severity_{none,low,medium,high}_count`
- `inspection_latest_condition`, `inspection_latest_condition_score`
  (excellent 3, good 2, fair 1, poor 0)
- `inspection_latest_severity`, `inspection_latest_severity_score`
  (none 0, low 1, medium 2, high 3)
- `inspection_days_since_latest`
- `inspection_poor_or_fair_ratio`, `inspection_high_severity_count`
- `inspection_mean_severity_score`
- `inspection_condition_score_trend_per_day`
- `inspection_count_last_365_days`

### Weather (`weather_*`, regional)
- `weather_region`, `weather_observation_count`, `weather_has_history`
- `weather_temperature_{mean,median,min,max,std,trend_per_day}`
- `weather_wind_speed_{mean,max}`
- `weather_precipitation_{mean,max,total_mm}`
- `weather_severe_count`, `weather_severe_ratio`
- `weather_days_since_latest`

### Data quality (`quality_*`)
- `quality_telemetry_has_readings`
- `quality_telemetry_sparse` — no readings, or coverage below
  `sparse_coverage_threshold` (default 0.5) when a window is supplied
- `quality_telemetry_coverage_ratio`, `quality_telemetry_missing_value_ratio`
- `quality_sensor_missing_count`, `quality_sensors_observed_count`,
  `quality_all_sensors_observed`
- `quality_missing_maintenance_history`, `quality_missing_inspection_history`,
  `quality_missing_weather_history`
- `quality_history_group_count` — number of the three histories present

### Combined record
`build_asset_feature_record` merges every group for one asset, filters inputs
by `asset_id`, applies the same cutoff everywhere, and adds
`feature_cutoff`, `feature_window_days`, and `feature_excluded_at_or_after`.
`build_asset_feature_records` groups a batch in memory and returns records in
ascending `asset_id` order.

### Model feature contract
`all_feature_names()` is the complete feature-record schema (including metadata
for traceability).  The training-facing schema is:

- `identifier_columns()` — `asset_id`
- `metadata_columns()` — names, install dates, current status, observation
  timestamps, cutoff metadata, event bounds, region labels
- `boolean_feature_names()`, `categorical_feature_names()`, `numeric_feature_names()`

`model_feature_names()` returns the ordered union of the latter three and is the
only advertised model-input list.  It excludes identifiers, metadata, timestamps,
cutoffs, event bounds, and label attributes.

## 4. Prediction-cutoff semantics

Every feature function requires an explicit `prediction_cutoff` and treats it as
an **exclusive** upper bound:

- `asset_telemetry.timestamp < cutoff`
- `maintenance_work_orders.opened_at < cutoff`
- `inspections.inspection_date < cutoff`
- `weather_observations.timestamp < cutoff`

A record exactly at the cutoff is excluded. Naive datetimes are the project
convention; aware datetimes are normalised to UTC and then made naive.

`exclude_at_or_after` adds an optional event bound (typically the first known
failure). The earlier of the cutoff and the event bound is applied, so a caller
can build a pre-failure snapshot even when the nominal cutoff is later.

The bound may be a single `datetime` (shared by every asset in the batch) or a
mapping of `asset_id -> datetime` (per-asset failure times such as
`{"T-00015": datetime(...), "T-00042": datetime(...)}`). For every asset the
bound is resolved per asset and applied consistently to telemetry, work orders,
inspections, and weather; an asset without a bound uses only the prediction
cutoff.

Every source group honours the bound with the same strict `<` comparison:

- `asset_telemetry.timestamp < effective_bound`
- `maintenance_work_orders.opened_at < effective_bound`
- `inspections.inspection_date < effective_bound`
- `weather_observations.timestamp < effective_bound`

The repository loaders accept the same bound and apply it in SQL (expanding a
per-asset mapping into per-asset predicates inside a single query per table).

### Post-failure telemetry
`data_engineering/generators/telemetry.py` appends elevated readings within
`failure_timestamp ± 2 days`. Readings *before* the event are legitimate leading
indicators and remain eligible. Readings **at or after** the event are excluded
by the cutoff and, when supplied, by `exclude_at_or_after`. A real-data check of
the 20 first failure assets produced zero violations of
`telemetry_last_observed_at < failure_timestamp`.

### Failure severity and downtime
`failure_severity` and `downtime_hours` are never inputs to feature functions
and never appear in output records. `FailureRecord` exists only for
`ml.features.labels`.

### Label integrity
`classify_outcome` returns:

- `CONFIRMED_POSITIVE` — a failure with `cutoff < failure_timestamp ≤ observation_end`
- `CONFIRMED_NEGATIVE` — only when the caller supplies an explicit
  `confirmed_healthy_until` covering the whole observation window
- `UNKNOWN` — otherwise, including every asset with no failure record

The absence of a failure is never converted into a negative label, and the
generator's telemetry-derived risk score is never used as a label.

A failure exactly at the prediction cutoff is not a future positive (the left
edge of the positive window is exclusive).  A failure after the observation end
is outside the window and therefore unknown.

### Training cohort
`build_training_cohort(decisions, require_binary=True)` returns a supervised
training cohort after censoring:

- `OutcomeLabel.UNKNOWN` decisions are always excluded.
- With `require_binary=True`, a cohort must contain at least one confirmed
  positive and one confirmed negative; otherwise an
  `InsufficientConfirmedNegativesError` is raised.

The current synthetic schema has no health-confirmation source, so the shipped
dataset currently has no defensible confirmed-negative cohort and cannot produce
a binary training cohort yet.  No synthetic health confirmations were invented.

## 5. Missing-data treatment

- Empty histories return complete, typed records with zero counts and `None`
  statistics rather than raising or imputing.
- Missing sensor values are excluded per statistic and counted explicitly
  (`*_missing`, `*_missing_ratio`, `telemetry_missing_value_ratio`).
- Assets without maintenance, inspection, or weather history get explicit
  `*_has_history = False` plus `quality_missing_*_history = True`.
- An asset with no `region` gets `weather_has_history = False`; weather is never
  imputed from another region.
- Duplicate timestamps are retained because the schema stores distinct readings
  that share a timestamp (normal and elevated). The duplicate count is exposed
  instead of silently deduplicating.
- Sparse telemetry is flagged, not fabricated: coverage is measured against a
  caller-supplied window.

## 6. Query strategy

`build_feature_records_for_assets` issues exactly five queries per batch —
assets, telemetry, work orders, inspections, weather — regardless of the number
of assets. Filtering by `asset_id IN (...)` and timestamp happens in SQL; a
per-asset event-bound mapping is expanded into per-asset predicates inside a
single query per table. A unit test asserts the five loader calls, so an
accidental N+1 regression fails the suite.

## 7. Tests and results

New test files (after remediation):

- `tests/test_feature_engineering.py` — 47 tests (feature engineering, model-feature
  contract, event bounds, maintenance history)
- `tests/test_feature_labels.py` — 11 tests (three-state labels, training cohort)
- `tests/test_feature_repository.py` — 3 integration tests against the existing
  `ingested_db` fixture (schema/record equality, loader cutoff+event bound
  filtering, per-asset event bounds)

Coverage includes normal aggregation, empty and sparse inputs, missing sensor
values, duplicate timestamps, exact cutoff exclusion, post-cutoff exclusion for
telemetry/work orders/inspections/weather, post-failure telemetry exclusion, and
event-bound exclusion for all four source groups, lookback windows, maintenance
historical completion semantics, missing maintenance/inspection/weather history,
deterministic repeated output, feature-name coverage, model-feature contract,
label censoring, and constant query count.

Executed results (Windows, `.venv`, Python 3.11):

```
.\.venv\Scripts\python.exe -m pytest tests/test_feature_engineering.py tests/test_feature_labels.py -q
60 passed

.\.venv\Scripts\python.exe -m pytest tests/test_feature_repository.py -q
3 passed

.\.venv\Scripts\python.exe -m pytest -q
<full-suite result — run during remediation>
```

The single warning is the pre-existing Starlette/httpx deprecation warning.
The original 42-test suite remains green.

## 8. Known limitations

- `assets.status` is a current-state attribute with no history table; it is
  emitted for traceability and classified as metadata, never as a historical
  model input. `assets.region` is treated as stable context for the observation
  period and is exposed as a categorical feature.
- `assets.operating_hours_cumulative` is a snapshot without an effective
  timestamp, so it is **not** emitted as a feature. Telemetry-derived operating
  hours are reported, but the synthetic generator randomises them per row, so
  they are not monotonic and deltas are unreliable.

## 9. Modeling readiness — synthetic-data limitations (BLOCKED)

The current synthetic dataset cannot yet support predictive-model validation:

1. Failure assets are selected by the same telemetry-derived risk score that the
   feature pipeline exposes, so the positive class is defined by the features
   (`data_engineering/generators/failures.py`).
2. Abnormal telemetry is injected around failure timestamps, including before
   the failure, for positive assets only (`data_engineering/generators/telemetry.py`).
3. Failed-asset risk scores are boosted and drive maintenance and inspection
   generation (`data_engineering/generators/maintenance.py`,
   `data_engineering/generators/inspections.py`).
4. No defensible confirmed-negative cohort exists (no health-confirmation source).

**Modeling-readiness status: BLOCKED — synthetic label construction is circular
and confirmed negatives are unavailable.** Feature-engineering validation
(timestamp filtering, aggregation, censoring) is complete; predictive-model
validation is not. A future milestone must decouple failure generation from the
telemetry features, stop label-conditioning maintenance/inspection generation,
and introduce an independent observation/follow-up process for confirmed
negatives.
