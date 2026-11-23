"""Engineering decision workflow services (Milestone 5)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models import DecisionEvidence, DecisionEvent, EngineeringDecision


VALID_STATUSES = {"PENDING_REVIEW", "IN_REVIEW", "APPROVED", "REJECTED", "OVERRIDDEN", "ESCALATED", "DEFERRED"}
TRANSITIONS = {
    "PENDING_REVIEW": {"IN_REVIEW"},
    "IN_REVIEW": {"APPROVED", "REJECTED", "OVERRIDDEN", "ESCALATED", "DEFERRED"},
}


class DecisionError(ValueError):
    """Raised when a decision action violates business rules."""


def create_decision(
    session: Session,
    *,
    asset_id: str,
    asset_type: str,
    model_version: str | None = None,
    predicted_risk_probability: float | None = None,
    risk_category: str | None = None,
    anomaly_score: float | None = None,
    reviewer: str = "demo-reviewer",
    reason: str | None = None,
) -> EngineeringDecision:
    decision = EngineeringDecision(
        asset_id=asset_id,
        asset_type=asset_type,
        model_version=model_version,
        predicted_risk_probability=predicted_risk_probability,
        risk_category=risk_category,
        anomaly_score=anomaly_score,
        decision_status="PENDING_REVIEW",
        decision_reason=reason,
        reviewer=reviewer,
    )
    session.add(decision)
    session.flush()
    event = DecisionEvent(
        decision_id=decision.decision_id,
        previous_status=None,
        new_status="PENDING_REVIEW",
        action="CREATE",
        reviewer=reviewer,
        reason=reason,
        prediction_snapshot={
            "predicted_risk_probability": predicted_risk_probability,
            "risk_category": risk_category,
            "anomaly_score": anomaly_score,
            "model_version": model_version,
        },
    )
    session.add(event)
    session.flush()
    return decision


def _transition(
    session: Session,
    decision: EngineeringDecision,
    *,
    action: str,
    new_status: str,
    reviewer: str,
    reason: str | None,
    replacement_risk_category: str | None = None,
    review_date: datetime | None = None,
    evidence: list[dict] | None = None,
) -> EngineeringDecision:
    if new_status not in VALID_STATUSES:
        raise DecisionError(f"invalid status: {new_status}")
    if new_status not in TRANSITIONS.get(decision.decision_status, set()):
        raise DecisionError(
            f"invalid transition from {decision.decision_status} to {new_status} via {action}"
        )

    previous_status = decision.decision_status
    decision.decision_status = new_status
    decision.reviewer = reviewer
    decision.decision_reason = reason
    decision.updated_at = datetime.now(timezone.utc)
    if new_status in {"APPROVED", "REJECTED", "OVERRIDDEN", "ESCALATED", "DEFERRED"}:
        decision.decided_at = datetime.now(timezone.utc)
    if replacement_risk_category is not None:
        decision.replacement_risk_category = replacement_risk_category
    if review_date is not None:
        decision.review_date = review_date

    if evidence:
        for item in evidence:
            session.add(
                DecisionEvidence(
                    decision_id=decision.decision_id,
                    document_id=item["document_id"],
                    chunk_id=item["chunk_id"],
                    document_title=item["document_title"],
                    revision=item["revision"],
                    page_number=item.get("page_number"),
                    excerpt=item["excerpt"],
                    source_checksum=item["source_checksum"],
                )
            )

    event = DecisionEvent(
        decision_id=decision.decision_id,
        previous_status=previous_status,
        new_status=new_status,
        action=action,
        reviewer=reviewer,
        reason=reason,
        prediction_snapshot={
            "predicted_risk_probability": (
                float(decision.predicted_risk_probability)
                if decision.predicted_risk_probability is not None
                else None
            ),
            "risk_category": decision.risk_category,
            "anomaly_score": float(decision.anomaly_score) if decision.anomaly_score is not None else None,
            "model_version": decision.model_version,
        },
        evidence_snapshot={"evidence": evidence} if evidence else None,
    )
    session.add(event)
    session.flush()
    return decision


def review_decision(session: Session, decision_id: UUID, *, reviewer: str = "demo-reviewer", reason: str | None = None) -> EngineeringDecision:
    decision = _get(session, decision_id)
    return _transition(session, decision, action="REVIEW", new_status="IN_REVIEW", reviewer=reviewer, reason=reason)


def approve_decision(session: Session, decision_id: UUID, *, reviewer: str, reason: str) -> EngineeringDecision:
    if not reason:
        raise DecisionError("APPROVE requires a reason")
    decision = _get(session, decision_id)
    return _transition(session, decision, action="APPROVE", new_status="APPROVED", reviewer=reviewer, reason=reason)


def reject_decision(session: Session, decision_id: UUID, *, reviewer: str, reason: str) -> EngineeringDecision:
    if not reason:
        raise DecisionError("REJECT requires a reason")
    decision = _get(session, decision_id)
    return _transition(session, decision, action="REJECT", new_status="REJECTED", reviewer=reviewer, reason=reason)


def override_decision(
    session: Session,
    decision_id: UUID,
    *,
    reviewer: str,
    reason: str,
    replacement_risk_category: str,
) -> EngineeringDecision:
    if not reason:
        raise DecisionError("OVERRIDE requires a reason")
    if not replacement_risk_category:
        raise DecisionError("OVERRIDE requires a replacement risk category")
    decision = _get(session, decision_id)
    return _transition(
        session,
        decision,
        action="OVERRIDE",
        new_status="OVERRIDDEN",
        reviewer=reviewer,
        reason=reason,
        replacement_risk_category=replacement_risk_category,
    )


def escalate_decision(session: Session, decision_id: UUID, *, reviewer: str, reason: str) -> EngineeringDecision:
    if not reason:
        raise DecisionError("ESCALATE requires a reason")
    decision = _get(session, decision_id)
    return _transition(session, decision, action="ESCALATE", new_status="ESCALATED", reviewer=reviewer, reason=reason)


def defer_decision(
    session: Session,
    decision_id: UUID,
    *,
    reviewer: str,
    reason: str,
    review_date: datetime | None = None,
) -> EngineeringDecision:
    if not reason:
        raise DecisionError("DEFER requires a reason")
    decision = _get(session, decision_id)
    return _transition(
        session,
        decision,
        action="DEFER",
        new_status="DEFERRED",
        reviewer=reviewer,
        reason=reason,
        review_date=review_date,
    )


def associate_evidence(
    session: Session,
    decision_id: UUID,
    evidence_items: list[dict],
    *,
    validate: bool = True,
) -> list[DecisionEvidence]:
    """Associate retrieved knowledge chunks with a decision."""
    decision = _get(session, decision_id)
    created: list[DecisionEvidence] = []
    for item in evidence_items:
        if validate:
            # Validate that the chunk exists in the knowledge base.
            from rag.repository import SQLAlchemyKnowledgeRepository

            repository = SQLAlchemyKnowledgeRepository(session)
            chunk = repository.get_chunk(item["chunk_id"])
            if chunk is None:
                raise DecisionError(f"evidence chunk not found: {item['chunk_id']}")
            if chunk.source_checksum != item.get("source_checksum"):
                raise DecisionError("evidence checksum mismatch")
        evidence = DecisionEvidence(
            decision_id=decision.decision_id,
            document_id=item["document_id"],
            chunk_id=item["chunk_id"],
            document_title=item["document_title"],
            revision=item["revision"],
            page_number=item.get("page_number"),
            excerpt=item["excerpt"],
            source_checksum=item["source_checksum"],
        )
        session.add(evidence)
        created.append(evidence)
    session.flush()
    return created


def get_decision(session: Session, decision_id: UUID) -> EngineeringDecision | None:
    return session.get(EngineeringDecision, decision_id)


def list_decisions(session: Session, *, status: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[EngineeringDecision], int]:
    query = session.query(EngineeringDecision)
    if status:
        query = query.filter(EngineeringDecision.decision_status == status)
    total = query.count()
    items = query.order_by(EngineeringDecision.created_at.desc()).offset(offset).limit(limit).all()
    return items, total


def get_history(session: Session, decision_id: UUID) -> list[DecisionEvent]:
    decision = _get(session, decision_id)
    return sorted(decision.history, key=lambda event: event.timestamp)


def get_evidence(session: Session, decision_id: UUID) -> list[DecisionEvidence]:
    decision = _get(session, decision_id)
    return list(decision.evidence)


def _get(session: Session, decision_id: UUID) -> EngineeringDecision:
    decision = session.get(EngineeringDecision, decision_id)
    if decision is None:
        raise DecisionError("decision not found")
    return decision


__all__ = [
    "DecisionError",
    "associate_evidence",
    "create_decision",
    "defer_decision",
    "escalate_decision",
    "get_decision",
    "get_evidence",
    "get_history",
    "list_decisions",
    "override_decision",
    "approve_decision",
    "reject_decision",
    "review_decision",
]
