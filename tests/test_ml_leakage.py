"""Targeted leakage regression tests for Milestone 3 (pure Python)."""

from __future__ import annotations

from datetime import datetime

from data_engineering.generators.independent_evaluation import (
    IndependentEvaluationParams,
    build_independent_feature_snapshots,
    generate_independent_evaluation,
)
from ml.data import confirmed_healthy_until_for_snapshots
from ml.data.cohort import build_modeling_dataset
from ml.features.asset import identifier_columns, metadata_columns, model_feature_names
from ml.features.labels import classify_outcomes
from ml.features.types import failure_from_mapping
from ml.pipelines.train import stratified_split
from data_engineering.generators.base import load_rows


EVAL_PARAMS = IndependentEvaluationParams(seed=7, asset_count=16, observation_days=60, horizon_days=30, failure_prevalence=0.25)
SPLIT_PARAMS = IndependentEvaluationParams(seed=7, asset_count=40, observation_days=60, horizon_days=30, failure_prevalence=0.25)


def _prepared(tmp_path, params=EVAL_PARAMS):
    directory = tmp_path / "eval"
    manifest = generate_independent_evaluation(directory, params=params)
    cutoff = datetime.fromisoformat(manifest["prediction_cutoff"])
    horizon_end = datetime.fromisoformat(manifest["horizon_end"])
    snapshots = build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)
    failures = []
    for row in load_rows(directory / "failures.csv"):
        mapped = dict(row)
        mapped["asset_id"] = mapped.get("asset_ref") or ""
        failures.append(failure_from_mapping(mapped))
    failed_ids = {failure.asset_id for failure in failures}
    confirmed = confirmed_healthy_until_for_snapshots(snapshots, cutoff, params.observation_days, horizon_end, failed_ids)
    decisions = classify_outcomes(failures, [str(s.get("asset_id")) for s in snapshots], cutoff, horizon_end, confirmed_healthy_until=confirmed)
    dataset = build_modeling_dataset(snapshots, decisions)
    return dataset


def test_model_predictors_exclude_leakage_columns(tmp_path) -> None:
    dataset = _prepared(tmp_path)
    forbidden = set(identifier_columns()) | set(metadata_columns())
    for row in dataset.features:
        assert not (set(row) & forbidden)
        assert set(row).issubset(set(model_feature_names()))


def test_three_way_split_is_disjoint_and_complete(tmp_path) -> None:
    dataset = _prepared(tmp_path, SPLIT_PARAMS)
    train_idx, val_idx, test_idx = stratified_split(dataset.asset_ids, dataset.labels, seed=42)
    train_set = set(train_idx)
    val_set = set(val_idx)
    test_set = set(test_idx)
    assert train_set.isdisjoint(val_set)
    assert train_set.isdisjoint(test_set)
    assert val_set.isdisjoint(test_set)
    assert train_set | val_set | test_set == set(range(len(dataset.asset_ids)))


def test_three_way_split_preserves_class_representation(tmp_path) -> None:
    dataset = _prepared(tmp_path, SPLIT_PARAMS)
    train_idx, val_idx, test_idx = stratified_split(dataset.asset_ids, dataset.labels, seed=42)
    for name, partition in (("train", train_idx), ("val", val_idx), ("test", test_idx)):
        labels = {dataset.labels[i] for i in partition}
        assert labels == {0, 1}, f"{name} partition missing a class"
