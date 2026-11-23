"""Tests for anomaly detection (Milestone 3)."""

from __future__ import annotations

from datetime import datetime

from data_engineering.generators.independent_evaluation import (
    IndependentEvaluationParams,
    build_independent_feature_snapshots,
    generate_independent_evaluation,
)
from ml.anomaly import asset_anomaly_score, fit_robust_baseline, robust_z_scores


EVAL_PARAMS = IndependentEvaluationParams(seed=7, asset_count=16, observation_days=60, horizon_days=30, failure_prevalence=0.25)


def _snapshots(tmp_path):
    directory = tmp_path / "eval"
    manifest = generate_independent_evaluation(directory, params=EVAL_PARAMS)
    cutoff = datetime.fromisoformat(manifest["prediction_cutoff"])
    return build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)


def test_robust_baseline_fits_and_scores(tmp_path) -> None:
    snapshots = _snapshots(tmp_path)
    medians, mads = fit_robust_baseline(snapshots)
    scores = robust_z_scores(snapshots, medians, mads)
    assert len(scores) == len(snapshots)
    assert all(isinstance(score, dict) for score in scores)
    assert all(score for score in scores)


def test_anomaly_score_is_non_negative(tmp_path) -> None:
    snapshots = _snapshots(tmp_path)
    medians, mads = fit_robust_baseline(snapshots)
    for snapshot in snapshots:
        score = asset_anomaly_score(snapshot, medians, mads)
        assert score >= 0.0


def test_anomaly_detection_is_reproducible(tmp_path) -> None:
    snapshots_one = _snapshots(tmp_path / "one")
    snapshots_two = _snapshots(tmp_path / "two")
    medians_one, mads_one = fit_robust_baseline(snapshots_one)
    medians_two, mads_two = fit_robust_baseline(snapshots_two)
    score_one = asset_anomaly_score(snapshots_one[0], medians_one, mads_one)
    score_two = asset_anomaly_score(snapshots_two[0], medians_two, mads_two)
    assert score_one == score_two
