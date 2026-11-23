"""Integration test: batched feature loading against the real schema.

This test reuses the existing ``ingested_db`` fixture, so it reads the already
generated synthetic CSVs and the dedicated test database.  It does not
regenerate data and does not mutate the development database.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from backend.app.models import Asset
from data_engineering.generators.config import REFERENCE_DATE
from ml.features import (
    all_feature_names,
    build_feature_records_for_assets,
    load_failures,
    load_inspections,
    load_telemetry,
    load_weather,
    load_work_orders,
    normalize_timestamp,
)


def test_build_features_for_assets_from_database(db_session_factory, ingested_db):
    cutoff = normalize_timestamp(REFERENCE_DATE - timedelta(days=30))

    with db_session_factory() as session:
        asset_ids = list(session.scalars(select(Asset.asset_id).order_by(Asset.asset_id).limit(5)))
        records = build_feature_records_for_assets(
            session, asset_ids, cutoff, window_days=365
        )

    assert len(records) == len(asset_ids)
    assert [record["asset_id"] for record in records] == asset_ids
    assert all(set(record) == set(all_feature_names()) for record in records)

    for record in records:
        assert record["feature_cutoff"] == cutoff
        last_observed = record["telemetry_last_observed_at"]
        if last_observed is not None:
            assert last_observed < cutoff
        assert "failure_severity" not in record
        assert "downtime_hours" not in record
        assert "failure_timestamp" not in record
        assert "risk_score" not in record


def test_loaders_apply_strict_cutoff_and_event_bound(db_session_factory, ingested_db):
    cutoff = normalize_timestamp(REFERENCE_DATE - timedelta(days=30))

    with db_session_factory() as session:
        asset_ids = list(session.scalars(select(Asset.asset_id).order_by(Asset.asset_id).limit(5)))

        telemetry = load_telemetry(session, asset_ids, cutoff)
        assert all(reading.timestamp < cutoff for reading in telemetry)

        work_orders = load_work_orders(session, asset_ids, cutoff)
        assert all(order.opened_at < cutoff for order in work_orders)

        inspections = load_inspections(session, asset_ids, cutoff)
        assert all(inspection.inspection_date < cutoff for inspection in inspections)

        weather = load_weather(session, [row[0] for row in session.execute(select(Asset.region).distinct())], cutoff)
        assert all(observation.timestamp < cutoff for observation in weather)

        bounded_orders = load_work_orders(
            session, asset_ids, cutoff, exclude_at_or_after=cutoff - timedelta(days=10)
        )
        assert all(order.opened_at < cutoff - timedelta(days=10) for order in bounded_orders)


def test_build_features_apply_per_asset_event_bounds(db_session_factory, ingested_db):
    cutoff = normalize_timestamp(REFERENCE_DATE - timedelta(days=30))

    with db_session_factory() as session:
        failures = load_failures(session)
        first_failure_by_asset: dict[str, object] = {}
        for failure in failures:
            first_failure_by_asset.setdefault(failure.asset_id, failure.failure_timestamp)
        failed_ids = sorted(first_failure_by_asset)[:2]

        records = build_feature_records_for_assets(
            session,
            failed_ids,
            cutoff,
            window_days=365,
            exclude_at_or_after=first_failure_by_asset,
        )

    assert len(records) == len(failed_ids)
    for record in records:
        event_bound = first_failure_by_asset[record["asset_id"]]
        assert record["feature_excluded_at_or_after"] == event_bound
        last_observed = record["telemetry_last_observed_at"]
        if last_observed is not None:
            assert last_observed < event_bound
