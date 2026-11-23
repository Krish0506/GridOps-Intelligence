"""Tests for three-state outcome labelling and censoring semantics."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from ml.features import (
    FailureRecord,
    InsufficientConfirmedNegativesError,
    OutcomeDecision,
    OutcomeLabel,
    TrainingCohort,
    build_training_cohort,
    classify_outcome,
    classify_outcomes,
    trainable_outcomes,
)

CUTOFF = datetime(2024, 6, 1, 12, 0, 0)
OBSERVATION_END = CUTOFF + timedelta(days=30)


def make_failure(timestamp: datetime, *, failure_id: str = "FAIL-00001") -> FailureRecord:
    return FailureRecord(
        failure_id=failure_id,
        asset_id="T-00001",
        failure_category="winding fault",
        failure_timestamp=timestamp,
        failure_severity=4,
        downtime_hours=12.0,
    )


def test_failure_inside_observation_window_is_positive() -> None:
    decision = classify_outcome(
        [make_failure(CUTOFF + timedelta(days=5))],
        "T-00001",
        CUTOFF,
        OBSERVATION_END,
    )

    assert decision.label is OutcomeLabel.CONFIRMED_POSITIVE
    assert decision.failure_id == "FAIL-00001"


def test_failure_before_cutoff_is_not_a_future_positive() -> None:
    decision = classify_outcome(
        [make_failure(CUTOFF - timedelta(days=1))],
        "T-00001",
        CUTOFF,
        OBSERVATION_END,
    )

    assert decision.label is OutcomeLabel.UNKNOWN


def test_failure_after_observation_end_is_unknown() -> None:
    decision = classify_outcome(
        [make_failure(OBSERVATION_END + timedelta(days=1))],
        "T-00001",
        CUTOFF,
        OBSERVATION_END,
    )

    assert decision.label is OutcomeLabel.UNKNOWN


def test_failure_exactly_at_cutoff_is_not_a_future_positive() -> None:
    """A failure at the prediction cutoff is already known at prediction time.

    The observation window is open-ended to the right but the failure bound is
    exclusive on the left, so a failure exactly at the cutoff is not a future
    positive.
    """
    decision = classify_outcome(
        [make_failure(CUTOFF)],
        "T-00001",
        CUTOFF,
        OBSERVATION_END,
    )

    assert decision.label is OutcomeLabel.UNKNOWN
    assert decision.failure_timestamp is None


def test_trainable_outcomes_exclude_unknown() -> None:
    positives = [
        OutcomeDecision(
            asset_id="T-1",
            label=OutcomeLabel.CONFIRMED_POSITIVE,
            reason="failure recorded inside the observation window",
            failure_id="FAIL-1",
        )
    ]
    negatives = [
        OutcomeDecision(
            asset_id="T-2",
            label=OutcomeLabel.CONFIRMED_NEGATIVE,
            reason="explicit health confirmation covers the observation window",
            observation_end=OBSERVATION_END,
        )
    ]
    unknown = [
        OutcomeDecision(
            asset_id="T-3",
            label=OutcomeLabel.UNKNOWN,
            reason="no failure recorded and no explicit health confirmation (censored)",
            observation_end=OBSERVATION_END,
        )
    ]

    trainable = trainable_outcomes([*positives, *negatives, *unknown])

    assert [decision.asset_id for decision in trainable] == ["T-1", "T-2"]
    assert all(decision.label is not OutcomeLabel.UNKNOWN for decision in trainable)


def test_training_cohort_excludes_unknown_and_is_binary_ready() -> None:
    decisions = [
        OutcomeDecision(
            asset_id="T-1",
            label=OutcomeLabel.CONFIRMED_POSITIVE,
            reason="failure recorded inside the observation window",
            failure_id="FAIL-1",
        ),
        OutcomeDecision(
            asset_id="T-2",
            label=OutcomeLabel.CONFIRMED_NEGATIVE,
            reason="explicit health confirmation covers the observation window",
            observation_end=OBSERVATION_END,
        ),
        OutcomeDecision(
            asset_id="T-3",
            label=OutcomeLabel.UNKNOWN,
            reason="no failure recorded and no explicit health confirmation (censored)",
            observation_end=OBSERVATION_END,
        ),
    ]

    cohort = build_training_cohort(decisions)

    assert isinstance(cohort, TrainingCohort)
    assert cohort.positive_count == 1
    assert cohort.negative_count == 1
    assert cohort.excluded_unknown_count == 1
    assert cohort.has_positives is True
    assert cohort.has_negatives is True
    assert cohort.is_binary_ready is True
    assert [decision.asset_id for decision in cohort.decisions] == ["T-1", "T-2"]


def test_training_cohort_requires_confirmed_negatives() -> None:
    decisions = [
        OutcomeDecision(
            asset_id="T-1",
            label=OutcomeLabel.CONFIRMED_POSITIVE,
            reason="failure recorded inside the observation window",
            failure_id="FAIL-1",
        ),
        OutcomeDecision(
            asset_id="T-3",
            label=OutcomeLabel.UNKNOWN,
            reason="no failure recorded and no explicit health confirmation (censored)",
            observation_end=OBSERVATION_END,
        ),
    ]

    with pytest.raises(InsufficientConfirmedNegativesError):
        build_training_cohort(decisions)


def test_absent_failure_is_not_assumed_healthy() -> None:
    decision = classify_outcome([], "T-00001", CUTOFF, OBSERVATION_END)

    assert decision.label is OutcomeLabel.UNKNOWN
    assert "censored" in decision.reason


def test_explicit_health_confirmation_can_produce_negative() -> None:
    decision = classify_outcome(
        [],
        "T-00001",
        CUTOFF,
        OBSERVATION_END,
        confirmed_healthy_until=OBSERVATION_END,
    )

    assert decision.label is OutcomeLabel.CONFIRMED_NEGATIVE


def test_partial_health_confirmation_stays_unknown() -> None:
    decision = classify_outcome(
        [],
        "T-00001",
        CUTOFF,
        OBSERVATION_END,
        confirmed_healthy_until=CUTOFF + timedelta(days=10),
    )

    assert decision.label is OutcomeLabel.UNKNOWN


def test_observation_end_must_follow_cutoff() -> None:
    import pytest

    with pytest.raises(ValueError):
        classify_outcome([], "T-00001", CUTOFF, CUTOFF)


def test_classify_outcomes_is_sorted_and_deterministic() -> None:
    failures = [
        FailureRecord(
            failure_id="FAIL-2",
            asset_id="T-2",
            failure_category="breaker trip",
            failure_timestamp=CUTOFF + timedelta(days=3),
            failure_severity=2,
            downtime_hours=1.0,
        )
    ]

    first = classify_outcomes(failures, ["T-2", "T-1", "T-2"], CUTOFF, OBSERVATION_END)
    second = classify_outcomes(failures, ["T-1", "T-2"], CUTOFF, OBSERVATION_END)

    assert [decision.asset_id for decision in first] == ["T-1", "T-2"]
    assert first == second
    assert first[1].label is OutcomeLabel.CONFIRMED_POSITIVE
    assert first[0].label is OutcomeLabel.UNKNOWN
