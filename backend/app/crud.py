"""Read-only query helpers used by the GridOps Intelligence API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
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
    search: str | None = None,
    sort_by: str = "asset_id",
    sort_dir: str = "asc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Asset], int]:
    """List assets with global search, filters, sorting, and pagination.

    ``region="__unassigned__"`` selects assets whose region is NULL; a blank
    region string is treated as "no filter" rather than as a literal empty
    value.
    """
    statement = select(Asset)
    if asset_type and asset_type.strip():
        statement = statement.where(Asset.asset_type == asset_type.strip())
    if status and status.strip():
        statement = statement.where(Asset.status == status.strip())
    if region and region.strip():
        region_value = region.strip()
        if region_value.lower() in {"__unassigned__", "unassigned", "none", "null"}:
            statement = statement.where(Asset.region.is_(None))
        else:
            statement = statement.where(Asset.region == region_value)
    if search is not None and search.strip():
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Asset.asset_id.ilike(term),
                Asset.name.ilike(term),
                Asset.region.ilike(term),
            )
        )

    sort_columns = {
        "asset_id": Asset.asset_id,
        "asset_type": Asset.asset_type,
        "name": Asset.name,
        "status": Asset.status,
        "region": Asset.region,
        "install_date": Asset.install_date,
        "operating_hours_cumulative": Asset.operating_hours_cumulative,
    }
    column = sort_columns.get(sort_by, Asset.asset_id)
    statement = statement.order_by(column.desc() if sort_dir.lower() == "desc" else column.asc())
    rows, total = _paginate(statement, session, limit=limit, offset=offset)
    return rows, total


def asset_filter_options(session: Session) -> dict[str, object]:
    """Return the actual filter values present in the asset dimension."""
    by_type = [
        {"value": value, "label": value.replace("_", " ").title(), "count": count}
        for value, count in session.execute(
            select(Asset.asset_type, func.count())
            .group_by(Asset.asset_type)
            .order_by(Asset.asset_type)
        )
    ]
    by_status = [
        {"value": value, "label": value.title(), "count": count}
        for value, count in session.execute(
            select(Asset.status, func.count()).group_by(Asset.status).order_by(Asset.status)
        )
    ]
    by_region = [
        {
            "value": "__unassigned__" if region is None else region,
            "label": "Unassigned" if region is None else region,
            "count": count,
        }
        for region, count in session.execute(
            select(Asset.region, func.count())
            .group_by(Asset.region)
            .order_by(func.coalesce(Asset.region, "zzz"))
        )
    ]
    return {"asset_types": by_type, "statuses": by_status, "regions": by_region}


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


def list_risk_records(
    session: Session,
    *,
    asset_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Any], int]:
    from backend.app.models import RiskRecord

    statement = select(RiskRecord)
    if asset_id is not None:
        statement = statement.where(RiskRecord.asset_id == asset_id)
    statement = statement.order_by(RiskRecord.id)
    rows, total = _paginate(statement, session, limit=limit, offset=offset)
    return rows, total


__all__ = [
    "asset_filter_options",
    "count_assets",
    "get_asset",
    "get_ingestion_run",
    "list_assets",
    "list_failures",
    "list_ingestion_runs",
    "list_risk_records",
    "list_telemetry",
    "list_work_orders",
]
