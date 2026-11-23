"""Combined asset-level feature records.

This module is the public entry point for building a deterministic feature
vector for one asset or a batch of assets.  It composes the static, telemetry,
maintenance, inspection, weather, and data-quality groups, all evaluated at the
same explicit prediction cutoff.

No failure labels, severity values, downtime values, or generator risk scores
are read here.  Labels are handled separately by :mod:`ml.features.labels`.

Event bounds
------------
``exclude_at_or_after`` accepts either a single ``datetime`` (shared by every
asset in the batch) or a mapping of ``asset_id -> datetime`` (per-asset event
times such as the first known failure for each asset).  The bound is applied to
telemetry, work orders, inspections, and weather consistently, and the earlier
of the prediction cutoff and the event bound is always used.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime

from ml.features.cutoff import normalize_timestamp, resolve_event_bound
from ml.features.inspection import inspection_feature_names, inspection_features
from ml.features.maintenance import maintenance_feature_names, maintenance_features
from ml.features.quality import quality_feature_names, quality_features
from ml.features.static import static_asset_features, static_feature_names
from ml.features.telemetry import telemetry_feature_names, telemetry_features
from ml.features.types import (
    AssetRecord,
    EventBound,
    InspectionRecord,
    TelemetryReading,
    WeatherRecord,
    WorkOrderRecord,
)
from ml.features.weather import weather_feature_names, weather_features


def build_asset_feature_record(
    asset: AssetRecord,
    telemetry_readings: Iterable[TelemetryReading] = (),
    work_orders: Iterable[WorkOrderRecord] = (),
    inspections: Iterable[InspectionRecord] = (),
    weather_observations: Iterable[WeatherRecord] = (),
    prediction_cutoff: datetime | None = None,
    window_days: int | float | None = None,
    exclude_at_or_after: EventBound = None,
) -> dict[str, object]:
    """Build one asset feature record at ``prediction_cutoff``.

    Inputs may contain records for other assets; they are filtered by
    ``asset.asset_id``.  ``prediction_cutoff`` is required in practice but is
    keyword-optional so callers get a clear error rather than a silent default.

    ``exclude_at_or_after`` may be a single datetime or a mapping of
    ``asset_id -> datetime``; it is resolved to this asset's event bound before
    being applied to every source group.
    """
    if prediction_cutoff is None:
        raise ValueError("prediction_cutoff is required")

    cutoff = normalize_timestamp(prediction_cutoff)
    asset_id = asset.asset_id
    event_bound = resolve_event_bound(exclude_at_or_after, asset_id)

    asset_telemetry = [reading for reading in telemetry_readings if reading.asset_id == asset_id]
    asset_orders = [order for order in work_orders if order.asset_id == asset_id]
    asset_inspections = [inspection for inspection in inspections if inspection.asset_id == asset_id]
    # Weather is regional; the asset's region is applied inside weather_features.
    regional_weather = list(weather_observations)

    telemetry_group = telemetry_features(
        asset_telemetry,
        cutoff,
        asset_id=asset_id,
        window_days=window_days,
        exclude_at_or_after=event_bound,
    )
    maintenance_group = maintenance_features(
        asset_orders, cutoff, asset_id=asset_id, exclude_at_or_after=event_bound
    )
    inspection_group = inspection_features(
        asset_inspections, cutoff, asset_id=asset_id, exclude_at_or_after=event_bound
    )
    weather_group = weather_features(
        regional_weather, asset.region, cutoff, window_days=window_days, exclude_at_or_after=event_bound
    )
    quality_group = quality_features(
        telemetry_group, maintenance_group, inspection_group, weather_group
    )

    record: dict[str, object] = {}
    record.update(static_asset_features(asset, cutoff))
    record.update(telemetry_group)
    record.update(maintenance_group)
    record.update(inspection_group)
    record.update(weather_group)
    record.update(quality_group)
    record["feature_cutoff"] = cutoff
    record["feature_window_days"] = window_days
    record["feature_excluded_at_or_after"] = (
        None if event_bound is None else normalize_timestamp(event_bound)
    )
    return record


def build_asset_feature_records(
    assets: Iterable[AssetRecord],
    telemetry_readings: Iterable[TelemetryReading] = (),
    work_orders: Iterable[WorkOrderRecord] = (),
    inspections: Iterable[InspectionRecord] = (),
    weather_observations: Iterable[WeatherRecord] = (),
    prediction_cutoff: datetime | None = None,
    window_days: int | float | None = None,
    exclude_at_or_after: EventBound = None,
) -> list[dict[str, object]]:
    """Build feature records for many assets in one pass.

    Records are grouped in memory by ``asset_id`` so the cost is linear in the
    number of input rows.  Output order follows ascending ``asset_id``, which
    makes repeated runs deterministic.

    ``exclude_at_or_after`` may be a single datetime or a mapping of
    ``asset_id -> datetime``; the mapping form is resolved per asset so that one
    asset's failure time never truncates another's history.
    """
    if prediction_cutoff is None:
        raise ValueError("prediction_cutoff is required")

    asset_list = sorted(assets, key=lambda asset: asset.asset_id)

    telemetry_by_asset: dict[str, list[TelemetryReading]] = defaultdict(list)
    for reading in telemetry_readings:
        telemetry_by_asset[reading.asset_id].append(reading)

    orders_by_asset: dict[str, list[WorkOrderRecord]] = defaultdict(list)
    for order in work_orders:
        orders_by_asset[order.asset_id].append(order)

    inspections_by_asset: dict[str, list[InspectionRecord]] = defaultdict(list)
    for inspection in inspections:
        inspections_by_asset[inspection.asset_id].append(inspection)

    weather_rows = list(weather_observations)

    return [
        build_asset_feature_record(
            asset,
            telemetry_readings=telemetry_by_asset.get(asset.asset_id, ()),
            work_orders=orders_by_asset.get(asset.asset_id, ()),
            inspections=inspections_by_asset.get(asset.asset_id, ()),
            weather_observations=weather_rows,
            prediction_cutoff=prediction_cutoff,
            window_days=window_days,
            exclude_at_or_after=exclude_at_or_after,
        )
        for asset in asset_list
    ]


def all_feature_names() -> list[str]:
    """Ordered names of every feature produced by the combined builder."""
    names: list[str] = []
    for group in (
        static_feature_names(),
        telemetry_feature_names(),
        maintenance_feature_names(),
        inspection_feature_names(),
        weather_feature_names(),
        quality_feature_names(),
    ):
        for name in group:
            if name not in names:
                names.append(name)
    names.extend(
        [
            "feature_cutoff",
            "feature_window_days",
            "feature_excluded_at_or_after",
        ]
    )
    return names


def identifier_columns() -> list[str]:
    """Columns that identify an asset or a record; never model inputs."""
    return ["asset_id"]


def metadata_columns() -> list[str]:
    """Traceability / provenance columns excluded from the model feature list.

    These include asset identifiers beyond ``asset_id``, display names, install
    dates, current-state status, observation timestamps, cutoff metadata, and the
    caller-supplied event bound.  They remain available on the feature record for
    auditability but must never be fed to a model.
    """
    return [
        "asset_name",
        "asset_install_date",
        "asset_status",
        "telemetry_first_observed_at",
        "telemetry_last_observed_at",
        "feature_cutoff",
        "feature_window_days",
        "feature_excluded_at_or_after",
        "weather_region",
    ]


def boolean_feature_names() -> list[str]:
    """Ordered boolean features in the combined record."""
    return [
        "asset_installed_before_cutoff",
        "telemetry_has_readings",
        "maintenance_has_history",
        "inspection_has_history",
        "weather_has_history",
        "quality_telemetry_has_readings",
        "quality_telemetry_sparse",
        "quality_all_sensors_observed",
        "quality_missing_maintenance_history",
        "quality_missing_inspection_history",
        "quality_missing_weather_history",
    ]


def categorical_feature_names() -> list[str]:
    """Ordered categorical (labelled) features in the combined record."""
    return [
        "asset_type",
        "asset_region",
        "maintenance_last_work_type",
        "maintenance_last_priority",
        "inspection_latest_condition",
        "inspection_latest_severity",
    ]


def numeric_feature_names() -> list[str]:
    """Ordered numeric features in the combined record.

    This is the model-input list derived from the full record schema after
    removing identifiers, metadata, booleans, and categoricals.  Event
    timestamps, observation timestamps, cutoffs, and event bounds never appear.
    """
    excluded = set(identifier_columns()) | set(metadata_columns()) | set(boolean_feature_names()) | set(
        categorical_feature_names()
    )
    names: list[str] = []
    for name in all_feature_names():
        if name in excluded:
            continue
        if name in names:
            continue
        names.append(name)
    return names


def model_feature_names() -> list[str]:
    """Ordered names of the features a downstream training pipeline may use.

    The model feature contract contains numeric, boolean, and categorical
    features only.  Identifiers, metadata, timestamps, cutoffs, event bounds,
    labels, and outcome attributes are excluded.
    """
    names: list[str] = []
    for name in (
        numeric_feature_names()
        + boolean_feature_names()
        + categorical_feature_names()
    ):
        if name not in names:
            names.append(name)
    return names
