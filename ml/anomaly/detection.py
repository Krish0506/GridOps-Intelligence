"""Anomaly detection for GridOps Intelligence (Milestone 3, independent of labels, pure Python)."""

from __future__ import annotations

from typing import Sequence


def fit_robust_baseline(rows: list[dict[str, object]]) -> tuple[dict[str, float], dict[str, float]]:
    """Fit median and MAD baselines over numeric model features."""
    from ml.features.asset import boolean_feature_names, numeric_feature_names

    numeric_names = list(numeric_feature_names()) + list(boolean_feature_names())
    matrix: list[list[float]] = []
    for row in rows:
        matrix.append([float(row.get(name) if row.get(name) is not None else 0.0) for name in numeric_names])
    medians: dict[str, float] = {}
    mads: dict[str, float] = {}
    for index, name in enumerate(numeric_names):
        values = sorted(row[index] for row in matrix)
        median = values[len(values) // 2] if values else 0.0
        deviations = sorted(abs(value - median) for value in values)
        mad = deviations[len(deviations) // 2] * 1.4826 if deviations else 1e-9
        medians[name] = median
        mads[name] = mad if mad > 0 else 1e-9
    return medians, mads


def robust_z_scores(
    rows: Sequence[dict[str, object]],
    medians: dict[str, float],
    mads: dict[str, float],
) -> list[dict[str, float]]:
    """Per-row robust z-score maps against fitted median/MAD baselines."""
    from ml.features.asset import boolean_feature_names, numeric_feature_names

    numeric_names = list(numeric_feature_names()) + list(boolean_feature_names())
    scores: list[dict[str, float]] = []
    for row in rows:
        scores.append(
            {
                name: abs(
                    (float(row.get(name) if row.get(name) is not None else 0.0) - medians.get(name, 0.0))
                    / mads.get(name, 1e-9)
                )
                for name in numeric_names
            }
        )
    return scores


def asset_anomaly_score(
    row: dict[str, object],
    medians: dict[str, float],
    mads: dict[str, float],
) -> float:
    """Aggregate robust z-scores into a single per-asset anomaly magnitude."""
    scores = robust_z_scores([row], medians, mads)
    return max(scores[0].values()) if scores and scores[0] else 0.0


__all__ = ["asset_anomaly_score", "fit_robust_baseline", "robust_z_scores"]
