"""Tests for the leakage-safe modeling cohort (Milestone 3)."""

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
from ml.features.asset import model_feature_names, identifier_columns, metadata_columns


EVAL_PARAMS = IndependentEvaluationParams(seed=7, asset_count=16, observation_days=60, horizon_days=30, failure_prevalence=0.25)


def _dataset(tmp_path):
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
    return dataset, snapshots, decisions


def test_modeling_dataset_excludes_unknowns(tmp_path) -> None:
    dataset, snapshots, decisions = _dataset(tmp_path)
    assert dataset.positive_count + dataset.negative_count == len(dataset.features)
    assert dataset.excluded_unknown_count > 0
    assert dataset.is_binary_ready


def test_modeling_dataset_uses_only_model_feature_columns(tmp_path) -> None:
    dataset, snapshots, decisions = _dataset(tmp_path)
    allowed = set(model_feature_names())
    forbidden = set(identifier_columns()) | set(metadata_columns())
    for row in dataset.features:
        assert set(row).issubset(allowed)
        assert not (set(row) & forbidden)


def test_modeling_dataset_preserves_asset_ids(tmp_path) -> None:
    dataset, snapshots, decisions = _dataset(tmp_path)
    assert len(dataset.asset_ids) == len(dataset.features) == len(dataset.labels)
    assert all(isinstance(label, int) for label in dataset.labels)
    assert set(dataset.labels).issubset({0, 1})
