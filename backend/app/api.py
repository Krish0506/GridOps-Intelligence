"""Read-only REST API for the GridOps Intelligence backend."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.crud import (
    get_asset,
    get_ingestion_run,
    list_assets,
    list_failures,
    list_ingestion_runs,
    list_telemetry,
    list_work_orders,
)
from backend.app.database import get_db
from backend.app.models import DataQualityResult, IngestionDatasetResult, IngestionRun
from backend.app.schemas import (
    AssetDetailOut,
    AssetOut,
    DataQualityResultOut,
    FailureOut,
    IngestionDatasetResultOut,
    IngestionRunOut,
    Page,
    TelemetryOut,
    WorkOrderOut,
    asset_detail_response,
)

router = APIRouter(prefix="/api/v1")


def _not_found(detail: str) -> JSONResponse:
    """Return a structured 404 response."""
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": detail})


def _run_out(run: IngestionRun) -> IngestionRunOut:
    """Convert an ORM ingestion run plus its persisted results to the API shape."""
    return IngestionRunOut(
        run_id=str(run.run_id),
        source_name=run.source_name,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        dry_run=run.dry_run,
        rows_read=run.rows_read,
        rows_inserted=run.rows_inserted,
        rows_updated=run.rows_updated,
        rows_skipped=run.rows_skipped,
        rows_rejected=run.rows_rejected,
        error_summary=run.error_summary,
        report_path=run.report_path,
        dataset_results=[
            IngestionDatasetResultOut.model_validate(item) for item in run.dataset_results
        ],
        quality_results=[
            DataQualityResultOut(
                result_id=item.result_id,
                run_id=str(item.run_id),
                dataset_name=item.dataset_name,
                check_name=item.check_name,
                severity=item.severity,
                records_checked=item.records_checked,
                records_passed=item.records_passed,
                records_failed=item.records_failed,
                details=item.details,
                created_at=item.created_at,
            )
            for item in run.quality_results
        ],
    )


@router.get("/assets", response_model=Page[AssetOut])
def list_assets_endpoint(
    asset_type: Annotated[str | None, Query(max_length=32)] = None,
    status: Annotated[str | None, Query(max_length=16)] = None,
    region: Annotated[str | None, Query(max_length=8)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_db),
) -> Page[AssetOut]:
    """List assets with optional filters and pagination."""
    assets, total = list_assets(
        session,
        asset_type=asset_type,
        status=status,
        region=region,
        limit=limit,
        offset=offset,
    )
    items = [AssetOut.model_validate(asset) for asset in assets]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/assets/{asset_id}", response_model=AssetDetailOut)
def get_asset_endpoint(
    asset_id: str,
    session: Session = Depends(get_db),
) -> AssetDetailOut:
    """Return one asset and its type-specific detail."""
    asset = get_asset(session, asset_id)
    if asset is None:
        return _not_found("asset not found")
    return asset_detail_response(asset)


@router.get("/telemetry/{asset_id}", response_model=Page[TelemetryOut])
def list_telemetry_endpoint(
    asset_id: str,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_db),
) -> Page[TelemetryOut]:
    """List telemetry readings for one asset with an optional time window."""
    asset = get_asset(session, asset_id)
    if asset is None:
        return _not_found("asset not found")
    rows, total = list_telemetry(
        session,
        asset_id,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )
    items = [TelemetryOut.model_validate(row) for row in rows]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/failures", response_model=Page[FailureOut])
def list_failures_endpoint(
    failure_category: Annotated[str | None, Query(max_length=64)] = None,
    failure_severity: Annotated[int | None, Query(ge=1, le=5)] = None,
    asset_id: Annotated[str | None, Query(max_length=16)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_db),
) -> Page[FailureOut]:
    """List failure incidents with optional filters and pagination."""
    rows, total = list_failures(
        session,
        failure_category=failure_category,
        failure_severity=failure_severity,
        asset_id=asset_id,
        limit=limit,
        offset=offset,
    )
    items = [FailureOut.model_validate(row) for row in rows]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/work-orders", response_model=Page[WorkOrderOut])
def list_work_orders_endpoint(
    work_type: Annotated[str | None, Query(max_length=16)] = None,
    priority: Annotated[str | None, Query(max_length=16)] = None,
    status: Annotated[str | None, Query(max_length=16)] = None,
    asset_id: Annotated[str | None, Query(max_length=16)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_db),
) -> Page[WorkOrderOut]:
    """List maintenance work orders with optional filters and pagination."""
    rows, total = list_work_orders(
        session,
        work_type=work_type,
        priority=priority,
        status=status,
        asset_id=asset_id,
        limit=limit,
        offset=offset,
    )
    items = [WorkOrderOut.model_validate(row) for row in rows]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/ingestion/runs", response_model=Page[IngestionRunOut])
def list_ingestion_runs_endpoint(
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_db),
) -> Page[IngestionRunOut]:
    """List prior ingestion runs with pagination."""
    runs, total = list_ingestion_runs(session, limit=limit, offset=offset)
    items = [_run_out(run) for run in runs]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/ingestion/runs/{run_id}", response_model=IngestionRunOut)
def get_ingestion_run_endpoint(
    run_id: str,
    session: Session = Depends(get_db),
) -> IngestionRunOut:
    """Return one ingestion run with dataset results and quality results."""
    run = get_ingestion_run(session, run_id)
    if run is None:
        return _not_found("ingestion run not found")
    return _run_out(run)
