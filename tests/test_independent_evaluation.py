"""Tests for the independent synthetic evaluation-data generator (Milestone 2B)."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta

import pytest

from data_engineering.generators.base import load_rows, parse_ts
from data_engineering.generators.config import (
    ASSET_ID_FIELDS,
    ASSET_TABLES,
    TABLE_FIELDNAMES,
    TABLES,
)
from data_engineering.generators.independent_evaluation import (
    IndependentEvaluationParams,
    build_independent_feature_snapshots,
    generate_independent_evaluation,
)
from data_engineering.generators.validation import validate_all
from ml.features.labels import (
    InsufficientConfirmedNegativesError,
    build_training_cohort,
    classify_outcomes,
    trainable_outcomes,
)
from ml.features.types import failure_from_mapping

EVAL_PARAMS = IndependentEvaluationParams(seed=7, asset_count=16, observation_days=60, horizon_days=30, failure_prevalence=0.25)


@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> dict:
    """Generate the independent evaluation dataset once per test module."""
    directory = tmp_path_factory.mktemp("independent-eval")
    manifest = generate_independent_evaluation(directory, params=EVAL_PARAMS)
    return {"directory": directory, "manifest": manifest}


def _failure_records(directory) -> list:
    records = []
    for row in load_rows(directory / "failures.csv"):
        mapped = dict(row)
        mapped["asset_id"] = mapped.get("asset_ref") or ""
        records.append(failure_from_mapping(mapped))
    return records


def _asset_ids(directory) -> list[str]:
    asset_ids: list[str] = []
    for table in ASSET_TABLES:
        id_field = ASSET_ID_FIELDS[table]
        for row in load_rows(directory / f"{table}.csv"):
            asset_ids.append(str(row[id_field]))
    return asset_ids


def _prediction_window() -> tuple[datetime, datetime]:
    cutoff = datetime(2026, 11, 21, 12, 0, 0) - timedelta(days=EVAL_PARAMS.observation_days)
    horizon_end = cutoff + timedelta(days=EVAL_PARAMS.horizon_days)
    return cutoff, horizon_end


def test_expected_files_created(generated) -> None:
    directory = generated["directory"]
    for table in TABLES:
        assert (directory / f"{table}.csv").is_file(), f"missing {table}.csv"
    assert (directory / "synthetic_manifest.json").is_file()


def test_csv_headers_match_schema(generated) -> None:
    directory = generated["directory"]
    for table in TABLES:
        with open(directory / f"{table}.csv", newline="") as handle:
            assert next(csv.reader(handle)) == TABLE_FIELDNAMES[table]


def test_every_record_marked_synthetic(generated) -> None:
    directory = generated["directory"]
    for table in TABLES:
        for row in load_rows(directory / f"{table}.csv"):
            assert str(row.get("synthetic", "")).strip() == "true", f"{table} row is not marked synthetic"


def test_validation_passes(generated) -> None:
    results = validate_all(generated["directory"])
    for table, result in results.items():
        assert result.ok, f"{table}: {[issue.describe() for issue in result.errors[:10]]}"
        assert result.completeness >= 0.95
        assert result.row_count > 0


def test_generation_is_deterministic(tmp_path) -> None:
    generate_independent_evaluation(tmp_path / "run1", params=EVAL_PARAMS)
    generate_independent_evaluation(tmp_path / "run2", params=EVAL_PARAMS)
    for table in TABLES:
        assert (tmp_path / "run1" / f"{table}.csv").read_bytes() == (tmp_path / "run2" / f"{table}.csv").read_bytes()
    assert (tmp_path / "run1" / "synthetic_manifest.json").read_bytes() == (
        tmp_path / "run2" / "synthetic_manifest.json"
    ).read_bytes()


def test_failures_are_in_future_horizon_and_telemetry_has_no_post_failure_rows(generated) -> None:
    directory = generated["directory"]
    cutoff, horizon_end = _prediction_window()
    failures = _failure_records(directory)
    asset_index = set(_asset_ids(directory))
    telemetry_by_asset: dict[str, list[datetime]] = {}

    for row in load_rows(directory / "asset_telemetry.csv"):
        asset_id = str(row.get("asset_id") or "")
        timestamp = parse_ts(str(row.get("timestamp") or ""))
        assert timestamp is not None, "telemetry row requires a timestamp"
        assert timestamp < cutoff, "historical telemetry must precede the prediction cutoff"
        telemetry_by_asset.setdefault(asset_id, []).append(timestamp)

    assert failures
    for failure in failures:
        assert failure.asset_id in asset_index
        assert cutoff < failure.failure_timestamp <= horizon_end
        for timestamp in telemetry_by_asset.get(failure.asset_id, []):
            assert timestamp < failure.failure_timestamp, "telemetry must not follow the failure event"

    for asset_id in asset_index:
        for timestamp in telemetry_by_asset.get(asset_id, []):
            assert timestamp < cutoff


def test_labels_are_three_state_and_training_cohort_requires_confirmed_negative(generated) -> None:
    directory = generated["directory"]
    cutoff, horizon_end = _prediction_window()
    failures = _failure_records(directory)

    decisions = classify_outcomes(failures, _asset_ids(directory), cutoff, horizon_end)
    positives = [d for d in decisions if d.label.value == "confirmed_positive"]
    unknowns = [d for d in decisions if d.label.value == "unknown"]
    assert len(positives) == len(failures)
    assert unknowns, "failure-free assets without health confirmation must stay UNKNOWN"

    with pytest.raises(InsufficientConfirmedNegativesError):
        build_training_cohort(decisions)

    trainable = trainable_outcomes(decisions)
    assert all(decision.label.value != "unknown" for decision in trainable)
    assert len(trainable) == len(failures)

    confirmed_healthy_until: dict[str, datetime] = {}
    for table in ASSET_TABLES:
        id_field = ASSET_ID_FIELDS[table]
        for row in load_rows(directory / f"{table}.csv"):
            aid = str(row[id_field])
            install = parse_ts(str(row.get("install_date") or ""))
            if install is None:
                continue
            if install + timedelta(days=EVAL_PARAMS.observation_days) <= cutoff:
                confirmed_healthy_until[aid] = horizon_end

    decisions_with_confirmations = classify_outcomes(
        failures,
        _asset_ids(directory),
        cutoff,
        horizon_end,
        confirmed_healthy_until=confirmed_healthy_until,
    )
    cohort = build_training_cohort(decisions_with_confirmations)
    assert cohort.is_binary_ready
    assert cohort.positive_count == len(failures)
    assert cohort.negative_count > 0
    assert cohort.excluded_unknown_count > 0


def test_feature_snapshots_exclude_post_failure_events(generated) -> None:
    directory = generated["directory"]
    cutoff, _ = _prediction_window()
    failures = _failure_records(directory)
    snapshots = build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)

    assert len(snapshots) == len(_asset_ids(directory))
    failed_by_asset = {failure.asset_id: failure for failure in failures}
    for snapshot in snapshots:
        asset_id = str(snapshot["asset_id"])
        failure = failed_by_asset.get(asset_id)
        if failure is None:
            assert snapshot["feature_excluded_at_or_after"] is None
            continue
        assert snapshot["feature_excluded_at_or_after"] == failure.failure_timestamp
        last_observed = snapshot["telemetry_last_observed_at"]
        assert last_observed is None or last_observed < failure.failure_timestamp
