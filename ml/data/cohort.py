"""Build the leakage-safe supervised modeling dataset from feature snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ml.features.asset import (
    categorical_feature_names,
    identifier_columns,
    metadata_columns,
    model_feature_names,
    numeric_feature_names,
)
from ml.features.labels import OutcomeLabel, OutcomeDecision

LABEL_EXCLUDED_COLUMNS = (
    "failure_id",
    "failure_timestamp",
    "failure_severity",
    "downtime_hours",
    "failure_category",
)


def confirmed_healthy_until_for_snapshots(
    snapshots: list[dict[str, object]],
    cutoff: datetime,
    observation_days: int,
    horizon_end: datetime,
    failed_asset_ids: set[str],
) -> dict[str, datetime]:
    """Return a confirmed-negative confirmation map for complete-history assets.

    Mirrors the Milestone 2B generator's negative-label rule: an asset with a
    complete observation history and no failure is confirmed negative for the
    whole window.
    """
    result: dict[str, datetime] = {}
    for snapshot in snapshots:
        asset_id = str(snapshot.get("asset_id") or "")
        if asset_id in failed_asset_ids:
            continue
        install = snapshot.get("asset_install_date")
        if isinstance(install, date) and install + timedelta(days=observation_days) <= cutoff.date():
            result[asset_id] = horizon_end
    return result


@dataclass(frozen=True)
class ModelingDataset:
    """Immutable supervised dataset derived from safe feature snapshots."""

    features: list[dict[str, object]]
    labels: list[int]
    asset_ids: list[str]
    positive_count: int
    negative_count: int
    excluded_unknown_count: int

    @property
    def is_binary_ready(self) -> bool:
        return self.positive_count > 0 and self.negative_count > 0


def build_modeling_dataset(
    snapshots: list[dict[str, object]],
    decisions: list[OutcomeDecision],
) -> ModelingDataset:
    """Combine feature snapshots with three-state outcome decisions.

    Only confirmed positives and confirmed negatives become rows.  Unknown
    decisions are excluded.  Only documented model predictor columns are used;
    identifiers, metadata, timestamps, cutoffs, event bounds, and label
    attributes never enter the modeling rows.
    """
    model_names = list(model_feature_names())
    excluded = set(identifier_columns()) | set(metadata_columns()) | set(LABEL_EXCLUDED_COLUMNS)

    decision_by_asset = {decision.asset_id: decision for decision in decisions}
    features: list[dict[str, object]] = []
    labels: list[int] = []
    asset_ids: list[str] = []
    positive_count = 0
    negative_count = 0
    excluded_unknown_count = 0

    for snapshot in snapshots:
        asset_id = str(snapshot.get("asset_id") or "")
        decision = decision_by_asset.get(asset_id)
        if decision is None or decision.label is OutcomeLabel.UNKNOWN:
            excluded_unknown_count += 1
            continue
        row: dict[str, object] = {}
        for name in model_names:
            if name in excluded or name.startswith("feature_"):
                continue
            row[name] = snapshot.get(name)
        features.append(row)
        asset_ids.append(asset_id)
        if decision.label is OutcomeLabel.CONFIRMED_POSITIVE:
            labels.append(1)
            positive_count += 1
        elif decision.label is OutcomeLabel.CONFIRMED_NEGATIVE:
            labels.append(0)
            negative_count += 1
        else:  # pragma: no cover - defensive
            excluded_unknown_count += 1
            features.pop()
            labels.pop()
            asset_ids.pop()

    return ModelingDataset(
        features=features,
        labels=labels,
        asset_ids=asset_ids,
        positive_count=positive_count,
        negative_count=negative_count,
        excluded_unknown_count=excluded_unknown_count,
    )
