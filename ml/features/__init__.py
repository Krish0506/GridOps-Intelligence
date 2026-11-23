"""Leakage-safe feature engineering for GridOps Intelligence (Milestone 2A).

Public API
----------
``build_asset_feature_record`` / ``build_asset_feature_records``
    Compose every feature group at one explicit prediction cutoff.
``telemetry_features``, ``maintenance_features``, ``inspection_features``,
``weather_features``, ``static_asset_features``, ``quality_features``
    Independently testable feature groups.
``classify_outcome``
    Three-state outcome labelling that keeps censored assets unknown.
``build_training_cohort`` / ``trainable_outcomes``
    Safe training-cohort construction: unknown rows are excluded and a binary
    cohort is refused when no confirmed negatives exist.
``build_feature_records_for_assets``
    Batched database path with a constant number of queries.

All functions are deterministic and treat the prediction cutoff as an
exclusive upper bound.

Model-feature contract
----------------------
``model_feature_names`` / ``numeric_feature_names`` / ``boolean_feature_names`` /
``categorical_feature_names`` are the only advertised model inputs.  Identifiers,
metadata, timestamps, cutoffs, event bounds, and label attributes are excluded.
"""

from __future__ import annotations

from ml.features.asset import (
    all_feature_names,
    boolean_feature_names,
    build_asset_feature_record,
    build_asset_feature_records,
    categorical_feature_names,
    identifier_columns,
    metadata_columns,
    model_feature_names,
    numeric_feature_names,
)
from ml.features.cutoff import (
    days_between,
    effective_bound,
    filter_strictly_before,
    filter_window,
    is_strictly_before,
    normalize_timestamp,
    resolve_event_bound,
)
from ml.features.inspection import inspection_feature_names, inspection_features
from ml.features.labels import (
    InsufficientConfirmedNegativesError,
    OutcomeDecision,
    OutcomeLabel,
    TrainingCohort,
    build_training_cohort,
    classify_outcome,
    classify_outcomes,
    trainable_outcomes,
)
from ml.features.maintenance import maintenance_feature_names, maintenance_features
from ml.features.quality import quality_feature_names, quality_features
from ml.features.repository import (
    build_feature_records_for_assets,
    load_assets,
    load_failures,
    load_inspections,
    load_telemetry,
    load_weather,
    load_work_orders,
)
from ml.features.static import static_asset_features, static_feature_names
from ml.features.telemetry import (
    SENSOR_FIELDS,
    SensorStatistics,
    summarize_sensor,
    telemetry_feature_names,
    telemetry_features,
)
from ml.features.types import (
    AssetRecord,
    FailureRecord,
    InspectionRecord,
    TelemetryReading,
    WeatherRecord,
    WorkOrderRecord,
)
from ml.features.weather import weather_feature_names, weather_features

__all__ = [
    "SENSOR_FIELDS",
    "AssetRecord",
    "FailureRecord",
    "InspectionRecord",
    "InsufficientConfirmedNegativesError",
    "OutcomeDecision",
    "OutcomeLabel",
    "SensorStatistics",
    "TelemetryReading",
    "TrainingCohort",
    "WeatherRecord",
    "WorkOrderRecord",
    "all_feature_names",
    "boolean_feature_names",
    "build_asset_feature_record",
    "build_asset_feature_records",
    "build_feature_records_for_assets",
    "build_training_cohort",
    "categorical_feature_names",
    "classify_outcome",
    "classify_outcomes",
    "days_between",
    "effective_bound",
    "filter_strictly_before",
    "filter_window",
    "inspection_feature_names",
    "inspection_features",
    "is_strictly_before",
    "identifier_columns",
    "load_assets",
    "load_failures",
    "load_inspections",
    "load_telemetry",
    "load_weather",
    "load_work_orders",
    "maintenance_feature_names",
    "maintenance_features",
    "metadata_columns",
    "model_feature_names",
    "numeric_feature_names",
    "normalize_timestamp",
    "quality_feature_names",
    "quality_features",
    "static_asset_features",
    "static_feature_names",
    "summarize_sensor",
    "telemetry_feature_names",
    "telemetry_features",
    "trainable_outcomes",
    "weather_feature_names",
    "weather_features",
]
