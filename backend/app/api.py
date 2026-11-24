"""Read-only REST API for the GridOps Intelligence backend."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.crud import (
    asset_filter_options,
    count_assets,
    get_asset,
    get_ingestion_run,
    list_assets,
    list_failures,
    list_ingestion_runs,
    list_telemetry,
    list_work_orders,
)
from backend.app.database import get_db
from backend.app.models import (
    AssetTelemetry,
    DataQualityResult,
    FailureIncident,
    IngestionDatasetResult,
    IngestionRun,
    Inspection,
    MaintenanceWorkOrder,
)
from backend.app.risk_engine import build_risk_items
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


@router.get("/assets/summary")
def assets_summary_endpoint(session: Session = Depends(get_db)):
    """Return total asset count, status split, and counts by equipment type."""
    total = count_assets(session)
    by_type = {}
    for asset_type in ("transformers", "substations", "circuit_breakers", "feeders"):
        by_type[asset_type] = count_assets(session, asset_type=asset_type)
    by_status = {
        status: count_assets(session, status=status) for status in ("active", "retired")
    }
    return {"total": total, "by_type": by_type, "by_status": by_status}


@router.get("/assets/filters")
def asset_filters_endpoint(session: Session = Depends(get_db)):
    """Return the filter values that actually exist in the asset dimension."""
    return asset_filter_options(session)


@router.get("/assets")
def list_assets_endpoint(
    asset_type: Annotated[str | None, Query(max_length=32)] = None,
    status: Annotated[str | None, Query(max_length=16)] = None,
    region: Annotated[str | None, Query(max_length=32)] = None,
    search: Annotated[str | None, Query(max_length=64)] = None,
    sort_by: Annotated[str, Query(max_length=32)] = "asset_id",
    sort_dir: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_db),
) -> Page[AssetOut]:
    """List assets with global search, filters, sorting, and pagination."""
    assets, total = list_assets(
        session,
        asset_type=asset_type,
        status=status,
        region=region,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    items = [AssetOut.model_validate(asset) for asset in assets]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/assets/{asset_id}")
def get_asset_endpoint(
    asset_id: str,
    session: Session = Depends(get_db),
) -> AssetDetailOut:
    """Return one asset and its type-specific detail."""
    asset = get_asset(session, asset_id)
    if asset is None:
        return _not_found("asset not found")
    return asset_detail_response(asset)


def _asset_profile(session: Session, asset_id: str) -> dict:
    asset = get_asset(session, asset_id)
    if asset is None:
        return {}
    risk_items = build_risk_items(session, asset_ids=[asset_id])
    recent_failures = session.query(FailureIncident).filter(
        FailureIncident.asset_id == asset_id
    ).order_by(FailureIncident.failure_timestamp.desc()).limit(5).all()
    recent_orders = session.query(MaintenanceWorkOrder).filter(
        MaintenanceWorkOrder.asset_id == asset_id
    ).order_by(MaintenanceWorkOrder.opened_at.desc()).limit(5).all()
    recent_inspections = session.query(Inspection).filter(
        Inspection.asset_id == asset_id
    ).order_by(Inspection.inspection_date.desc()).limit(5).all()
    telemetry_count = int(
        session.query(AssetTelemetry).filter(AssetTelemetry.asset_id == asset_id).count()
    )
    latest_telemetry = session.query(AssetTelemetry).filter(
        AssetTelemetry.asset_id == asset_id
    ).order_by(AssetTelemetry.timestamp.desc()).first()
    return {
        "asset": asset_detail_response(asset).model_dump(),
        "risk": risk_items[0] if risk_items else None,
        "telemetry": {
            "count": telemetry_count,
            "latest": None
            if latest_telemetry is None
            else {
                "timestamp": latest_telemetry.timestamp.isoformat(),
                "temperature_c": None if latest_telemetry.temperature_c is None else float(latest_telemetry.temperature_c),
                "load_pct": None if latest_telemetry.load_pct is None else float(latest_telemetry.load_pct),
                "voltage_kv": None if latest_telemetry.voltage_kv is None else float(latest_telemetry.voltage_kv),
                "current_a": None if latest_telemetry.current_a is None else float(latest_telemetry.current_a),
                "vibration_mm_s": None if latest_telemetry.vibration_mm_s is None else float(latest_telemetry.vibration_mm_s),
            },
        },
        "recent_failures": [
            {
                "failure_id": row.failure_id,
                "failure_category": row.failure_category,
                "failure_timestamp": row.failure_timestamp.isoformat(),
                "failure_severity": row.failure_severity,
                "downtime_hours": float(row.downtime_hours),
            }
            for row in recent_failures
        ],
        "recent_work_orders": [
            {
                "work_order_id": row.work_order_id,
                "work_type": row.work_type,
                "priority": row.priority,
                "status": row.status,
                "opened_at": row.opened_at.isoformat(),
                "completed_at": None if row.completed_at is None else row.completed_at.isoformat(),
            }
            for row in recent_orders
        ],
        "recent_inspections": [
            {
                "inspection_id": row.inspection_id,
                "inspection_date": row.inspection_date.isoformat(),
                "condition": row.condition,
                "severity": row.severity,
                "findings": row.findings,
            }
            for row in recent_inspections
        ],
    }


@router.get("/assets/{asset_id}/profile")
def asset_profile_endpoint(asset_id: str, session: Session = Depends(get_db)):
    """Return an asset, its risk record, telemetry summary, and recent history."""
    profile = _asset_profile(session, asset_id)
    if not profile:
        return _not_found("asset not found")
    return profile


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

# ---------------------------------------------------------------------------
# Command-center, predictive, risk, explainability, and governance surfaces
# ---------------------------------------------------------------------------


@router.get("/overview")
def overview_endpoint(session: Session = Depends(get_db)):
    """Return database-derived operations overview metrics."""
    from backend.app.overview import overview

    return overview(session)


@router.get("/predictive/status")
def predictive_status_endpoint():
    """Backward-compatible model status summary."""
    from backend.app.predictive import predictive_overview

    payload = predictive_overview()
    preferred = payload["preferred_model"]
    return {
        "available": payload["available"],
        "model_name": preferred["model_name"] if preferred else None,
        "label": preferred["label"] if preferred else None,
        "model_version": preferred["model_version"] if preferred else None,
        "artifact_path": preferred["artifact_path"] if preferred else None,
        "threshold": preferred["threshold"] if preferred else None,
        "metrics": preferred["validation_metrics"] if preferred else None,
        "test_metrics": preferred["test_metrics"] if preferred else None,
        "message": payload["message"],
        "synthetic_warning": payload["synthetic_warning"],
    }


@router.get("/predictive")
def predictive_endpoint():
    """Return every persisted model artifact, metrics, and comparison context."""
    from backend.app.predictive import predictive_overview

    return predictive_overview()


@router.get("/risk/summary")
def risk_summary_endpoint(session: Session = Depends(get_db)):
    """Return the ranked risk population summary and its transparent rules."""
    from backend.app.risk_engine import build_risk_items, risk_summary

    items = build_risk_items(session)
    summary = risk_summary(items)
    summary["filter_options"] = {
        "asset_types": sorted({item["asset_type"] for item in items}),
        "priorities": [band for band in ("P1", "P2", "P3", "P4", "P5") if summary["by_priority"].get(band)],
        "risk_categories": sorted({item["risk_category"] for item in items}),
    }
    return summary


@router.get("/risk")
def risk_list_endpoint(
    search: Annotated[str | None, Query(max_length=64)] = None,
    asset_type: Annotated[str | None, Query(max_length=32)] = None,
    priority: Annotated[str | None, Query(max_length=2)] = None,
    risk_category: Annotated[str | None, Query(max_length=32)] = None,
    sort: Annotated[str, Query(max_length=32)] = "rank",
    direction: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_db),
):
    """Return ranked, filterable risk records with the full-population summary."""
    from backend.app.risk_engine import (
        build_risk_items,
        filter_risk_items,
        risk_summary,
    )

    items = build_risk_items(session)
    summary = risk_summary(items)
    filtered = filter_risk_items(
        items,
        search=search,
        asset_type=asset_type,
        priority=priority,
        risk_category=risk_category,
        sort=sort,
        direction=direction,
    )
    page_items = filtered[offset : offset + limit]
    return {
        "items": page_items,
        "total": len(filtered),
        "limit": limit,
        "offset": offset,
        "summary": summary,
        "filter_options": {
            "asset_types": sorted({item["asset_type"] for item in items}),
            "priorities": [
                band for band in ("P1", "P2", "P3", "P4", "P5")
                if summary["by_priority"].get(band)
            ],
            "risk_categories": sorted({item["risk_category"] for item in items}),
        },
    }


@router.get("/risk/{asset_id}")
def risk_detail_endpoint(asset_id: str, session: Session = Depends(get_db)):
    """Return one ranked risk record plus its persisted explanation."""
    from backend.app.explainability import explain_asset
    from backend.app.risk_engine import build_risk_items

    items = build_risk_items(session)
    item = next((entry for entry in items if entry["asset_id"] == asset_id), None)
    if item is None:
        return _not_found("risk record not found")
    return {"item": item, "explanation": explain_asset(session, asset_id)}


@router.get("/explainability/global")
def explainability_global_endpoint():
    """Return the model-wide explanation inputs and methodology."""
    from backend.app.explainability import (
        BASELINE_PATH,
        global_feature_importance,
        load_baseline,
    )
    from backend.app.predictive import predictive_overview
    from backend.app.settings import DEFAULT_MODEL_NAME, model_artifact_path, safe_artifact_reference

    model_path = model_artifact_path(DEFAULT_MODEL_NAME)
    importance: list[dict] = []
    model_loaded = False
    if model_path.exists():
        from ml.artifacts.registry import load_model

        try:
            model = load_model(model_path)
            importance = global_feature_importance(model, top_n=15)
            model_loaded = True
        except Exception:  # noqa: BLE001 - a corrupt artifact must not crash the API
            importance = []
    baseline = load_baseline()
    payload = predictive_overview()
    return {
        "model_available": model_loaded,
        "preferred_model": payload["preferred_model"],
        "global_importance": importance,
        "baseline": None
        if baseline is None
        else {
            "artifact": safe_artifact_reference(BASELINE_PATH),
            "created_at": baseline.get("created_at"),
            "prediction_cutoff": baseline.get("prediction_cutoff"),
            "asset_count": baseline.get("asset_count"),
            "feature_count": baseline.get("feature_count"),
            "model_version": baseline.get("model_version"),
            "methodology": baseline.get("methodology"),
            "z_cap": baseline.get("z_cap"),
        },
        "methodology": {
            "deviation": "Robust z-score of an asset feature against the persisted population median and robust scale.",
            "importance": "Global importance is aggregated from model coefficients or tree feature importances; it is not local attribution.",
            "causality": "Neither deviation nor importance establishes causation.",
            "not_shap": "This implementation is not SHAP and does not compute Shapley values.",
        },
    }


@router.get("/explainability/{asset_id}")
def explainability_asset_endpoint(asset_id: str, session: Session = Depends(get_db)):
    """Return the persisted explanation for one asset."""
    from backend.app.explainability import explain_asset

    explanation = explain_asset(session, asset_id)
    if explanation is None:
        return _not_found("asset not found")
    return explanation


@router.get("/governance")
def governance_endpoint(session: Session = Depends(get_db)):
    """Return lineage, ingestion, quality, model, and audit evidence."""
    from backend.app.governance import governance_overview

    return governance_overview(session)
