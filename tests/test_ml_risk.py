"""Tests for operational risk prioritization (Milestone 3)."""

from __future__ import annotations

from datetime import datetime

from data_engineering.generators.independent_evaluation import (
    IndependentEvaluationParams,
    build_independent_feature_snapshots,
    generate_independent_evaluation,
)
from ml.anomaly import fit_robust_baseline
from ml.risk.prioritization import build_risk_records


EVAL_PARAMS = IndependentEvaluationParams(seed=7, asset_count=16, observation_days=60, horizon_days=30, failure_prevalence=0.25)


def _snapshots(tmp_path):
    directory = tmp_path / "eval"
    manifest = generate_independent_evaluation(directory, params=EVAL_PARAMS)
    cutoff = datetime.fromisoformat(manifest["prediction_cutoff"])
    snapshots = build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)
    medians, mads = fit_robust_baseline(snapshots)
    return snapshots, cutoff, medians, mads


def test_risk_records_schema_without_model(tmp_path) -> None:
    snapshots, cutoff, medians, mads = _snapshots(tmp_path)
    records = build_risk_records(
        snapshots=snapshots,
        model_probabilities=None,
        model_version=None,
        prediction_cutoff=cutoff,
        medians=medians,
        mads=mads,
    )
    assert len(records) == len(snapshots)
    record = records[0]
    assert record.asset_id
    assert record.asset_type
    assert record.prediction_cutoff == cutoff
    assert record.model_probability is None
    assert record.risk_category in {"anomaly", "normal"}
    assert isinstance(record.anomaly_score, float)
    assert isinstance(record.primary_drivers, list)
    assert isinstance(record.data_quality, dict)
    assert record.model_version is None


def test_risk_records_with_model_probability(tmp_path) -> None:
    snapshots, cutoff, medians, mads = _snapshots(tmp_path)
    probabilities = {str(snapshot.get("asset_id")): 0.9 for snapshot in snapshots[:2]}
    records = build_risk_records(
        snapshots=snapshots,
        model_probabilities=probabilities,
        model_version="logistic_regression-v1",
        prediction_cutoff=cutoff,
        medians=medians,
        mads=mads,
    )
    predicted = [record for record in records if record.model_probability is not None]
    assert len(predicted) == 2
    assert all(record.risk_category == "predicted_failure" for record in predicted)
    assert all(record.model_version == "logistic_regression-v1" for record in predicted)
