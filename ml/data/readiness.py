"""Data-readiness assessment for supervised predictive modeling.

The readiness gate answers one question before any model training happens:
*does the current synthetic evaluation dataset contain enough defensible
confirmed-positive and confirmed-negative observations to justify fitting a
binary failure model?*

The assessment is deliberately explicit and conservative.  Minimum sample
requirements are configurable, never silently lowered, and the verdict is derived
only from the counts and diagnostics supplied by the caller.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

MINIMUM_CONFIRMED_POSITIVES = 100
MINIMUM_CONFIRMED_NEGATIVES = 100


@dataclass(frozen=True)
class DataReadinessReport:
    """Outcome of a data-readiness assessment."""

    dataset_name: str
    generator: str
    seed: int
    asset_count: int
    snapshot_count: int
    prediction_cutoff: datetime
    horizon_end: datetime
    confirmed_positive_count: int
    confirmed_negative_count: int
    unknown_count: int
    positive_rate: float
    missingness: dict[str, float]
    feature_count: int
    excluded_columns: list[str]
    split_feasible: bool
    class_balance: dict[str, float]
    ready: bool
    reasons: list[str]


def assess_readiness(
    *,
    dataset_name: str,
    generator: str,
    seed: int,
    asset_count: int,
    snapshot_count: int,
    prediction_cutoff: datetime,
    horizon_end: datetime,
    confirmed_positive: int,
    confirmed_negative: int,
    unknown: int,
    missingness: Mapping[str, float] = (),
    feature_count: int = 0,
    excluded_columns: Sequence[str] = (),
    min_confirmed_positives: int = MINIMUM_CONFIRMED_POSITIVES,
    min_confirmed_negatives: int = MINIMUM_CONFIRMED_NEGATIVES,
) -> DataReadinessReport:
    """Assess whether the evaluation data can support supervised classification.

    A dataset is ready when it has at least ``min_confirmed_positives``
    confirmed positives and at least ``min_confirmed_negatives`` confirmed
    negatives, and when at least one feature snapshot is available.  Unknown
    outcomes are reported but never satisfy a class requirement.
    """
    total = confirmed_positive + confirmed_negative + unknown
    positive_rate = (
        confirmed_positive / (confirmed_positive + confirmed_negative)
        if (confirmed_positive + confirmed_negative) > 0
        else 0.0
    )
    reasons: list[str] = []
    if confirmed_positive < min_confirmed_positives:
        reasons.append(
            f"insufficient confirmed positives: {confirmed_positive} < {min_confirmed_positives}"
        )
    if confirmed_negative < min_confirmed_negatives:
        reasons.append(
            f"insufficient confirmed negatives: {confirmed_negative} < {min_confirmed_negatives}"
        )
    if snapshot_count <= 0:
        reasons.append("no feature snapshots available")
    if confirmed_positive + confirmed_negative <= 0:
        reasons.append("no confirmed outcomes available for classification")

    ready = not reasons

    return DataReadinessReport(
        dataset_name=dataset_name,
        generator=generator,
        seed=seed,
        asset_count=asset_count,
        snapshot_count=snapshot_count,
        prediction_cutoff=prediction_cutoff,
        horizon_end=horizon_end,
        confirmed_positive_count=confirmed_positive,
        confirmed_negative_count=confirmed_negative,
        unknown_count=unknown,
        positive_rate=positive_rate,
        missingness=dict(missingness),
        feature_count=feature_count,
        excluded_columns=list(excluded_columns),
        split_feasible=True,  # one snapshot per asset -> documented asset-level split
        class_balance={
            "confirmed_positive": float(confirmed_positive),
            "confirmed_negative": float(confirmed_negative),
            "unknown": float(unknown),
            "positive_rate_among_confirmed": positive_rate,
        },
        ready=ready,
        reasons=reasons,
    )
