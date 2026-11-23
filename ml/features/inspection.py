"""Historical inspection features.

Source: ``inspections``.  An inspection is eligible only when
``inspection_date < prediction_cutoff``.  Inspections are often triggered by
failures, so callers should pass a cutoff before the event of interest; the
strict bound is what prevents post-failure inspections from entering features.

Condition and severity are ordinal, so both the raw category and a numeric
score are emitted.  The score mapping is fixed and documented:

* condition: ``excellent=3``, ``good=2``, ``fair=1``, ``poor=0``
* severity:  ``none=0``, ``low=1``, ``medium=2``, ``high=3``
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from datetime import datetime

from ml.features.cutoff import days_between, filter_window, normalize_timestamp
from ml.features.telemetry import summarize_sensor
from ml.features.types import InspectionRecord

CONDITIONS: tuple[str, ...] = ("excellent", "good", "fair", "poor")
SEVERITIES: tuple[str, ...] = ("none", "low", "medium", "high")

CONDITION_SCORES: dict[str, int] = {"excellent": 3, "good": 2, "fair": 1, "poor": 0}
SEVERITY_SCORES: dict[str, int] = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / float(denominator), 6)


def inspection_features(
    inspections: Iterable[InspectionRecord],
    prediction_cutoff: datetime,
    *,
    asset_id: str,
    exclude_at_or_after: datetime | None = None,
) -> dict[str, object]:
    """Aggregate inspections dated strictly before ``prediction_cutoff``.

    Parameters
    ----------
    inspections:
        Inspection rows for a single asset; rows for other assets are ignored.
    prediction_cutoff:
        Exclusive upper bound for inspection eligibility.
    asset_id:
        Asset identifier the rows are scoped to; rows for other assets are
        ignored.
    exclude_at_or_after:
        Optional event bound (typically the first known failure timestamp).
        Inspections at or after the bound are excluded, so a pre-failure
        snapshot contains no post-failure inspection context.
    """
    cutoff = normalize_timestamp(prediction_cutoff)
    scoped_inspections = [
        inspection for inspection in inspections if inspection.asset_id == asset_id
    ]
    eligible = filter_window(
        scoped_inspections,
        cutoff,
        key=lambda inspection: inspection.inspection_date,
        exclude_at_or_after=exclude_at_or_after,
    )
    total = len(eligible)

    record: dict[str, object] = {
        "inspection_count": total,
        "inspection_has_history": total > 0,
        "inspection_latest_condition": None,
        "inspection_latest_condition_score": None,
        "inspection_latest_severity": None,
        "inspection_latest_severity_score": None,
        "inspection_days_since_latest": None,
        "inspection_poor_or_fair_ratio": None,
        "inspection_high_severity_count": 0,
        "inspection_mean_severity_score": None,
        "inspection_condition_score_trend_per_day": None,
        "inspection_count_last_365_days": 0,
    }

    for condition in CONDITIONS:
        record[f"inspection_{condition}_count"] = 0
    for severity in SEVERITIES:
        record[f"inspection_severity_{severity}_count"] = 0

    if not eligible:
        return record

    ordered = sorted(
        eligible,
        key=lambda inspection: (
            normalize_timestamp(inspection.inspection_date),
            inspection.inspection_id,
        ),
    )
    latest = ordered[-1]

    for condition in CONDITIONS:
        record[f"inspection_{condition}_count"] = sum(
            1 for inspection in ordered if inspection.condition == condition
        )
    for severity in SEVERITIES:
        record[f"inspection_severity_{severity}_count"] = sum(
            1 for inspection in ordered if inspection.severity == severity
        )

    record["inspection_latest_condition"] = latest.condition
    record["inspection_latest_condition_score"] = CONDITION_SCORES.get(latest.condition)
    record["inspection_latest_severity"] = latest.severity
    record["inspection_latest_severity_score"] = SEVERITY_SCORES.get(latest.severity)
    record["inspection_days_since_latest"] = round(
        days_between(latest.inspection_date, cutoff), 6
    )

    poor_or_fair = int(record["inspection_fair_count"]) + int(  # type: ignore[arg-type]
        record["inspection_poor_count"]  # type: ignore[arg-type]
    )
    record["inspection_poor_or_fair_ratio"] = _ratio(poor_or_fair, total)
    record["inspection_high_severity_count"] = int(
        record["inspection_severity_high_count"]  # type: ignore[arg-type]
    )

    severity_scores = [
        SEVERITY_SCORES[inspection.severity]
        for inspection in ordered
        if inspection.severity in SEVERITY_SCORES
    ]
    if severity_scores:
        record["inspection_mean_severity_score"] = round(
            statistics.fmean(severity_scores), 6
        )

    condition_points = [
        (inspection.inspection_date, float(CONDITION_SCORES[inspection.condition]))
        for inspection in ordered
        if inspection.condition in CONDITION_SCORES
    ]
    record["inspection_condition_score_trend_per_day"] = summarize_sensor(
        condition_points
    ).trend_per_day

    record["inspection_count_last_365_days"] = sum(
        1 for inspection in ordered if days_between(inspection.inspection_date, cutoff) <= 365
    )

    return record


def inspection_feature_names() -> list[str]:
    """Ordered feature names produced by :func:`inspection_features`."""
    names = [
        "inspection_count",
        "inspection_has_history",
        "inspection_latest_condition",
        "inspection_latest_condition_score",
        "inspection_latest_severity",
        "inspection_latest_severity_score",
        "inspection_days_since_latest",
        "inspection_poor_or_fair_ratio",
        "inspection_high_severity_count",
        "inspection_mean_severity_score",
        "inspection_condition_score_trend_per_day",
        "inspection_count_last_365_days",
    ]
    names.extend(f"inspection_{condition}_count" for condition in CONDITIONS)
    names.extend(f"inspection_severity_{severity}_count" for severity in SEVERITIES)
    return names
