"""Operational risk prioritization output (Milestone 3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ml.anomaly import asset_anomaly_score, fit_robust_baseline, robust_z_scores


@dataclass(frozen=True)
class RiskRecord:
    """One asset's prioritization output.

    Concepts kept separate on purpose: an anomaly score is not a calibrated
    failure probability, and a model probability is only meaningful when a
    validated model exists.
    """

    asset_id: str
    asset_type: str
    prediction_cutoff: datetime
    risk_category: str
    anomaly_score: float
    model_probability: float | None
    data_quality: dict[str, object]
    primary_drivers: list[str]
    model_version: str | None
    limitations: list[str]


def build_risk_records(
    *,
    snapshots: list[dict[str, object]],
    model_probabilities: dict[str, float] | None,
    model_version: str | None,
    prediction_cutoff: datetime,
    medians: dict[str, float] | None = None,
    mads: dict[str, float] | None = None,
    limitations: list[str] | None = None,
) -> list[RiskRecord]:
    """Assemble per-asset risk prioritization records from feature snapshots."""
    medians = medians or {}
    mads = mads or {}
    records: list[RiskRecord] = []
    for snapshot in snapshots:
        asset_id = str(snapshot.get("asset_id") or "")
        probability = (model_probabilities or {}).get(asset_id)
        anomaly = asset_anomaly_score(snapshot, medians, mads)
        z_map = robust_z_scores([snapshot], medians, mads)[0]
        primary_drivers = [
            name
            for name, _score in sorted(z_map.items(), key=lambda item: item[1], reverse=True)[:3]
            if name
        ]
        if probability is None:
            category = "anomaly" if anomaly > 1.0 else "normal"
        else:
            category = "predicted_failure" if float(probability) >= 0.5 else "predicted_no_failure"
        records.append(
            RiskRecord(
                asset_id=asset_id,
                asset_type=str(snapshot.get("asset_type") or "unknown"),
                prediction_cutoff=prediction_cutoff,
                risk_category=category,
                anomaly_score=float(anomaly),
                model_probability=None if probability is None else float(probability),
                data_quality={
                    "telemetry_has_readings": bool(snapshot.get("telemetry_has_readings")),
                    "telemetry_sparse": bool(snapshot.get("telemetry_sparse")),
                    "quality_history_group_count": int(snapshot.get("quality_history_group_count") or 0),
                },
                primary_drivers=primary_drivers,
                model_version=model_version,
                limitations=list(limitations or []),
            )
        )
    return records


__all__ = ["RiskRecord", "build_risk_records"]
