"""Operations overview aggregation for the command-center page."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import (
    Asset,
    AssetTelemetry,
    DocumentChunk,
    EngineeringDecision,
    FailureIncident,
    IngestionRun,
    Inspection,
    KnowledgeDocument,
    MaintenanceWorkOrder,
    RiskRecord,
    WeatherObservation,
)
from backend.app.predictive import predictive_overview
from backend.app.risk_engine import build_risk_items, risk_summary


def _count(session: Session, model: Any, *conditions: Any) -> int:
    statement = select(func.count()).select_from(model)
    for condition in conditions:
        statement = statement.where(condition)
    return int(session.scalar(statement) or 0)


def _latest_timestamp(session: Session, column: Any) -> str | None:
    value = session.scalar(select(func.max(column)))
    return value.isoformat() if value is not None else None


def overview(session: Session) -> dict[str, Any]:
    """Return real, database-derived metrics for the operations dashboard."""
    total_assets = _count(session, Asset)
    by_type = {
        asset_type: _count(session, Asset, Asset.asset_type == asset_type)
        for asset_type in ("transformers", "substations", "circuit_breakers", "feeders")
    }
    by_status = {
        status: _count(session, Asset, Asset.status == status)
        for status in ("active", "retired")
    }
    by_region = [
        {"region": region or "Unassigned", "count": count}
        for region, count in session.execute(
            select(Asset.region, func.count())
            .group_by(Asset.region)
            .order_by(func.coalesce(Asset.region, "zzz"))
        )
    ]

    latest_telemetry = _latest_timestamp(session, AssetTelemetry.timestamp)
    max_failure = session.scalar(select(func.max(FailureIncident.failure_timestamp)))
    failure_cutoff = max_failure - timedelta(days=90) if max_failure is not None else None
    failures_total = _count(session, FailureIncident)
    failures_90d = (
        _count(session, FailureIncident, FailureIncident.failure_timestamp >= failure_cutoff)
        if failure_cutoff is not None
        else 0
    )
    failure_severity = [
        {"severity": severity, "count": count}
        for severity, count in session.execute(
            select(FailureIncident.failure_severity, func.count())
            .group_by(FailureIncident.failure_severity)
            .order_by(FailureIncident.failure_severity)
        )
    ]

    work_order_status = {
        status: _count(session, MaintenanceWorkOrder, MaintenanceWorkOrder.status == status)
        for status in ("open", "in_progress", "completed", "cancelled")
    }
    work_order_priority = {
        priority: _count(
            session,
            MaintenanceWorkOrder,
            MaintenanceWorkOrder.priority == priority,
            MaintenanceWorkOrder.status.in_(("open", "in_progress")),
        )
        for priority in ("critical", "high", "medium", "low")
    }
    oldest_open = session.scalar(
        select(func.min(MaintenanceWorkOrder.opened_at)).where(
            MaintenanceWorkOrder.status.in_(("open", "in_progress"))
        )
    )

    inspections_total = _count(session, Inspection)
    inspected_assets = int(
        session.scalar(select(func.count(func.distinct(Inspection.asset_id)))) or 0
    )
    condition_counts = {
        condition: _count(session, Inspection, Inspection.condition == condition)
        for condition in ("excellent", "good", "fair", "poor")
    }
    latest_inspection = _latest_timestamp(session, Inspection.inspection_date)

    risk_items = build_risk_items(session)
    risks = risk_summary(risk_items)

    recent_runs = session.scalars(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(5)
    ).all()
    recent_decisions = session.scalars(
        select(EngineeringDecision).order_by(EngineeringDecision.created_at.desc()).limit(5)
    ).all()
    decision_status = {
        status: _count(session, EngineeringDecision, EngineeringDecision.decision_status == status)
        for status in (
            "PENDING_REVIEW",
            "IN_REVIEW",
            "APPROVED",
            "REJECTED",
            "OVERRIDDEN",
            "ESCALATED",
            "DEFERRED",
        )
    }

    documents = _count(session, KnowledgeDocument)
    chunks = _count(session, DocumentChunk)
    latest_weather = _latest_timestamp(session, WeatherObservation.timestamp)
    model = predictive_overview()

    return {
        "synthetic": True,
        "assets": {
            "total": total_assets,
            "by_type": by_type,
            "by_status": by_status,
            "by_region": by_region,
        },
        "failures": {
            "total": failures_total,
            "last_90_days": failures_90d,
            "window_end": max_failure.isoformat() if max_failure is not None else None,
            "severity": failure_severity,
        },
        "work_orders": {
            "by_status": work_order_status,
            "active_by_priority": work_order_priority,
            "active_total": work_order_status["open"] + work_order_status["in_progress"],
            "oldest_open_at": oldest_open.isoformat() if oldest_open is not None else None,
        },
        "inspections": {
            "total": inspections_total,
            "assets_inspected": inspected_assets,
            "coverage_percent": round(inspected_assets / total_assets * 100.0, 1)
            if total_assets
            else 0.0,
            "conditions": condition_counts,
            "latest_inspection": latest_inspection,
        },
        "risks": risks,
        "risk_record_count": _count(session, RiskRecord),
        "knowledge": {"documents": documents, "chunks": chunks},
        "decisions": {
            "total": sum(decision_status.values()),
            "by_status": decision_status,
            "active": decision_status["PENDING_REVIEW"] + decision_status["IN_REVIEW"],
            "recent": [
                {
                    "decision_id": str(decision.decision_id),
                    "asset_id": decision.asset_id,
                    "asset_type": decision.asset_type,
                    "decision_status": decision.decision_status,
                    "reviewer": decision.reviewer,
                    "created_at": decision.created_at.isoformat(),
                }
                for decision in recent_decisions
            ],
        },
        "recent_ingestion": [
            {
                "run_id": str(run.run_id),
                "source_name": run.source_name,
                "status": run.status,
                "started_at": run.started_at.isoformat(),
                "completed_at": None if run.completed_at is None else run.completed_at.isoformat(),
                "rows_read": run.rows_read,
                "rows_inserted": run.rows_inserted,
                "rows_updated": run.rows_updated,
                "rows_rejected": run.rows_rejected,
            }
            for run in recent_runs
        ],
        "model": {
            "available": model["available"],
            "name": model["preferred_model"]["label"] if model["preferred_model"] else None,
            "model_name": model["preferred_model"]["model_name"] if model["preferred_model"] else None,
            "model_version": model["preferred_model"]["model_version"] if model["preferred_model"] else None,
            "threshold": model["preferred_model"]["threshold"] if model["preferred_model"] else None,
        },
        "freshness": {
            "latest_telemetry": latest_telemetry,
            "latest_failure": max_failure.isoformat() if max_failure is not None else None,
            "latest_inspection": latest_inspection,
            "latest_weather": latest_weather,
        },
        "top_risks": risks["top_assets"],
    }


__all__ = ["overview"]
