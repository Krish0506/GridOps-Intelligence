"""Failure-outcome labelling with explicit censoring.

A missing failure record is **not** evidence of health.  The synthetic data only
records failures, so most assets have no observed outcome at all.  This module
therefore returns one of three states:

* ``CONFIRMED_POSITIVE`` -- a failure is recorded in the observation window.
* ``CONFIRMED_NEGATIVE`` -- an explicit health confirmation covers the whole
  observation window (callers must supply it; it is never inferred).
* ``UNKNOWN`` -- no failure and no explicit health confirmation.  This includes
  censored assets and must not be turned into a negative label.

The synthetic generator's telemetry-derived risk score is deliberately not an
input here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ml.features.cutoff import normalize_timestamp
from ml.features.types import FailureRecord


class OutcomeLabel(str, Enum):
    """Training-label states supported by the available data."""

    CONFIRMED_POSITIVE = "confirmed_positive"
    CONFIRMED_NEGATIVE = "confirmed_negative"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class OutcomeDecision:
    """Label plus the evidence that produced it."""

    asset_id: str
    label: OutcomeLabel
    reason: str
    failure_id: str | None = None
    failure_timestamp: datetime | None = None
    observation_end: datetime | None = None
    evidence: str | None = None


class InsufficientConfirmedNegativesError(ValueError):
    """Raised when no defensible confirmed-negative cohort exists.

    A binary training cohort requires at least one confirmed negative.  The
    available synthetic schema has no health-confirmation source, so the current
    dataset cannot produce a valid binary cohort without caller-invented
    confirmations.  Never silently train on :attr:`OutcomeLabel.UNKNOWN` rows.
    """


def classify_outcome(
    failures: Iterable[FailureRecord],
    asset_id: str,
    prediction_cutoff: datetime,
    observation_end: datetime,
    confirmed_healthy_until: datetime | None = None,
) -> OutcomeDecision:
    """Classify the outcome for ``asset_id`` between cutoff and observation end.

    A failure counts as positive only when
    ``prediction_cutoff < failure_timestamp <= observation_end``.  A failure at
    or before the cutoff is already known at prediction time and is not a
    future outcome.

    ``confirmed_healthy_until`` represents an explicit external confirmation
    (for example a passed inspection with a validity horizon).  Without it, the
    absence of a failure yields ``UNKNOWN``.
    """
    cutoff = normalize_timestamp(prediction_cutoff)
    end = normalize_timestamp(observation_end)
    if end <= cutoff:
        raise ValueError("observation_end must be after prediction_cutoff")

    eligible = sorted(
        (
            failure
            for failure in failures
            if failure.asset_id == asset_id
            and cutoff < normalize_timestamp(failure.failure_timestamp) <= end
        ),
        key=lambda failure: normalize_timestamp(failure.failure_timestamp),
    )
    if eligible:
        first = eligible[0]
        return OutcomeDecision(
            asset_id=asset_id,
            label=OutcomeLabel.CONFIRMED_POSITIVE,
            reason="failure recorded inside the observation window",
            failure_id=first.failure_id,
            failure_timestamp=normalize_timestamp(first.failure_timestamp),
            observation_end=end,
            evidence=f"failure_id={first.failure_id}",
        )

    if confirmed_healthy_until is not None:
        healthy_until = normalize_timestamp(confirmed_healthy_until)
        if healthy_until >= end:
            return OutcomeDecision(
                asset_id=asset_id,
                label=OutcomeLabel.CONFIRMED_NEGATIVE,
                reason="explicit health confirmation covers the observation window",
                observation_end=end,
                evidence=f"confirmed_healthy_until={healthy_until.isoformat()}",
            )

    return OutcomeDecision(
        asset_id=asset_id,
        label=OutcomeLabel.UNKNOWN,
        reason="no failure recorded and no explicit health confirmation (censored)",
        observation_end=end,
        evidence="no_failure_no_confirmation",
    )


def classify_outcomes(
    failures: Iterable[FailureRecord],
    asset_ids: Iterable[str],
    prediction_cutoff: datetime,
    observation_end: datetime,
    confirmed_healthy_until: dict[str, datetime] | None = None,
) -> list[OutcomeDecision]:
    """Classify many assets deterministically in ascending ``asset_id`` order."""
    failure_list = list(failures)
    confirmations = confirmed_healthy_until or {}
    return [
        classify_outcome(
            failure_list,
            asset_id,
            prediction_cutoff,
            observation_end,
            confirmed_healthy_until=confirmations.get(asset_id),
        )
        for asset_id in sorted(set(asset_ids))
    ]


@dataclass(frozen=True, slots=True)
class TrainingCohort:
    """Trainable rows derived from outcome decisions, with censoring applied."""

    decisions: tuple[OutcomeDecision, ...]
    positive_count: int
    negative_count: int
    excluded_unknown_count: int

    @property
    def has_positives(self) -> bool:
        return self.positive_count > 0

    @property
    def has_negatives(self) -> bool:
        return self.negative_count > 0

    @property
    def is_binary_ready(self) -> bool:
        """True only when both a confirmed-positive and a confirmed-negative row exist."""
        return self.has_positives and self.has_negatives


def trainable_outcomes(
    decisions: Iterable[OutcomeDecision],
) -> list[OutcomeDecision]:
    """Return only decisions that are safe to use as supervised training rows.

    ``OutcomeLabel.UNKNOWN`` rows are censored and are never returned here, so a
    trainer cannot accidentally train on an asset that simply had no recorded
    outcome.
    """
    return sorted(
        (decision for decision in decisions if decision.label is not OutcomeLabel.UNKNOWN),
        key=lambda decision: decision.asset_id,
    )


def build_training_cohort(
    decisions: Iterable[OutcomeDecision],
    *,
    require_binary: bool = True,
) -> TrainingCohort:
    """Build a training cohort from outcome decisions.

    Unknown decisions are excluded.  When ``require_binary`` is true, a valid
    binary cohort (confirmed positive + confirmed negative) is required; without
    at least one confirmed negative the call raises
    :class:`InsufficientConfirmedNegativesError` instead of returning a cohort
    that would silently train on unknowns or on an invented negative class.
    """
    decision_list = sorted(decisions, key=lambda decision: decision.asset_id)
    trainable = trainable_outcomes(decision_list)
    positives = [
        decision
        for decision in trainable
        if decision.label is OutcomeLabel.CONFIRMED_POSITIVE
    ]
    negatives = [
        decision
        for decision in trainable
        if decision.label is OutcomeLabel.CONFIRMED_NEGATIVE
    ]

    if require_binary and not (positives and negatives):
        raise InsufficientConfirmedNegativesError(
            "no valid binary training cohort can be built: "
            f"{len(positives)} confirmed positive(s) and {len(negatives)} confirmed "
            f"negative(s) available; unknown (censored) decisions are excluded. "
            "A confirmed negative requires an explicit health confirmation and "
            "the current synthetic schema does not provide one."
        )

    return TrainingCohort(
        decisions=tuple(trainable),
        positive_count=len(positives),
        negative_count=len(negatives),
        excluded_unknown_count=len(decision_list) - len(trainable),
    )
