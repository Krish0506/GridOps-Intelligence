"""Read-only query helpers used by the GridOps Intelligence API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from backend.app.models import (
    Asset,
    AssetTelemetry,
    FailureIncident,
    IngestionRun,
    MaintenanceWorkOrder,
)


def _paginate(
    statement: Any, session: Session, *, limit: int, offset: int
) -> tuple[list[Any], int]:
    total = int(
        session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    )
    rows = session.execute(statement.offset(offset).limit(limit)).scalars().all()
    return list(rows), total


def count_assets(
    session: Session,
    *,
    asset_type: str | None = None,
    status: str | None = None,
    region: str | None = None,
) -> int:
    """Count assets matching the supplied filters."""
    statement = select(Asset)
    if asset_type is not None:
        statement = statement.where(Asset.asset_type == asset_type)
    if status is not None:
        statement = statement.where(Asset.status == status)
    if region is not None:
        statement = statement.where(Asset.region == region)
    return int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)


def list_assets(
    session: Session,
    *,
    asset_type: str | None = None,
    status: str | None = None,
    region: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Asset], int]:
    """List assets with optional filters and pagination."""
    statement = select(Asset)
    if asset_type is not None:
        statement = statement.where(Asset.asset_type == asset_type)
    if status is not None:
        statement = statement.where(Asset.status == status)
    if region is not None:
        statement = statement.where(Asset.region == region)
    rows, total = _paginate(statement, session, limit=limit, offset=offset)
    return rows, total


def get_asset(session: Session, asset_id: str) -> Asset | None:
    """Return one asset by identifier."""
    return session.get(Asset, asset_id)


def count_telemetry(
    session: Session,
    asset_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    """Count telemetry rows for one asset, optionally in a time window."""
    statement = select(AssetTelemetry).where(AssetTelemetry.asset_id == asset_id)
    if start is not None:
        statement = statement.where(AssetTelemetry.timestamp >= start)
    if end is not None:
        statement = statement.where(AssetTelemetry.timestamp <= end)
    return int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)


def list_telemetry(
    session: Session,
    asset_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AssetTelemetry], int]:
    """List telemetry rows for one asset with optional window and pagination."""
    statement = select(AssetTelemetry).where(AssetTelemetry.asset_id == asset_id)
    if start is not None:
        statement = statement.where(AssetTelemetry.timestamp >= start)
    if end is not None:
        statement = statement.where(AssetTelemetry.timestamp <= end)
    rows, total = _paginate(statement, session, limit=limit, offset=offset)
    return rows, total


def list_failures(
    session: Session,
    *,
    failure_category: str | None = None,
    failure_severity: int | None = None,
    asset_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FailureIncident], int]:
    """List failure incidents with optional filters and pagination."""
    statement = select(FailureIncident)
    if failure_category is not None:
        statement = statement.where(FailureIncident.failure_category == failure_category)
    if failure_severity is not None:
        statement = statement.where(FailureIncident.failure_severity == failure_severity)
    if asset_id is not None:
        statement = statement.where(FailureIncident.asset_id == asset_id)
    rows, total = _paginate(statement, session, limit=limit, offset=offset)
    return rows, total


def list_work_orders(
    session: Session,
    *,
    work_type: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    asset_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MaintenanceWorkOrder], int]:
    """List maintenance work orders with optional filters and pagination."""
    statement = select(MaintenanceWorkOrder)
    if work_type is not None:
        statement = statement.where(MaintenanceWorkOrder.work_type == work_type)
    if priority is not None:
        statement = statement.where(MaintenanceWorkOrder.priority == priority)
    if status is not None:
        statement = statement.where(MaintenanceWorkOrder.status == status)
    if asset_id is not None:
        statement = statement.where(MaintenanceWorkOrder.asset_id == asset_id)
    rows, total = _paginate(statement, session, limit=limit, offset=offset)
    return rows, total


def list_ingestion_runs(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[IngestionRun], int]:
    """List ingestion runs, newest first, with pagination."""
    statement = select(IngestionRun).order_by(IngestionRun.started_at.desc())
    rows, total = _paginate(statement, session, limit=limit, offset=offset)
    return rows, total


def get_ingestion_run(session: Session, run_id: str) -> IngestionRun | None:
    """Return one ingestion run by identifier."""
    from uuid import UUID

    return session.get(IngestionRun, UUID(run_id))


__all__ = [
    "count_assets",
    "get_asset",
    "get_ingestion_run",
    "list_assets",
    "list_failures",
    "list_ingestion_runs",
    "list_telemetry",
    "list_work_orders",
]
