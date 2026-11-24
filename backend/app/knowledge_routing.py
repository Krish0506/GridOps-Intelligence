"""Structured-question routing for Evidence Intelligence.

Questions about counts, status breakdowns, and other tabular facts must be
answered from PostgreSQL, not from document retrieval.  The router is
deliberately conservative: unrecognised questions fall through to the RAG
pipeline.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import (
    Asset,
    AssetTelemetry,
    EngineeringDecision,
    FailureIncident,
    Inspection,
    KnowledgeDocument,
    MaintenanceWorkOrder,
    RiskRecord,
)

ASSET_TYPES = {
    "transformer": "transformers",
    "transformers": "transformers",
    "substation": "substations",
    "substations": "substations",
    "circuit breaker": "circuit_breakers",
    "circuit breakers": "circuit_breakers",
    "breaker": "circuit_breakers",
    "breakers": "circuit_breakers",
    "feeder": "feeders",
    "feeders": "feeders",
}


def _count(session: Session, model: Any, *conditions: Any) -> int:
    statement = select(func.count()).select_from(model)
    for condition in conditions:
        statement = statement.where(condition)
    return int(session.scalar(statement) or 0)


def _asset_type_in_question(question: str) -> str | None:
    lowered = question.lower()
    for phrase, asset_type in sorted(ASSET_TYPES.items(), key=lambda item: len(item[0]), reverse=True):
        if phrase in lowered:
            return asset_type
    return None


def _region_in_question(session: Session, question: str) -> str | None:
    regions = [
        region
        for region in session.scalars(select(Asset.region).distinct().order_by(Asset.region)).all()
        if region
    ]
    tokens = set(re.findall(r"\b[A-Za-z]{2,3}\b", question))
    for region in regions:
        if region in tokens or region.lower() in question.lower():
            return region
    return None


def _answer(question: str, metric: str, value: Any, text: str, **extra: Any) -> dict[str, Any]:
    return {
        "question": question,
        "route": "structured_database",
        "metric": metric,
        "value": value,
        "text": text,
        **extra,
    }


def route_question(session: Session, question: str) -> dict[str, Any] | None:
    """Return a structured answer for a tabular question, or ``None``."""
    lowered = question.lower().strip()
    if not lowered:
        return None

    asset_type = _asset_type_in_question(question)
    region = _region_in_question(session, question)

    if re.search(r"\b(total|how many|count|number of)\b.*\bassets?\b", lowered) or (
        "asset count" in lowered
    ):
        total = _count(session, Asset)
        by_type = {
            asset_type_name: _count(session, Asset, Asset.asset_type == asset_type_name)
            for asset_type_name in ("transformers", "substations", "circuit_breakers", "feeders")
        }
        if asset_type:
            value = by_type[asset_type]
            return _answer(
                question,
                "asset_count",
                value,
                f"The synthetic asset inventory contains {value:,} {asset_type.replace('_', ' ')}.",
                breakdown={"asset_type": asset_type},
            )
        if region:
            value = _count(session, Asset, Asset.region == region)
            return _answer(
                question,
                "asset_count",
                value,
                f"The synthetic asset inventory contains {value:,} assets in region {region}.",
                breakdown={"region": region},
            )
        return _answer(
            question,
            "asset_count",
            total,
            f"The synthetic asset inventory contains {total:,} assets: "
            + ", ".join(f"{name.replace('_', ' ')} {count:,}" for name, count in by_type.items())
            + ".",
            breakdown=by_type,
        )

    if re.search(r"\b(active|retired)\b", lowered) and "asset" in lowered:
        status = "active" if "active" in lowered else "retired"
        value = _count(session, Asset, Asset.status == status)
        return _answer(
            question,
            "asset_status_count",
            value,
            f"There are {value:,} {status} synthetic assets.",
            breakdown={"status": status},
        )

    if asset_type and re.search(r"\b(how many|count|number)\b", lowered):
        value = _count(session, Asset, Asset.asset_type == asset_type)
        return _answer(
            question,
            "asset_count",
            value,
            f"There are {value:,} synthetic {asset_type.replace('_', ' ')} in the inventory.",
            breakdown={"asset_type": asset_type},
        )

    if re.search(r"\b(work orders?|maintenance backlog|backlog)\b", lowered):
        open_count = _count(session, MaintenanceWorkOrder, MaintenanceWorkOrder.status == "open")
        in_progress = _count(
            session, MaintenanceWorkOrder, MaintenanceWorkOrder.status == "in_progress"
        )
        total = _count(session, MaintenanceWorkOrder)
        critical = _count(
            session,
            MaintenanceWorkOrder,
            MaintenanceWorkOrder.priority == "critical",
            MaintenanceWorkOrder.status.in_(("open", "in_progress")),
        )
        return _answer(
            question,
            "work_order_backlog",
            open_count + in_progress,
            f"There are {open_count:,} open and {in_progress:,} in-progress work orders "
            f"({critical:,} of the open/in-progress orders are critical priority). "
            f"The full synthetic maintenance history contains {total:,} work orders.",
            breakdown={
                "open": open_count,
                "in_progress": in_progress,
                "critical_active": critical,
                "total": total,
            },
        )

    if "failure" in lowered and re.search(r"\b(how many|count|number|total)\b", lowered):
        total = _count(session, FailureIncident)
        severe = _count(session, FailureIncident, FailureIncident.failure_severity >= 4)
        return _answer(
            question,
            "failure_count",
            total,
            f"The synthetic failure history contains {total:,} incidents; {severe:,} have severity 4 or 5.",
            breakdown={"total": total, "severity_4_or_5": severe},
        )

    if "inspection" in lowered and re.search(r"\b(how many|count|number|coverage)\b", lowered):
        total = _count(session, Inspection)
        covered = int(
            session.scalar(select(func.count(func.distinct(Inspection.asset_id)))) or 0
        )
        asset_total = _count(session, Asset)
        percent = (covered / asset_total * 100.0) if asset_total else 0.0
        return _answer(
            question,
            "inspection_coverage",
            covered,
            f"The synthetic inspection history contains {total:,} inspections covering "
            f"{covered:,} of {asset_total:,} assets ({percent:.1f}% asset coverage).",
            breakdown={
                "inspections": total,
                "assets_with_inspection": covered,
                "asset_total": asset_total,
                "coverage_percent": round(percent, 2),
            },
        )

    if re.search(r"\b(telemetry|sensor readings?)\b", lowered) and re.search(
        r"\b(how many|count|number|total)\b", lowered
    ):
        total = _count(session, AssetTelemetry)
        return _answer(
            question,
            "telemetry_count",
            total,
            f"The synthetic telemetry store contains {total:,} readings.",
            breakdown={"total": total},
        )

    if re.search(r"\b(risk records?|assets? at risk|risk count|high risk)\b", lowered) and re.search(
        r"\b(how many|count|number|total)\b", lowered
    ):
        total = _count(session, RiskRecord)
        predicted = _count(session, RiskRecord, RiskRecord.risk_category == "predicted_failure")
        return _answer(
            question,
            "risk_count",
            total,
            f"The persisted risk workspace contains {total:,} asset risk records; "
            f"{predicted:,} are currently classified as predicted failure by the synthetic model.",
            breakdown={"total": total, "predicted_failure": predicted},
        )

    if re.search(r"\b(knowledge|documents?|corpus)\b", lowered) and re.search(
        r"\b(how many|count|number|total)\b", lowered
    ):
        from backend.app.models import DocumentChunk

        documents = _count(session, KnowledgeDocument)
        chunks = _count(session, DocumentChunk)
        return _answer(
            question,
            "knowledge_count",
            documents,
            f"The synthetic engineering corpus contains {documents:,} document files and {chunks:,} indexed chunks.",
            breakdown={"documents": documents, "chunks": chunks},
        )

    if re.search(r"\bdecisions?\b", lowered) and re.search(
        r"\b(how many|count|number|pending|approved|review)\b", lowered
    ):
        total = _count(session, EngineeringDecision)
        by_status = {
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
        active = by_status["PENDING_REVIEW"] + by_status["IN_REVIEW"]
        return _answer(
            question,
            "decision_count",
            active,
            f"There are {active:,} decisions awaiting human review and {total:,} decision records in total.",
            breakdown=by_status,
        )

    match = re.search(r"\b(?:T|S|CB|F)-\d{5}\b", question, re.IGNORECASE)
    if match and re.search(r"\b(how many|count|number|risk|status|details?)\b", lowered):
        asset_id = match.group(0).upper()
        asset = session.get(Asset, asset_id)
        if asset is None:
            return _answer(
                question,
                "asset_lookup",
                None,
                f"No synthetic asset with identifier {asset_id} exists.",
                breakdown={"asset_id": asset_id, "found": False},
            )
        risk = session.scalars(
            select(RiskRecord)
            .where(RiskRecord.asset_id == asset_id)
            .order_by(RiskRecord.prediction_cutoff.desc())
            .limit(1)
        ).first()
        risk_text = ""
        if risk is not None:
            probability = float(risk.model_probability) if risk.model_probability is not None else None
            risk_text = (
                f" Its latest persisted risk record is {risk.risk_category}"
                + (f" with model probability {probability:.3f}" if probability is not None else "")
                + "."
            )
        return _answer(
            question,
            "asset_lookup",
            asset_id,
            f"{asset.asset_id} is a synthetic {asset.asset_type.replace('_', ' ')} "
            f"named {asset.name} with status {asset.status}.{risk_text}",
            breakdown={
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "status": asset.status,
                "region": asset.region,
            },
        )

    return None


__all__ = ["route_question"]
