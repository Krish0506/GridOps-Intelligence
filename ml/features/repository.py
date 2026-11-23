"""Batched database loaders for feature engineering.

The loaders execute one query per source table for a whole batch of assets, so
building features for *N* assets costs a constant number of queries rather than
*N* queries per table.  All temporal filtering happens in SQL and is repeated in
Python by the feature functions, giving defence in depth against leakage.

The ORM models are imported lazily inside the functions so that importing
:mod:`ml.features` does not require a configured database.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ml.features.asset import build_asset_feature_records
from ml.features.cutoff import effective_bound, normalize_timestamp, resolve_event_bound, window_start
from ml.features.types import (
    AssetRecord,
    EventBound,
    FailureRecord,
    InspectionRecord,
    TelemetryReading,
    WeatherRecord,
    WorkOrderRecord,
)


def _asset_ids(values: Iterable[str]) -> list[str]:
    return sorted(set(values))


def load_assets(session: Session, asset_ids: Iterable[str] | None = None) -> list[AssetRecord]:
    """Load static asset rows, optionally restricted to ``asset_ids``."""
    from backend.app.models import Asset

    statement = select(Asset)
    if asset_ids is not None:
        ids = _asset_ids(asset_ids)
        if not ids:
            return []
        statement = statement.where(Asset.asset_id.in_(ids))
    statement = statement.order_by(Asset.asset_id)

    return [
        AssetRecord(
            asset_id=row.asset_id,
            asset_type=row.asset_type,
            name=row.name,
            install_date=row.install_date,
            status=row.status,
            region=row.region,
            operating_hours_cumulative=row.operating_hours_cumulative,
        )
        for row in session.scalars(statement)
    ]


def load_telemetry(
    session: Session,
    asset_ids: Iterable[str],
    prediction_cutoff: datetime,
    window_days: int | float | None = None,
    exclude_at_or_after: EventBound = None,
) -> list[TelemetryReading]:
    """Load telemetry strictly before the cutoff, in one query.

    ``exclude_at_or_after`` may be a single datetime or a per-asset mapping of
    ``asset_id -> datetime``; when a mapping is supplied the SQL predicate is
    expanded into one asset-scoped condition per asset so a single query per
    batch still applies the correct per-asset event bound.
    """
    from backend.app.models import AssetTelemetry

    ids = _asset_ids(asset_ids)
    if not ids:
        return []
    cutoff = normalize_timestamp(prediction_cutoff)
    statement = select(AssetTelemetry)
    if isinstance(exclude_at_or_after, Mapping):
        statement = statement.where(
            or_(
                *[
                    and_(
                        AssetTelemetry.asset_id == asset_id,
                        AssetTelemetry.timestamp
                        < effective_bound(cutoff, resolve_event_bound(exclude_at_or_after, asset_id)),
                    )
                    for asset_id in ids
                ]
            )
        )
    else:
        bound = effective_bound(cutoff, exclude_at_or_after)
        statement = statement.where(
            AssetTelemetry.asset_id.in_(ids),
            AssetTelemetry.timestamp < bound,
        )
        start = window_start(bound, window_days)
        if start is not None:
            statement = statement.where(AssetTelemetry.timestamp >= start)
    statement = statement.order_by(AssetTelemetry.asset_id, AssetTelemetry.timestamp)

    return [
        TelemetryReading(
            asset_id=row.asset_id,
            timestamp=row.timestamp,
            temperature_c=None if row.temperature_c is None else float(row.temperature_c),
            load_pct=None if row.load_pct is None else float(row.load_pct),
            voltage_kv=None if row.voltage_kv is None else float(row.voltage_kv),
            current_a=None if row.current_a is None else float(row.current_a),
            vibration_mm_s=None if row.vibration_mm_s is None else float(row.vibration_mm_s),
            operating_hours_cumulative=row.operating_hours_cumulative,
        )
        for row in session.scalars(statement)
    ]


def load_work_orders(
    session: Session,
    asset_ids: Iterable[str],
    prediction_cutoff: datetime,
    exclude_at_or_after: EventBound = None,
) -> list[WorkOrderRecord]:
    """Load work orders opened strictly before the cutoff, in one query.

    ``exclude_at_or_after`` may be a single datetime or a per-asset mapping of
    ``asset_id -> datetime``.
    """
    from backend.app.models import MaintenanceWorkOrder

    ids = _asset_ids(asset_ids)
    if not ids:
        return []
    cutoff = normalize_timestamp(prediction_cutoff)
    statement = select(MaintenanceWorkOrder)
    if isinstance(exclude_at_or_after, Mapping):
        statement = statement.where(
            or_(
                *[
                    and_(
                        MaintenanceWorkOrder.asset_id == asset_id,
                        MaintenanceWorkOrder.opened_at
                        < effective_bound(cutoff, resolve_event_bound(exclude_at_or_after, asset_id)),
                    )
                    for asset_id in ids
                ]
            )
        )
    else:
        bound = effective_bound(cutoff, exclude_at_or_after)
        statement = statement.where(
            MaintenanceWorkOrder.asset_id.in_(ids),
            MaintenanceWorkOrder.opened_at < bound,
        )
    statement = statement.order_by(MaintenanceWorkOrder.asset_id, MaintenanceWorkOrder.opened_at)

    return [
        WorkOrderRecord(
            work_order_id=row.work_order_id,
            asset_id=row.asset_id,
            work_type=row.work_type,
            priority=row.priority,
            status=row.status,
            opened_at=row.opened_at,
            completed_at=row.completed_at,
        )
        for row in session.scalars(statement)
    ]


def load_inspections(
    session: Session,
    asset_ids: Iterable[str],
    prediction_cutoff: datetime,
    exclude_at_or_after: EventBound = None,
) -> list[InspectionRecord]:
    """Load inspections dated strictly before the cutoff, in one query.

    ``exclude_at_or_after`` may be a single datetime or a per-asset mapping of
    ``asset_id -> datetime``.
    """
    from backend.app.models import Inspection

    ids = _asset_ids(asset_ids)
    if not ids:
        return []
    cutoff = normalize_timestamp(prediction_cutoff)
    statement = select(Inspection)
    if isinstance(exclude_at_or_after, Mapping):
        statement = statement.where(
            or_(
                *[
                    and_(
                        Inspection.asset_id == asset_id,
                        Inspection.inspection_date
                        < effective_bound(cutoff, resolve_event_bound(exclude_at_or_after, asset_id)),
                    )
                    for asset_id in ids
                ]
            )
        )
    else:
        bound = effective_bound(cutoff, exclude_at_or_after)
        statement = statement.where(
            Inspection.asset_id.in_(ids),
            Inspection.inspection_date < bound,
        )
    statement = statement.order_by(Inspection.asset_id, Inspection.inspection_date)

    return [
        InspectionRecord(
            inspection_id=row.inspection_id,
            asset_id=row.asset_id,
            inspection_date=row.inspection_date,
            condition=row.condition,
            severity=row.severity,
            findings=row.findings,
        )
        for row in session.scalars(statement)
    ]


def load_weather(
    session: Session,
    regions: Iterable[str | None],
    prediction_cutoff: datetime,
    window_days: int | float | None = None,
    exclude_at_or_after: EventBound = None,
) -> list[WeatherRecord]:
    """Load regional weather strictly before the cutoff, in one query.

    ``exclude_at_or_after`` may be a single datetime or a per-asset mapping of
    ``asset_id -> datetime``.  Weather rows are regional rather than
    asset-scoped, so a per-asset mapping is resolved against the single global
    bound here; the asset-scoped builder applies each asset's own event bound.
    """
    from backend.app.models import WeatherObservation

    region_values = sorted({region for region in regions if region is not None})
    if not region_values:
        return []
    cutoff = normalize_timestamp(prediction_cutoff)
    if isinstance(exclude_at_or_after, Mapping):
        bound = effective_bound(cutoff, None)
    else:
        bound = effective_bound(cutoff, exclude_at_or_after)

    statement = select(WeatherObservation).where(
        WeatherObservation.region.in_(region_values),
        WeatherObservation.timestamp < bound,
    )
    start = window_start(bound, window_days)
    if start is not None:
        statement = statement.where(WeatherObservation.timestamp >= start)
    statement = statement.order_by(
        WeatherObservation.region, WeatherObservation.timestamp
    )

    return [
        WeatherRecord(
            weather_id=row.weather_id,
            region=row.region,
            timestamp=row.timestamp,
            temperature_c=float(row.temperature_c),
            wind_speed_ms=float(row.wind_speed_ms),
            precipitation_mm=float(row.precipitation_mm),
            severe=row.severe,
        )
        for row in session.scalars(statement)
    ]


def load_failures(
    session: Session,
    asset_ids: Sequence[str] | None = None,
) -> list[FailureRecord]:
    """Load failure labels for outcome classification (never for features)."""
    from backend.app.models import FailureIncident

    statement = select(FailureIncident)
    if asset_ids is not None:
        ids = _asset_ids(asset_ids)
        if not ids:
            return []
        statement = statement.where(FailureIncident.asset_id.in_(ids))
    statement = statement.order_by(FailureIncident.asset_id, FailureIncident.failure_timestamp)

    return [
        FailureRecord(
            failure_id=row.failure_id,
            asset_id=row.asset_id,
            failure_category=row.failure_category,
            failure_timestamp=row.failure_timestamp,
            failure_severity=row.failure_severity,
            downtime_hours=float(row.downtime_hours),
        )
        for row in session.scalars(statement)
    ]


def build_feature_records_for_assets(
    session: Session,
    asset_ids: Iterable[str],
    prediction_cutoff: datetime,
    window_days: int | float | None = None,
    exclude_at_or_after: EventBound = None,
) -> list[dict[str, object]]:
    """Build combined feature records for a batch using five queries total.

    Query count is independent of the number of assets: assets, telemetry,
    work orders, inspections, and weather are each fetched once.

    ``exclude_at_or_after`` may be a single datetime or a per-asset mapping of
    ``asset_id -> datetime``; when a mapping is supplied the loaders expand the
    event bound into per-asset SQL predicates.
    """
    ids = _asset_ids(asset_ids)
    if not ids:
        return []

    cutoff = normalize_timestamp(prediction_cutoff)
    assets = load_assets(session, ids)
    telemetry = load_telemetry(
        session,
        ids,
        cutoff,
        window_days=window_days,
        exclude_at_or_after=exclude_at_or_after,
    )
    work_orders = load_work_orders(
        session, ids, cutoff, exclude_at_or_after=exclude_at_or_after
    )
    inspections = load_inspections(
        session, ids, cutoff, exclude_at_or_after=exclude_at_or_after
    )
    weather = load_weather(
        session,
        [asset.region for asset in assets],
        cutoff,
        window_days=window_days,
        exclude_at_or_after=exclude_at_or_after,
    )

    return build_asset_feature_records(
        assets,
        telemetry_readings=telemetry,
        work_orders=work_orders,
        inspections=inspections,
        weather_observations=weather,
        prediction_cutoff=cutoff,
        window_days=window_days,
        exclude_at_or_after=exclude_at_or_after,
    )
