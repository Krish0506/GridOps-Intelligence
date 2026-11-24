"""Governance, lineage, and audit aggregation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.app.models import (
    Asset,
    AssetTelemetry,
    DataQualityResult,
    DecisionEvent,
    DocumentChunk,
    EngineeringDecision,
    FailureIncident,
    IngestionRun,
    Inspection,
    KnowledgeDocument,
    KnowledgeIngestionRun,
    MaintenanceWorkOrder,
    RiskRecord,
    WeatherObservation,
)
from backend.app.predictive import predictive_overview
from backend.app.risk_engine import build_risk_items, risk_summary


def _count(session: Session, model: Any) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _format_quality_details(details: Any) -> str:
    """Render persisted JSONB quality detail payloads as readable prose."""
    if details is None:
        return ""
    if isinstance(details, str):
        return details
    if isinstance(details, dict):
        parts = []
        for key, value in details.items():
            if isinstance(value, bool):
                parts.append(f"{key}: {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                parts.append(f"{key}: {float(value):g}")
            else:
                parts.append(f"{key}: {value}")
        return "; ".join(parts)
    if isinstance(details, (list, tuple)):
        return "; ".join(str(item) for item in details)
    return str(details)


def _quality_summary(session: Session) -> dict[str, Any]:
    severity = {row.severity: row.count for row in session.execute(
        select(DataQualityResult.severity, func.count()).group_by(DataQualityResult.severity)
    )}
    totals = session.execute(
        select(
            func.count(DataQualityResult.result_id),
            func.coalesce(func.sum(DataQualityResult.records_checked), 0),
            func.coalesce(func.sum(DataQualityResult.records_failed), 0),
        )
    ).one()
    worst = session.execute(
        select(
            DataQualityResult.result_id,
            DataQualityResult.dataset_name,
            DataQualityResult.check_name,
            DataQualityResult.severity,
            DataQualityResult.records_failed,
            DataQualityResult.details,
        )
        .where(DataQualityResult.records_failed > 0)
        .order_by(DataQualityResult.records_failed.desc())
        .limit(12)
    ).all()
    return {
        "checks": int(totals[0] or 0),
        "records_checked": int(totals[1] or 0),
        "records_failed": int(totals[2] or 0),
        "by_severity": {key: int(value) for key, value in severity.items()},
        "checks_with_failures": [
            {
                "result_id": row.result_id,
                "dataset": row.dataset_name,
                "check": row.check_name,
                "severity": row.severity,
                "records_failed": row.records_failed,
                "details": _format_quality_details(row.details),
            }
            for row in worst
        ],
    }


def governance_overview(session: Session) -> dict[str, Any]:
    """Return traceability data that is actually present in PostgreSQL."""
    datasets = {
        "assets": _count(session, Asset),
        "transformers": 0,
        "substations": 0,
        "circuit_breakers": 0,
        "feeders": 0,
        "telemetry": _count(session, AssetTelemetry),
        "work_orders": _count(session, MaintenanceWorkOrder),
        "inspections": _count(session, Inspection),
        "failures": _count(session, FailureIncident),
        "weather": _count(session, WeatherObservation),
        "risk_records": _count(session, RiskRecord),
        "knowledge_documents": _count(session, KnowledgeDocument),
        "knowledge_chunks": _count(session, DocumentChunk),
        "engineering_decisions": _count(session, EngineeringDecision),
        "decision_events": _count(session, DecisionEvent),
        "data_quality_results": _count(session, DataQualityResult),
    }
    for asset_type, key in (
        ("transformers", "transformers"),
        ("substations", "substations"),
        ("circuit_breakers", "circuit_breakers"),
        ("feeders", "feeders"),
    ):
        datasets[key] = int(
            session.scalar(
                select(func.count()).select_from(Asset).where(Asset.asset_type == asset_type)
            )
            or 0
        )

    runs = session.scalars(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(10)
    ).all()
    knowledge_runs = session.scalars(
        select(KnowledgeIngestionRun).order_by(KnowledgeIngestionRun.started_at.desc()).limit(10)
    ).all()
    decisions = session.scalars(
        select(EngineeringDecision).order_by(EngineeringDecision.updated_at.desc()).limit(10)
    ).all()
    events = session.scalars(
        select(DecisionEvent).order_by(DecisionEvent.timestamp.desc()).limit(20)
    ).all()
    knowledge_categories = [
        {"category": category, "count": count}
        for category, count in session.execute(
            select(KnowledgeDocument.category, func.count())
            .group_by(KnowledgeDocument.category)
            .order_by(KnowledgeDocument.category)
        )
    ]
    models = predictive_overview()
    risks = risk_summary(build_risk_items(session))
    try:
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # noqa: BLE001
        revision = None

    return {
        "synthetic": True,
        "database": {
            "alembic_revision": revision,
            "engine": "PostgreSQL 16 with pgvector extension available",
        },
        "datasets": datasets,
        "ingestion_runs": [
            {
                "run_id": str(run.run_id),
                "source_name": run.source_name,
                "status": run.status,
                "started_at": run.started_at.isoformat(),
                "completed_at": None if run.completed_at is None else run.completed_at.isoformat(),
                "rows_read": run.rows_read,
                "rows_inserted": run.rows_inserted,
                "rows_updated": run.rows_updated,
                "rows_skipped": run.rows_skipped,
                "rows_rejected": run.rows_rejected,
                "error_summary": run.error_summary,
                "report_path": run.report_path,
            }
            for run in runs
        ],
        "data_quality": _quality_summary(session),
        "knowledge": {
            "documents": datasets["knowledge_documents"],
            "chunks": datasets["knowledge_chunks"],
            "categories": knowledge_categories,
            "ingestion_runs": [
                {
                    "run_id": str(run.run_id),
                    "status": run.status,
                    "started_at": run.started_at.isoformat(),
                    "completed_at": None if run.completed_at is None else run.completed_at.isoformat(),
                    "documents_processed": run.documents_processed,
                    "chunks_created": run.chunks_created,
                    "error_count": run.error_count,
                }
                for run in knowledge_runs
            ],
        },
        "models": models["models"],
        "model_warning": models["synthetic_warning"],
        "risk_generation": {
            "records": risks["total"],
            "by_priority": risks["by_priority"],
            "by_type": risks["by_type"],
            "model_versions": risks["model_versions"],
            "prediction_cutoffs": risks["prediction_cutoffs"],
            "data_quality_warning_count": risks["data_quality_warning_count"],
        },
        "decisions": {
            "recent": [
                {
                    "decision_id": str(decision.decision_id),
                    "asset_id": decision.asset_id,
                    "asset_type": decision.asset_type,
                    "decision_status": decision.decision_status,
                    "reviewer": decision.reviewer,
                    "risk_category": decision.risk_category,
                    "model_version": decision.model_version,
                    "created_at": decision.created_at.isoformat(),
                    "updated_at": decision.updated_at.isoformat(),
                    "decided_at": None if decision.decided_at is None else decision.decided_at.isoformat(),
                }
                for decision in decisions
            ],
            "audit_events": [
                {
                    "event_id": str(event.event_id),
                    "decision_id": str(event.decision_id),
                    "previous_status": event.previous_status,
                    "new_status": event.new_status,
                    "action": event.action,
                    "reviewer": event.reviewer,
                    "reason": event.reason,
                    "timestamp": event.timestamp.isoformat(),
                }
                for event in events
            ],
        },
        "limitations": [
            "No authentication or authorization is implemented.",
            "No production compliance certification or regulatory approval.",
            "No implemented model-drift monitoring or automated retraining.",
            "All data, documents, models, and outcomes are synthetic demonstration material.",
            "The system never auto-approves a decision or executes maintenance.",
            "Anomaly scores are not calibrated failure probabilities.",
        ],
    }


__all__ = ["governance_overview"]
