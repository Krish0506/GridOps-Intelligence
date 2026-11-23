"""Tests for the Milestone 3 data-readiness assessment."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from ml.data import MINIMUM_CONFIRMED_NEGATIVES, MINIMUM_CONFIRMED_POSITIVES, assess_readiness


def test_readiness_passes_with_sufficient_samples() -> None:
    report = assess_readiness(
        dataset_name="test",
        generator="gen",
        seed=1,
        asset_count=200,
        snapshot_count=200,
        prediction_cutoff=datetime(2025, 11, 21, 12, 0),
        horizon_end=datetime(2026, 2, 19, 12, 0),
        confirmed_positive=100,
        confirmed_negative=100,
        unknown=50,
        missingness={},
        feature_count=150,
        excluded_columns=["asset_id"],
    )
    assert report.ready is True
    assert report.reasons == []
    assert report.confirmed_positive_count == 100
    assert report.confirmed_negative_count == 100
    assert report.split_feasible is True


def test_readiness_blocked_with_insufficient_positives() -> None:
    report = assess_readiness(
        dataset_name="test",
        generator="gen",
        seed=1,
        asset_count=100,
        snapshot_count=100,
        prediction_cutoff=datetime(2025, 11, 21, 12, 0),
        horizon_end=datetime(2026, 2, 19, 12, 0),
        confirmed_positive=5,
        confirmed_negative=100,
        unknown=10,
        min_confirmed_positives=100,
        min_confirmed_negatives=100,
    )
    assert report.ready is False
    assert any("insufficient confirmed positives" in reason for reason in report.reasons)


def test_readiness_blocked_with_insufficient_negatives() -> None:
    report = assess_readiness(
        dataset_name="test",
        generator="gen",
        seed=1,
        asset_count=100,
        snapshot_count=100,
        prediction_cutoff=datetime(2025, 11, 21, 12, 0),
        horizon_end=datetime(2026, 2, 19, 12, 0),
        confirmed_positive=100,
        confirmed_negative=5,
        unknown=10,
        min_confirmed_positives=100,
        min_confirmed_negatives=100,
    )
    assert report.ready is False
    assert any("insufficient confirmed negatives" in reason for reason in report.reasons)


def test_readiness_blocked_without_snapshots() -> None:
    report = assess_readiness(
        dataset_name="test",
        generator="gen",
        seed=1,
        asset_count=100,
        snapshot_count=0,
        prediction_cutoff=datetime(2025, 11, 21, 12, 0),
        horizon_end=datetime(2026, 2, 19, 12, 0),
        confirmed_positive=100,
        confirmed_negative=100,
        unknown=0,
    )
    assert report.ready is False
    assert any("no feature snapshots" in reason for reason in report.reasons)


def test_readiness_defaults_are_conservative() -> None:
    assert MINIMUM_CONFIRMED_POSITIVES >= 100
    assert MINIMUM_CONFIRMED_NEGATIVES >= 100
    assert MINIMUM_CONFIRMED_POSITIVES == MINIMUM_CONFIRMED_NEGATIVES == 100
