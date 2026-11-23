"""Tests for the Milestone 5 engineering decision workflow."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from decisions.service import (
    DecisionError,
    approve_decision,
    associate_evidence,
    create_decision,
    defer_decision,
    escalate_decision,
    get_evidence,
    get_history,
    override_decision,
    reject_decision,
    review_decision,
)


def test_create_decision_starts_pending(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers", reviewer="alice")
    db_session.commit()
    assert decision.decision_status == "PENDING_REVIEW"
    history = get_history(db_session, decision.decision_id)
    assert len(history) == 1
    assert history[0].action == "CREATE"


def test_review_transition(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    reviewed = review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    assert reviewed.decision_status == "IN_REVIEW"
    assert len(get_history(db_session, decision.decision_id)) == 2


def test_approve_requires_reason(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    with pytest.raises(DecisionError):
        approve_decision(db_session, decision.decision_id, reviewer="alice", reason="")
    db_session.rollback()


def test_approve_with_reason(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    approved = approve_decision(db_session, decision.decision_id, reviewer="alice", reason="Evidence supports maintenance")
    db_session.commit()
    assert approved.decision_status == "APPROVED"
    assert approved.decision_reason == "Evidence supports maintenance"


def test_invalid_transition_rejected(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    with pytest.raises(DecisionError):
        approve_decision(db_session, decision.decision_id, reviewer="alice", reason="no review")
    db_session.rollback()


def test_override_requires_replacement_category(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    with pytest.raises(DecisionError):
        override_decision(db_session, decision.decision_id, reviewer="alice", reason="r", replacement_risk_category="")
    db_session.rollback()


def test_override_with_replacement(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers", risk_category="high")
    db_session.commit()
    review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    overridden = override_decision(db_session, decision.decision_id, reviewer="alice", reason="r", replacement_risk_category="medium")
    db_session.commit()
    assert overridden.decision_status == "OVERRIDDEN"
    assert overridden.replacement_risk_category == "medium"
    assert overridden.risk_category == "high"  # original preserved


def test_reject_requires_reason(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    with pytest.raises(DecisionError):
        reject_decision(db_session, decision.decision_id, reviewer="alice", reason="")
    db_session.rollback()


def test_escalate_requires_reason(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    with pytest.raises(DecisionError):
        escalate_decision(db_session, decision.decision_id, reviewer="alice", reason="")
    db_session.rollback()


def test_defer_requires_reason(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    with pytest.raises(DecisionError):
        defer_decision(db_session, decision.decision_id, reviewer="alice", reason="")
    db_session.rollback()


def test_defer_with_reason(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    deferred = defer_decision(db_session, decision.decision_id, reviewer="alice", reason="waiting for data")
    db_session.commit()
    assert deferred.decision_status == "DEFERRED"


def test_evidence_association_validates_chunk(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    with pytest.raises(DecisionError):
        associate_evidence(
            db_session,
            decision.decision_id,
            [{"document_id": "D", "chunk_id": "missing", "document_title": "T", "revision": "R", "excerpt": "x", "source_checksum": "abc"}],
            validate=True,
        )
    db_session.rollback()


def test_history_is_append_only(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    approve_decision(db_session, decision.decision_id, reviewer="alice", reason="ok")
    db_session.commit()
    history = get_history(db_session, decision.decision_id)
    assert len(history) == 3
    actions = [e.action for e in history]
    assert actions == ["CREATE", "REVIEW", "APPROVE"]


def test_prediction_snapshot_preserved(db_session: Session) -> None:
    decision = create_decision(
        db_session,
        asset_id="T-00001",
        asset_type="transformers",
        model_version="v1",
        predicted_risk_probability=0.9,
        risk_category="high",
        anomaly_score=2.5,
    )
    db_session.commit()
    review_decision(db_session, decision.decision_id, reviewer="alice")
    db_session.commit()
    history = get_history(db_session, decision.decision_id)
    event = history[-1]
    assert event.prediction_snapshot is not None
    assert event.prediction_snapshot["risk_category"] == "high"


def test_get_evidence_empty(db_session: Session) -> None:
    decision = create_decision(db_session, asset_id="T-00001", asset_type="transformers")
    db_session.commit()
    assert get_evidence(db_session, decision.decision_id) == []
