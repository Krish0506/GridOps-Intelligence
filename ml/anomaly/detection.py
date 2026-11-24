"""Anomaly detection for GridOps Intelligence (Milestone 3, independent of labels, pure Python)."""

from __future__ import annotations

import math
from typing import Sequence

# A robust z-score is a screening signal, not a calibrated probability.  Capping
# prevents a single near-constant feature from dominating the operational
# review ordering while retaining the relative ordering of extreme values.
DEFAULT_Z_CAP = 50.0


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, int(round(fraction * (len(sorted_values) - 1)))))
    return sorted_values[index]


def _scale_floor(median: float) -> float:
    """Return a small, feature-appropriate floor for a deviation scale."""
    magnitude = abs(median)
    if magnitude > 1_000_000:
        return magnitude * 1e-4
    if magnitude > 1_000:
        return magnitude * 1e-3
    if magnitude > 1:
        return magnitude * 1e-2
    return 1e-3


def fit_robust_baseline(rows: list[dict[str, object]]) -> tuple[dict[str, float], dict[str, float]]:
    """Fit median and robust scale baselines over numeric model features.

    The median absolute deviation (MAD) is preferred.  Many operational
    features are count-like and have a zero MAD because more than half of the
    assets share the same value; in that case the interquartile range and then
    the population standard deviation are used as fallbacks.  A final
    feature-scale floor prevents division by a vanishing number.
    """
    from ml.features.asset import boolean_feature_names, numeric_feature_names

    numeric_names = list(numeric_feature_names()) + list(boolean_feature_names())
    matrix: list[list[float]] = []
    for row in rows:
        matrix.append([float(row.get(name) if row.get(name) is not None else 0.0) for name in numeric_names])
    medians: dict[str, float] = {}
    mads: dict[str, float] = {}
    for index, name in enumerate(numeric_names):
        values = sorted(row[index] for row in matrix)
        if not values:
            medians[name] = 0.0
            mads[name] = 1e-3
            continue
        median = values[len(values) // 2]
        deviations = sorted(abs(value - median) for value in values)
        mad = deviations[len(deviations) // 2] * 1.4826
        if mad <= 0:
            q1 = _percentile(values, 0.25)
            q3 = _percentile(values, 0.75)
            iqr = q3 - q1
            mad = iqr / 1.349 if iqr > 0 else 0.0
        if mad <= 0:
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            mad = math.sqrt(variance) if variance > 0 else 0.0
        medians[name] = median
        mads[name] = max(mad, _scale_floor(median))
    return medians, mads


def robust_z_scores(
    rows: Sequence[dict[str, object]],
    medians: dict[str, float],
    mads: dict[str, float],
    *,
    cap: float | None = DEFAULT_Z_CAP,
) -> list[dict[str, float]]:
    """Per-row robust z-score maps against fitted median/robust-scale baselines."""
    from ml.features.asset import boolean_feature_names, numeric_feature_names

    numeric_names = list(numeric_feature_names()) + list(boolean_feature_names())
    scores: list[dict[str, float]] = []
    for row in rows:
        row_scores: dict[str, float] = {}
        for name in numeric_names:
            value = float(row.get(name) if row.get(name) is not None else 0.0)
            scale = mads.get(name, 1e-3)
            if scale <= 0:
                scale = 1e-3
            score = abs((value - medians.get(name, 0.0)) / scale)
            if cap is not None:
                score = min(score, cap)
            row_scores[name] = score
        scores.append(row_scores)
    return scores


def asset_anomaly_score(
    row: dict[str, object],
    medians: dict[str, float],
    mads: dict[str, float],
    *,
    cap: float | None = DEFAULT_Z_CAP,
) -> float:
    """Aggregate capped robust z-scores into one per-asset anomaly magnitude."""
    scores = robust_z_scores([row], medians, mads, cap=cap)
    return max(scores[0].values()) if scores and scores[0] else 0.0


__all__ = ["asset_anomaly_score", "fit_robust_baseline", "robust_z_scores"]
