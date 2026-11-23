"""Engineering decision REST API (Milestone 5)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import Page
from decisions.service import (
    DecisionError,
    approve_decision,
    associate_evidence,
    create_decision,
    defer_decision,
    escalate_decision,
    get_decision,
    get_evidence,
    get_history,
    list_decisions,
    override_decision,
    reject_decision,
    review_decision,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/decisions")


class DecisionCreateRequest(BaseModel):
    asset_id: str
    asset_type: str
    model_version: str | None = None
    predicted_risk_probability: float | None = None
    risk_category: str | None = None
    anomaly_score: float | None = None
    reviewer: str = "demo-reviewer"
    reason: str | None = None


class DecisionActionRequest(BaseModel):
    reviewer: str = "demo-reviewer"
    reason: str = ""
    replacement_risk_category: str | None = None
    review_date: str | None = None


class DecisionEvidenceRequest(BaseModel):
    evidence: list[dict]


class DecisionOut(BaseModel):
    decision_id: str
    asset_id: str
    asset_type: str
    model_version: str | None
    predicted_risk_probability: float | None
    risk_category: str | None
    anomaly_score: float | None
    decision_status: str
    decision_reason: str | None
    replacement_risk_category: str | None
    reviewer: str
    created_at: str
    updated_at: str
    decided_at: str | None


class DecisionEventOut(BaseModel):
    event_id: str
    previous_status: str | None
    new_status: str
    action: str
    reviewer: str
    reason: str | None
    timestamp: str


class DecisionEvidenceOut(BaseModel):
    id: int
    document_id: str
    chunk_id: str
    document_title: str
    revision: str
    page_number: int | None
    excerpt: str
    source_checksum: str


def _decision_out(decision) -> DecisionOut:
    return DecisionOut(
        decision_id=str(decision.decision_id),
        asset_id=decision.asset_id,
        asset_type=decision.asset_type,
        model_version=decision.model_version,
        predicted_risk_probability=(
            float(decision.predicted_risk_probability) if decision.predicted_risk_probability is not None else None
        ),
        risk_category=decision.risk_category,
        anomaly_score=float(decision.anomaly_score) if decision.anomaly_score is not None else None,
        decision_status=decision.decision_status,
        decision_reason=decision.decision_reason,
        replacement_risk_category=decision.replacement_risk_category,
        reviewer=decision.reviewer,
        created_at=decision.created_at.isoformat(),
        updated_at=decision.updated_at.isoformat(),
        decided_at=decision.decided_at.isoformat() if decision.decided_at else None,
    )


def _handle_error(exc: DecisionError):
    raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=Page[DecisionOut])
def list_decisions_endpoint(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
):
    items, total = list_decisions(session, status=status, limit=limit, offset=offset)
    return Page(items=[_decision_out(d) for d in items], total=total, limit=limit, offset=offset)


@router.post("", response_model=DecisionOut, status_code=201)
def create_decision_endpoint(request: DecisionCreateRequest, session: Session = Depends(get_db)):
    try:
        decision = create_decision(
            session,
            asset_id=request.asset_id,
            asset_type=request.asset_type,
            model_version=request.model_version,
            predicted_risk_probability=request.predicted_risk_probability,
            risk_category=request.risk_category,
            anomaly_score=request.anomaly_score,
            reviewer=request.reviewer,
            reason=request.reason,
        )
        session.commit()
    except DecisionError as exc:
        session.rollback()
        _handle_error(exc)
    return _decision_out(decision)


@router.get("/{decision_id}", response_model=DecisionOut)
def get_decision_endpoint(decision_id: str, session: Session = Depends(get_db)):
    try:
        decision = get_decision(session, UUID(decision_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="decision not found")
    if decision is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return _decision_out(decision)


@router.post("/{decision_id}/review", response_model=DecisionOut)
def review_endpoint(decision_id: str, request: DecisionActionRequest, session: Session = Depends(get_db)):
    try:
        decision = review_decision(session, UUID(decision_id), reviewer=request.reviewer, reason=request.reason or None)
        session.commit()
    except (DecisionError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _decision_out(decision)


@router.post("/{decision_id}/approve", response_model=DecisionOut)
def approve_endpoint(decision_id: str, request: DecisionActionRequest, session: Session = Depends(get_db)):
    try:
        decision = approve_decision(session, UUID(decision_id), reviewer=request.reviewer, reason=request.reason)
        session.commit()
    except (DecisionError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _decision_out(decision)


@router.post("/{decision_id}/reject", response_model=DecisionOut)
def reject_endpoint(decision_id: str, request: DecisionActionRequest, session: Session = Depends(get_db)):
    try:
        decision = reject_decision(session, UUID(decision_id), reviewer=request.reviewer, reason=request.reason)
        session.commit()
    except (DecisionError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _decision_out(decision)


@router.post("/{decision_id}/override", response_model=DecisionOut)
def override_endpoint(decision_id: str, request: DecisionActionRequest, session: Session = Depends(get_db)):
    try:
        decision = override_decision(
            session,
            UUID(decision_id),
            reviewer=request.reviewer,
            reason=request.reason,
            replacement_risk_category=request.replacement_risk_category or "",
        )
        session.commit()
    except (DecisionError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _decision_out(decision)


@router.post("/{decision_id}/escalate", response_model=DecisionOut)
def escalate_endpoint(decision_id: str, request: DecisionActionRequest, session: Session = Depends(get_db)):
    try:
        decision = escalate_decision(session, UUID(decision_id), reviewer=request.reviewer, reason=request.reason)
        session.commit()
    except (DecisionError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _decision_out(decision)


@router.post("/{decision_id}/defer", response_model=DecisionOut)
def defer_endpoint(decision_id: str, request: DecisionActionRequest, session: Session = Depends(get_db)):
    from datetime import datetime

    review_date = None
    if request.review_date:
        review_date = datetime.fromisoformat(request.review_date)
    try:
        decision = defer_decision(session, UUID(decision_id), reviewer=request.reviewer, reason=request.reason, review_date=review_date)
        session.commit()
    except (DecisionError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _decision_out(decision)


@router.post("/{decision_id}/evidence", response_model=list[DecisionEvidenceOut])
def associate_evidence_endpoint(decision_id: str, request: DecisionEvidenceRequest, session: Session = Depends(get_db)):
    try:
        created = associate_evidence(session, UUID(decision_id), request.evidence, validate=True)
        session.commit()
    except (DecisionError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return [
        DecisionEvidenceOut(
            id=item.id,
            document_id=item.document_id,
            chunk_id=item.chunk_id,
            document_title=item.document_title,
            revision=item.revision,
            page_number=item.page_number,
            excerpt=item.excerpt,
            source_checksum=item.source_checksum,
        )
        for item in created
    ]


@router.get("/{decision_id}/history", response_model=list[DecisionEventOut])
def history_endpoint(decision_id: str, session: Session = Depends(get_db)):
    try:
        events = get_history(session, UUID(decision_id))
    except (DecisionError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return [
        DecisionEventOut(
            event_id=str(event.event_id),
            previous_status=event.previous_status,
            new_status=event.new_status,
            action=event.action,
            reviewer=event.reviewer,
            reason=event.reason,
            timestamp=event.timestamp.isoformat(),
        )
        for event in events
    ]


@router.get("/{decision_id}/evidence", response_model=list[DecisionEvidenceOut])
def evidence_endpoint(decision_id: str, session: Session = Depends(get_db)):
    try:
        items = get_evidence(session, UUID(decision_id))
    except (DecisionError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return [
        DecisionEvidenceOut(
            id=item.id,
            document_id=item.document_id,
            chunk_id=item.chunk_id,
            document_title=item.document_title,
            revision=item.revision,
            page_number=item.page_number,
            excerpt=item.excerpt,
            source_checksum=item.source_checksum,
        )
        for item in items
    ]
