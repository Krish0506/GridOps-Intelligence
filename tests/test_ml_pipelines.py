"""Tests for the training pipeline and preprocessing isolation (Milestone 3)."""

from __future__ import annotations

from datetime import datetime, timedelta

from data_engineering.generators.independent_evaluation import (
    IndependentEvaluationParams,
    build_independent_feature_snapshots,
    generate_independent_evaluation,
)
from ml.data import confirmed_healthy_until_for_snapshots
from ml.data.cohort import build_modeling_dataset
from ml.features.labels import classify_outcomes
from ml.features.types import failure_from_mapping
from ml.pipelines.train import train_baseline, predict_positive_probability


EVAL_PARAMS = IndependentEvaluationParams(seed=7, asset_count=16, observation_days=60, horizon_days=30, failure_prevalence=0.25)


def _prepared(tmp_path):
    directory = tmp_path / "eval"
    manifest = generate_independent_evaluation(directory, params=EVAL_PARAMS)
    cutoff = datetime.fromisoformat(manifest["prediction_cutoff"])
    horizon_end = datetime.fromisoformat(manifest["horizon_end"])
    snapshots = build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)
    failures = []
    for row in __import__("data_engineering.generators.base", fromlist=["load_rows"]).load_rows(directory / "failures.csv"):
        mapped = dict(row)
        mapped["asset_id"] = mapped.get("asset_ref") or ""
        failures.append(failure_from_mapping(mapped))
    failed_ids = {failure.asset_id for failure in failures}
    confirmed = confirmed_healthy_until_for_snapshots(snapshots, cutoff, EVAL_PARAMS.observation_days, horizon_end, failed_ids)
    decisions = classify_outcomes(failures, [str(s.get("asset_id")) for s in snapshots], cutoff, horizon_end, confirmed_healthy_until=confirmed)
    dataset = build_modeling_dataset(snapshots, decisions)
    trained = train_baseline(dataset, "logistic_regression", seed=42)
    return trained, snapshots


def test_training_produces_metrics(tmp_path) -> None:
    trained, snapshots = _prepared(tmp_path)
    assert trained.metrics["accuracy"] >= 0.0
    assert "roc_auc" in trained.metrics
    assert trained.positive_count > 0
    assert trained.negative_count > 0
    assert trained.train_asset_ids and trained.validation_asset_ids
    assert set(trained.train_asset_ids).isdisjoint(trained.validation_asset_ids)


def test_prediction_returns_probability(tmp_path) -> None:
    trained, snapshots = _prepared(tmp_path)
    probability = predict_positive_probability(trained, snapshots[0])
    assert isinstance(probability, float)
    assert 0.0 <= probability <= 1.0


def test_training_is_reproducible(tmp_path) -> None:
    trained_one, _ = _prepared(tmp_path / "one")
    trained_two, _ = _prepared(tmp_path / "two")
    for key in trained_one.metrics:
        value_one = trained_one.metrics[key]
        value_two = trained_two.metrics[key]
        if isinstance(value_one, float) and value_one != value_one:  # NaN
            assert value_two != value_two
        else:
            assert value_one == value_two
