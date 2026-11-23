"""Tests for the leakage-safe feature-engineering package (Milestone 2A).

The tests exercise pure feature functions only.  They do not require a database
and never regenerate synthetic data.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from ml.features import (
    AssetRecord,
    InspectionRecord,
    TelemetryReading,
    WeatherRecord,
    WorkOrderRecord,
    all_feature_names,
    boolean_feature_names,
    build_asset_feature_record,
    build_asset_feature_records,
    categorical_feature_names,
    identifier_columns,
    inspection_feature_names,
    inspection_features,
    is_strictly_before,
    maintenance_feature_names,
    maintenance_features,
    metadata_columns,
    model_feature_names,
    numeric_feature_names,
    quality_feature_names,
    quality_features,
    static_asset_features,
    static_feature_names,
    telemetry_feature_names,
    telemetry_features,
    weather_feature_names,
    weather_features,
)

CUTOFF = datetime(2024, 6, 1, 12, 0, 0)
ASSET_ID = "T-00001"


def make_asset(**overrides: object) -> AssetRecord:
    values: dict[str, object] = {
        "asset_id": ASSET_ID,
        "asset_type": "transformers",
        "name": "Transformer T-0001",
        "install_date": date(2020, 1, 1),
        "status": "active",
        "region": "NE",
        "operating_hours_cumulative": 12345,
    }
    values.update(overrides)
    return AssetRecord(**values)  # type: ignore[arg-type]


def make_reading(
    timestamp: datetime,
    *,
    asset_id: str = ASSET_ID,
    **overrides: object,
) -> TelemetryReading:
    values: dict[str, object] = {
        "temperature_c": 20.0,
        "load_pct": 50.0,
        "voltage_kv": 115.0,
        "current_a": 100.0,
        "vibration_mm_s": 1.0,
        "operating_hours_cumulative": 1000,
    }
    values.update(overrides)
    return TelemetryReading(asset_id=asset_id, timestamp=timestamp, **values)  # type: ignore[arg-type]


def make_order(
    opened_at: datetime,
    *,
    asset_id: str = ASSET_ID,
    work_order_id: str = "WO-00001",
    work_type: str = "preventive",
    priority: str = "medium",
    status: str = "completed",
    completed_at: datetime | None = None,
) -> WorkOrderRecord:
    return WorkOrderRecord(
        work_order_id=work_order_id,
        asset_id=asset_id,
        work_type=work_type,
        priority=priority,
        status=status,
        opened_at=opened_at,
        completed_at=completed_at,
    )


def make_inspection(
    inspection_date: datetime,
    *,
    inspection_id: str = "INSP-00001",
    asset_id: str = ASSET_ID,
    condition: str = "good",
    severity: str = "low",
) -> InspectionRecord:
    return InspectionRecord(
        inspection_id=inspection_id,
        asset_id=asset_id,
        inspection_date=inspection_date,
        condition=condition,
        severity=severity,
        findings=None,
    )


def make_weather(
    timestamp: datetime,
    *,
    region: str = "NE",
    temperature_c: float = 15.0,
    wind_speed_ms: float = 5.0,
    precipitation_mm: float = 1.0,
    severe: bool = False,
    weather_id: str = "WX-00001",
) -> WeatherRecord:
    return WeatherRecord(
        weather_id=weather_id,
        region=region,
        timestamp=timestamp,
        temperature_c=temperature_c,
        wind_speed_ms=wind_speed_ms,
        precipitation_mm=precipitation_mm,
        severe=severe,
    )


# ---------------------------------------------------------------------------
# Static asset features
# ---------------------------------------------------------------------------


def test_static_features_use_supported_columns() -> None:
    features = static_asset_features(make_asset(), CUTOFF)

    assert features["asset_id"] == ASSET_ID
    assert features["asset_type"] == "transformers"
    assert features["asset_status"] == "active"
    assert features["asset_region"] == "NE"
    assert features["asset_installed_before_cutoff"] is True
    assert features["asset_age_days"] == (CUTOFF.date() - date(2020, 1, 1)).days


def test_static_features_do_not_invent_age_for_future_install() -> None:
    features = static_asset_features(make_asset(install_date=date(2025, 1, 1)), CUTOFF)

    assert features["asset_installed_before_cutoff"] is False
    assert features["asset_age_days"] is None


def test_static_features_handle_missing_install_date() -> None:
    features = static_asset_features(make_asset(install_date=None), CUTOFF)

    assert features["asset_installed_before_cutoff"] is False
    assert features["asset_age_days"] is None


# ---------------------------------------------------------------------------
# Telemetry aggregation
# ---------------------------------------------------------------------------


def test_telemetry_normal_aggregation() -> None:
    readings = [
        make_reading(CUTOFF - timedelta(days=3), temperature_c=10.0),
        make_reading(CUTOFF - timedelta(days=2), temperature_c=20.0),
        make_reading(CUTOFF - timedelta(days=1), temperature_c=30.0),
    ]

    features = telemetry_features(readings, CUTOFF, asset_id=ASSET_ID)

    assert features["telemetry_reading_count"] == 3
    assert features["telemetry_distinct_timestamp_count"] == 3
    assert features["telemetry_duplicate_timestamp_count"] == 0
    assert features["telemetry_has_readings"] is True
    assert features["telemetry_temperature_c_count"] == 3
    assert features["telemetry_temperature_c_mean"] == 20.0
    assert features["telemetry_temperature_c_median"] == 20.0
    assert features["telemetry_temperature_c_min"] == 10.0
    assert features["telemetry_temperature_c_max"] == 30.0
    assert features["telemetry_temperature_c_std"] == pytest.approx(8.164966)
    assert features["telemetry_temperature_c_change"] == 20.0
    assert features["telemetry_temperature_c_trend_per_day"] == pytest.approx(10.0)
    assert features["telemetry_days_since_last_reading"] == pytest.approx(1.0)


def test_telemetry_empty_history() -> None:
    features = telemetry_features([], CUTOFF, asset_id=ASSET_ID)

    assert features["telemetry_reading_count"] == 0
    assert features["telemetry_has_readings"] is False
    assert features["telemetry_missing_value_ratio"] is None
    assert features["telemetry_temperature_c_count"] == 0
    assert features["telemetry_temperature_c_mean"] is None
    assert features["telemetry_temperature_c_median"] is None
    assert features["telemetry_temperature_c_std"] is None
    assert features["telemetry_temperature_c_trend_per_day"] is None


def test_telemetry_sparse_history() -> None:
    features = telemetry_features(
        [make_reading(CUTOFF - timedelta(days=5), temperature_c=12.0)],
        CUTOFF,
        asset_id=ASSET_ID,
        window_days=10,
    )

    assert features["telemetry_reading_count"] == 1
    assert features["telemetry_temperature_c_std"] == 0.0
    assert features["telemetry_temperature_c_trend_per_day"] is None
    assert features["telemetry_coverage_ratio"] == pytest.approx(0.1)


def test_telemetry_missing_sensor_values() -> None:
    readings = [
        make_reading(CUTOFF - timedelta(days=2), temperature_c=None, load_pct=None),
        make_reading(CUTOFF - timedelta(days=1), temperature_c=20.0, load_pct=60.0),
    ]

    features = telemetry_features(readings, CUTOFF, asset_id=ASSET_ID)

    assert features["telemetry_temperature_c_count"] == 1
    assert features["telemetry_temperature_c_missing"] == 1
    assert features["telemetry_temperature_c_missing_ratio"] == 0.5
    assert features["telemetry_load_pct_count"] == 1
    assert features["telemetry_missing_value_ratio"] == pytest.approx(2 / 10)


def test_telemetry_duplicate_timestamps_are_retained_and_counted() -> None:
    timestamp = CUTOFF - timedelta(days=1)
    readings = [
        make_reading(timestamp, temperature_c=10.0),
        make_reading(timestamp, temperature_c=30.0),
        make_reading(CUTOFF - timedelta(days=2), temperature_c=20.0),
    ]

    features = telemetry_features(readings, CUTOFF, asset_id=ASSET_ID)

    assert features["telemetry_reading_count"] == 3
    assert features["telemetry_distinct_timestamp_count"] == 2
    assert features["telemetry_duplicate_timestamp_count"] == 1
    assert features["telemetry_temperature_c_mean"] == 20.0
    assert features["telemetry_temperature_c_max"] == 30.0


def test_cutoff_boundary_is_excluded() -> None:
    readings = [
        make_reading(CUTOFF - timedelta(seconds=1), temperature_c=10.0),
        make_reading(CUTOFF, temperature_c=99.0),
    ]

    features = telemetry_features(readings, CUTOFF, asset_id=ASSET_ID)

    assert features["telemetry_reading_count"] == 1
    assert features["telemetry_temperature_c_max"] == 10.0


def test_post_cutoff_telemetry_is_excluded() -> None:
    readings = [
        make_reading(CUTOFF - timedelta(hours=1), temperature_c=10.0),
        make_reading(CUTOFF + timedelta(hours=1), temperature_c=99.0),
    ]

    features = telemetry_features(readings, CUTOFF, asset_id=ASSET_ID)

    assert features["telemetry_reading_count"] == 1
    assert features["telemetry_temperature_c_max"] == 10.0


def test_post_failure_telemetry_is_excluded() -> None:
    failure_at = CUTOFF - timedelta(hours=2)
    readings = [
        make_reading(failure_at - timedelta(hours=1), temperature_c=10.0),
        make_reading(failure_at, temperature_c=95.0),
        make_reading(failure_at + timedelta(hours=1), temperature_c=99.0),
    ]

    features = telemetry_features(
        readings, CUTOFF, asset_id=ASSET_ID, exclude_at_or_after=failure_at
    )

    assert features["telemetry_reading_count"] == 1
    assert features["telemetry_temperature_c_max"] == 10.0


def test_lookback_window_excludes_old_telemetry() -> None:
    readings = [
        make_reading(CUTOFF - timedelta(days=40), temperature_c=10.0),
        make_reading(CUTOFF - timedelta(days=5), temperature_c=20.0),
    ]

    features = telemetry_features(readings, CUTOFF, asset_id=ASSET_ID, window_days=30)

    assert features["telemetry_reading_count"] == 1
    assert features["telemetry_temperature_c_mean"] == 20.0


def test_telemetry_is_deterministic() -> None:
    readings = [
        make_reading(CUTOFF - timedelta(days=3), temperature_c=10.0),
        make_reading(CUTOFF - timedelta(days=1), temperature_c=30.0),
    ]

    assert telemetry_features(readings, CUTOFF, asset_id=ASSET_ID) == telemetry_features(
        readings, CUTOFF, asset_id=ASSET_ID
    )


def test_telemetry_feature_names_cover_all_keys() -> None:
    features = telemetry_features(
        [make_reading(CUTOFF - timedelta(days=1))],
        CUTOFF,
        asset_id=ASSET_ID,
    )

    assert set(features) == set(telemetry_feature_names())


def test_telemetry_group_ignores_other_assets() -> None:
    readings = [
        make_reading(CUTOFF - timedelta(days=1), asset_id="T-99999", temperature_c=99.0),
    ]

    features = telemetry_features(readings, CUTOFF, asset_id=ASSET_ID)

    assert features["telemetry_reading_count"] == 0
    assert features["telemetry_has_readings"] is False


# ---------------------------------------------------------------------------
# Maintenance features
# ---------------------------------------------------------------------------


def test_maintenance_normal_history() -> None:
    orders = [
        make_order(
            CUTOFF - timedelta(days=20),
            work_type="corrective",
            priority="high",
            status="completed",
            completed_at=CUTOFF - timedelta(days=15),
            work_order_id="WO-1",
        ),
        make_order(
            CUTOFF - timedelta(days=10),
            work_type="preventive",
            priority="medium",
            status="open",
            work_order_id="WO-2",
        ),
        make_order(
            CUTOFF - timedelta(days=5),
            work_type="scheduled",
            priority="low",
            status="completed",
            completed_at=CUTOFF + timedelta(days=1),  # future completion
            work_order_id="WO-3",
        ),
    ]

    features = maintenance_features(orders, CUTOFF, asset_id=ASSET_ID)

    assert features["maintenance_work_order_count"] == 3
    assert features["maintenance_corrective_count"] == 1
    assert features["maintenance_preventive_count"] == 1
    assert features["maintenance_scheduled_count"] == 1
    assert features["maintenance_completed_before_cutoff_count"] == 1
    assert features["maintenance_completed_before_cutoff_ratio"] == pytest.approx(1 / 3)
    assert features["maintenance_unresolved_at_cutoff_count"] == 2
    assert features["maintenance_corrective_ratio"] == pytest.approx(1 / 3)
    assert features["maintenance_high_priority_count"] == 1
    assert features["maintenance_last_work_type"] == "scheduled"
    assert features["maintenance_last_priority"] == "low"
    assert features["maintenance_days_since_last_opened"] == pytest.approx(5.0)
    assert features["maintenance_completion_duration_count"] == 1
    assert features["maintenance_mean_completion_days"] == pytest.approx(5.0)
    assert features["maintenance_days_since_last_completed"] == pytest.approx(15.0)


def test_maintenance_missing_history() -> None:
    features = maintenance_features([], CUTOFF, asset_id=ASSET_ID)

    assert features["maintenance_work_order_count"] == 0
    assert features["maintenance_has_history"] is False
    assert features["maintenance_corrective_ratio"] is None
    assert features["maintenance_completed_before_cutoff_ratio"] is None
    assert features["maintenance_days_since_last_opened"] is None


def test_maintenance_cutoff_boundary_and_post_cutoff_excluded() -> None:
    orders = [
        make_order(CUTOFF - timedelta(days=1), work_order_id="WO-1"),
        make_order(CUTOFF, work_order_id="WO-2"),
        make_order(CUTOFF + timedelta(days=1), work_order_id="WO-3"),
    ]

    features = maintenance_features(orders, CUTOFF, asset_id=ASSET_ID)

    assert features["maintenance_work_order_count"] == 1
    assert features["maintenance_days_since_last_opened"] == pytest.approx(1.0)


def test_maintenance_future_completion_is_not_completed() -> None:
    orders = [make_order(CUTOFF - timedelta(days=10), status="completed", completed_at=CUTOFF + timedelta(days=10))]

    features = maintenance_features(orders, CUTOFF, asset_id=ASSET_ID)

    assert features["maintenance_completed_before_cutoff_count"] == 0
    assert features["maintenance_completed_before_cutoff_ratio"] == 0.0
    assert features["maintenance_unresolved_at_cutoff_count"] == 1
    assert features["maintenance_completion_duration_count"] == 0
    assert features["maintenance_mean_completion_days"] is None
    assert features["maintenance_days_since_last_completed"] is None


def test_maintenance_completion_exactly_at_cutoff_is_not_completed() -> None:
    orders = [make_order(CUTOFF - timedelta(days=10), status="completed", completed_at=CUTOFF)]

    features = maintenance_features(orders, CUTOFF, asset_id=ASSET_ID)

    assert features["maintenance_completed_before_cutoff_count"] == 0
    assert features["maintenance_unresolved_at_cutoff_count"] == 1
    assert features["maintenance_completion_duration_count"] == 0


def test_maintenance_order_without_completion_is_unresolved() -> None:
    orders = [make_order(CUTOFF - timedelta(days=10), status="open", completed_at=None)]

    features = maintenance_features(orders, CUTOFF, asset_id=ASSET_ID)

    assert features["maintenance_work_order_count"] == 1
    assert features["maintenance_completed_before_cutoff_count"] == 0
    assert features["maintenance_unresolved_at_cutoff_count"] == 1
    assert features["maintenance_has_history"] is True


def test_maintenance_event_bound_excludes_orders_opened_at_or_after() -> None:
    orders = [
        make_order(CUTOFF - timedelta(days=10), status="completed", completed_at=CUTOFF - timedelta(days=5), work_order_id="WO-1"),
        make_order(CUTOFF - timedelta(days=3), status="completed", completed_at=CUTOFF - timedelta(days=2), work_order_id="WO-2"),
    ]

    features = maintenance_features(
        orders, CUTOFF, asset_id=ASSET_ID, exclude_at_or_after=CUTOFF - timedelta(days=8)
    )

    assert features["maintenance_work_order_count"] == 1
    assert features["maintenance_completed_before_cutoff_count"] == 1


def test_maintenance_features_do_not_expose_current_status() -> None:
    features = maintenance_features(
        [make_order(CUTOFF - timedelta(days=1), status="completed", completed_at=CUTOFF - timedelta(days=2))],
        CUTOFF,
        asset_id=ASSET_ID,
    )

    assert "maintenance_last_status" not in features
    assert not any(key.startswith("maintenance_open") for key in features)
    assert not any(key.startswith("maintenance_in_progress") for key in features)
    assert not any(key.startswith("maintenance_cancelled") for key in features)


def test_maintenance_feature_names_cover_all_keys() -> None:
    features = maintenance_features([make_order(CUTOFF - timedelta(days=1))], CUTOFF, asset_id=ASSET_ID)

    assert set(features) == set(maintenance_feature_names())
    assert len(maintenance_feature_names()) == len(set(maintenance_feature_names()))


# ---------------------------------------------------------------------------
# Inspection features
# ---------------------------------------------------------------------------


def test_inspection_normal_history() -> None:
    inspections = [
        make_inspection(
            CUTOFF - timedelta(days=10),
            inspection_id="INSP-1",
            condition="poor",
            severity="high",
        ),
        make_inspection(
            CUTOFF - timedelta(days=2),
            inspection_id="INSP-2",
            condition="excellent",
            severity="none",
        ),
    ]

    features = inspection_features(inspections, CUTOFF, asset_id=ASSET_ID)

    assert features["inspection_count"] == 2
    assert features["inspection_has_history"] is True
    assert features["inspection_poor_count"] == 1
    assert features["inspection_excellent_count"] == 1
    assert features["inspection_severity_high_count"] == 1
    assert features["inspection_latest_condition"] == "excellent"
    assert features["inspection_latest_condition_score"] == 3
    assert features["inspection_latest_severity"] == "none"
    assert features["inspection_latest_severity_score"] == 0
    assert features["inspection_days_since_latest"] == pytest.approx(2.0)
    assert features["inspection_poor_or_fair_ratio"] == 0.5


def test_inspection_missing_history() -> None:
    features = inspection_features([], CUTOFF, asset_id=ASSET_ID)

    assert features["inspection_count"] == 0
    assert features["inspection_has_history"] is False
    assert features["inspection_latest_condition"] is None
    assert features["inspection_days_since_latest"] is None


def test_inspection_cutoff_boundary_and_post_cutoff_excluded() -> None:
    inspections = [
        make_inspection(CUTOFF - timedelta(days=1), inspection_id="INSP-1", condition="good"),
        make_inspection(CUTOFF, inspection_id="INSP-2", condition="poor"),
        make_inspection(CUTOFF + timedelta(days=1), inspection_id="INSP-3", condition="poor"),
    ]

    features = inspection_features(inspections, CUTOFF, asset_id=ASSET_ID)

    assert features["inspection_count"] == 1
    assert features["inspection_latest_condition"] == "good"
    assert features["inspection_poor_count"] == 0


def test_inspection_event_bound_excludes_post_failure_inspections() -> None:
    inspections = [
        make_inspection(CUTOFF - timedelta(days=10), inspection_id="INSP-1", condition="good"),
        make_inspection(CUTOFF - timedelta(days=2), inspection_id="INSP-2", condition="poor"),
    ]

    features = inspection_features(
        inspections,
        CUTOFF,
        asset_id=ASSET_ID,
        exclude_at_or_after=CUTOFF - timedelta(days=8),
    )

    assert features["inspection_count"] == 1
    assert features["inspection_latest_condition"] == "good"


def test_inspection_feature_names_cover_all_keys() -> None:
    features = inspection_features(
        [make_inspection(CUTOFF - timedelta(days=1))],
        CUTOFF,
        asset_id=ASSET_ID,
    )

    assert set(features) == set(inspection_feature_names())


# ---------------------------------------------------------------------------
# Weather features
# ---------------------------------------------------------------------------


def test_weather_normal_history_for_region() -> None:
    observations = [
        make_weather(CUTOFF - timedelta(days=2), temperature_c=10.0, severe=False),
        make_weather(
            CUTOFF - timedelta(days=1),
            temperature_c=20.0,
            wind_speed_ms=30.0,
            precipitation_mm=25.0,
            severe=True,
            weather_id="WX-2",
        ),
        make_weather(
            CUTOFF - timedelta(days=1),
            region="SW",
            temperature_c=40.0,
            weather_id="WX-3",
        ),
    ]

    features = weather_features(observations, "NE", CUTOFF)

    assert features["weather_region"] == "NE"
    assert features["weather_observation_count"] == 2
    assert features["weather_has_history"] is True
    assert features["weather_temperature_mean"] == 15.0
    assert features["weather_temperature_max"] == 20.0
    assert features["weather_wind_speed_max"] == 30.0
    assert features["weather_precipitation_total_mm"] == 26.0
    assert features["weather_severe_count"] == 1
    assert features["weather_severe_ratio"] == 0.5
    assert features["weather_days_since_latest"] == pytest.approx(1.0)


def test_weather_missing_region_and_missing_history() -> None:
    observations = [make_weather(CUTOFF - timedelta(days=1))]

    missing_region = weather_features(observations, None, CUTOFF)
    missing_history = weather_features(observations, "SW", CUTOFF)

    assert missing_region["weather_has_history"] is False
    assert missing_region["weather_observation_count"] == 0
    assert missing_history["weather_has_history"] is False
    assert missing_history["weather_temperature_mean"] is None


def test_weather_cutoff_boundary_and_post_cutoff_excluded() -> None:
    observations = [
        make_weather(CUTOFF - timedelta(days=1), temperature_c=10.0),
        make_weather(CUTOFF, temperature_c=99.0, weather_id="WX-2"),
        make_weather(CUTOFF + timedelta(days=1), temperature_c=99.0, weather_id="WX-3"),
    ]

    features = weather_features(observations, "NE", CUTOFF)

    assert features["weather_observation_count"] == 1
    assert features["weather_temperature_max"] == 10.0


def test_weather_event_bound_excludes_post_failure_observations() -> None:
    observations = [
        make_weather(CUTOFF - timedelta(days=10), temperature_c=10.0, weather_id="WX-1"),
        make_weather(CUTOFF - timedelta(days=2), temperature_c=20.0, weather_id="WX-2"),
    ]

    features = weather_features(
        observations, "NE", CUTOFF, exclude_at_or_after=CUTOFF - timedelta(days=8)
    )

    assert features["weather_observation_count"] == 1
    assert features["weather_temperature_max"] == 10.0


def test_weather_feature_names_cover_all_keys() -> None:
    features = weather_features([make_weather(CUTOFF - timedelta(days=1))], "NE", CUTOFF)

    assert set(features) == set(weather_feature_names())


# ---------------------------------------------------------------------------
# Quality and combined records
# ---------------------------------------------------------------------------


def test_quality_flags_missing_history_and_sparse_telemetry() -> None:
    telemetry_group = telemetry_features(
        [make_reading(CUTOFF - timedelta(days=9), temperature_c=None)],
        CUTOFF,
        asset_id=ASSET_ID,
        window_days=10,
    )
    maintenance_group = maintenance_features([], CUTOFF, asset_id=ASSET_ID)
    inspection_group = inspection_features([], CUTOFF, asset_id=ASSET_ID)
    weather_group = weather_features([], "NE", CUTOFF)

    features = quality_features(
        telemetry_group, maintenance_group, inspection_group, weather_group
    )

    assert features["quality_telemetry_has_readings"] is True
    assert features["quality_telemetry_sparse"] is True
    assert features["quality_missing_maintenance_history"] is True
    assert features["quality_missing_inspection_history"] is True
    assert features["quality_missing_weather_history"] is True
    assert features["quality_history_group_count"] == 0
    assert features["quality_sensor_missing_count"] == 1
    assert features["quality_all_sensors_observed"] is False


def test_quality_feature_names_cover_all_keys() -> None:
    features = quality_features(
        telemetry_features([], CUTOFF, asset_id=ASSET_ID),
        maintenance_features([], CUTOFF, asset_id=ASSET_ID),
        inspection_features([], CUTOFF, asset_id=ASSET_ID),
        weather_features([], "NE", CUTOFF),
    )

    assert set(features) == set(quality_feature_names())


def test_combined_record_contains_every_group_and_is_deterministic() -> None:
    asset = make_asset()
    readings = [
        make_reading(CUTOFF - timedelta(days=2), temperature_c=10.0),
        make_reading(CUTOFF - timedelta(days=1), temperature_c=20.0),
    ]
    orders = [make_order(CUTOFF - timedelta(days=3))]
    inspections = [make_inspection(CUTOFF - timedelta(days=4))]
    weather = [make_weather(CUTOFF - timedelta(days=1))]

    first = build_asset_feature_record(
        asset,
        telemetry_readings=readings,
        work_orders=orders,
        inspections=inspections,
        weather_observations=weather,
        prediction_cutoff=CUTOFF,
        window_days=30,
    )
    second = build_asset_feature_record(
        asset,
        telemetry_readings=readings,
        work_orders=orders,
        inspections=inspections,
        weather_observations=weather,
        prediction_cutoff=CUTOFF,
        window_days=30,
    )

    assert first == second
    assert first["asset_id"] == ASSET_ID
    assert first["telemetry_reading_count"] == 2
    assert first["maintenance_work_order_count"] == 1
    assert first["inspection_count"] == 1
    assert first["weather_observation_count"] == 1
    assert first["quality_history_group_count"] == 3
    assert first["feature_cutoff"] == CUTOFF
    assert first["feature_window_days"] == 30
    assert set(first).issubset(set(all_feature_names()))


def test_combined_record_filters_other_assets() -> None:
    asset = make_asset()
    other_readings = [
        make_reading(CUTOFF - timedelta(days=1), asset_id="T-99999", temperature_c=99.0),
    ]
    other_orders = [make_order(CUTOFF - timedelta(days=1), asset_id="T-99999", work_order_id="WO-X")]

    features = build_asset_feature_record(
        asset,
        telemetry_readings=other_readings,
        work_orders=other_orders,
        prediction_cutoff=CUTOFF,
    )

    assert features["telemetry_reading_count"] == 0
    assert features["maintenance_work_order_count"] == 0


def test_combined_records_are_sorted_and_isolated() -> None:
    assets = [make_asset(asset_id="T-2"), make_asset(asset_id="T-1")]
    readings = [
        make_reading(CUTOFF - timedelta(days=1), asset_id="T-1", temperature_c=10.0),
        make_reading(CUTOFF - timedelta(days=1), asset_id="T-2", temperature_c=30.0),
    ]

    records = build_asset_feature_records(
        assets, telemetry_readings=readings, prediction_cutoff=CUTOFF
    )

    assert [record["asset_id"] for record in records] == ["T-1", "T-2"]
    assert records[0]["telemetry_temperature_c_mean"] == 10.0
    assert records[1]["telemetry_temperature_c_mean"] == 30.0


def test_feature_output_never_contains_failure_severity_or_downtime() -> None:
    features = build_asset_feature_record(
        make_asset(),
        telemetry_readings=[make_reading(CUTOFF - timedelta(days=1))],
        prediction_cutoff=CUTOFF,
    )

    forbidden = [key for key in features if "failure" in key or "downtime" in key]
    assert forbidden == []
    assert not any("risk_score" in key for key in features)


def test_model_feature_contract_excludes_identifiers_metadata_and_bounds() -> None:
    record = build_asset_feature_record(make_asset(), prediction_cutoff=CUTOFF)

    for key in identifier_columns():
        assert key in record
    for key in metadata_columns():
        assert key in record
    for key in (
        "feature_cutoff",
        "feature_window_days",
        "feature_excluded_at_or_after",
        "telemetry_first_observed_at",
        "telemetry_last_observed_at",
        "asset_install_date",
        "asset_name",
        "asset_status",
        "weather_region",
    ):
        assert key in record

    model_features = model_feature_names()
    assert model_features
    assert set(model_features) <= set(all_feature_names())
    assert set(model_features) <= set(record)
    assert not any(key in model_features for key in metadata_columns())
    assert not any(key in model_features for key in identifier_columns())
    assert not any(key in model_features for key in ("feature_cutoff", "feature_window_days", "feature_excluded_at_or_after"))
    assert len(model_features) == len(set(model_features))


def test_model_feature_names_contain_no_identifiers_names_dates_or_bounds() -> None:
    model_features = model_feature_names()
    forbidden_tokens = (
        "asset_id",
        "asset_name",
        "install_date",
        "failure",
        "downtime",
        "risk",
        "excluded_at_or_after",
        "feature_cutoff",
        "feature_window_days",
        "feature_excluded_at_or_after",
        "telemetry_first_observed_at",
        "telemetry_last_observed_at",
        "weather_region",
    )
    for name in model_features:
        assert not any(token in name for token in forbidden_tokens), name


def test_numeric_and_categorical_model_features_are_complete() -> None:
    numeric = numeric_feature_names()
    categorical = categorical_feature_names()
    boolean = boolean_feature_names()

    assert len(numeric) + len(categorical) + len(boolean) >= len(model_feature_names())
    assert set(numeric).isdisjoint(set(categorical))
    assert set(numeric).isdisjoint(set(boolean))
    assert set(categorical).isdisjoint(set(boolean))
    assert set(numeric) | set(categorical) | set(boolean) == set(model_feature_names())
    for name in categorical:
        assert name in all_feature_names()
    for name in boolean:
        assert name in all_feature_names()
    for name in numeric:
        assert name in all_feature_names()


def test_metadata_columns_remain_available_in_record() -> None:
    record = build_asset_feature_record(make_asset(), prediction_cutoff=CUTOFF)

    for key in metadata_columns():
        assert key in record


def test_all_feature_names_are_unique() -> None:
    names = all_feature_names()
    assert len(names) == len(set(names))


def test_cutoff_helper_is_strict() -> None:
    assert is_strictly_before(CUTOFF - timedelta(seconds=1), CUTOFF) is True
    assert is_strictly_before(CUTOFF, CUTOFF) is False
    assert is_strictly_before(CUTOFF + timedelta(seconds=1), CUTOFF) is False


def test_mapping_helpers_accept_csv_strings() -> None:
    from ml.features.types import (
        telemetry_from_mapping,
        weather_from_mapping,
        work_order_from_mapping,
    )

    reading = telemetry_from_mapping(
        {
            "asset_id": "T-1",
            "timestamp": "2024-06-01T00:00:00",
            "temperature_c": "",
            "load_pct": "50.5",
            "voltage_kv": "115.0",
            "current_a": "",
            "vibration_mm_s": "1.25",
            "operating_hours_cumulative": "900",
        }
    )
    order = work_order_from_mapping(
        {
            "work_order_id": "WO-1",
            "asset_id": "T-1",
            "work_type": "preventive",
            "priority": "medium",
            "status": "open",
            "opened_at": "2024-05-01T08:00:00",
            "completed_at": "",
        }
    )
    weather = weather_from_mapping(
        {
            "weather_id": "WX-1",
            "region": "NE",
            "timestamp": "2024-05-01T08:00:00",
            "temperature_c": "12.5",
            "wind_speed_ms": "4.0",
            "precipitation_mm": "0.0",
            "severe": "false",
        }
    )

    assert reading.temperature_c is None
    assert reading.load_pct == 50.5
    assert reading.operating_hours_cumulative == 900
    assert order.completed_at is None
    assert weather.severe is False


def test_batched_builder_calls_each_loader_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature building must not degrade into per-asset (N+1) queries."""
    import ml.features.repository as repository

    calls: list[str] = []
    assets = [make_asset(asset_id="T-1"), make_asset(asset_id="T-2")]

    def fake_load_assets(session: object, asset_ids: object = None) -> list[AssetRecord]:
        calls.append("assets")
        return assets

    def fake_load_telemetry(session: object, asset_ids: object, cutoff: object, **kwargs: object) -> list[TelemetryReading]:
        calls.append("telemetry")
        return [
            make_reading(CUTOFF - timedelta(days=1), asset_id="T-1", temperature_c=10.0),
            make_reading(CUTOFF - timedelta(days=1), asset_id="T-2", temperature_c=30.0),
        ]

    def fake_load_work_orders(session: object, asset_ids: object, cutoff: object, **kwargs: object) -> list[WorkOrderRecord]:
        calls.append("work_orders")
        return []

    def fake_load_inspections(session: object, asset_ids: object, cutoff: object, **kwargs: object) -> list[InspectionRecord]:
        calls.append("inspections")
        return []

    def fake_load_weather(session: object, regions: object, cutoff: object, **kwargs: object) -> list[WeatherRecord]:
        calls.append("weather")
        return []

    monkeypatch.setattr(repository, "load_assets", fake_load_assets)
    monkeypatch.setattr(repository, "load_telemetry", fake_load_telemetry)
    monkeypatch.setattr(repository, "load_work_orders", fake_load_work_orders)
    monkeypatch.setattr(repository, "load_inspections", fake_load_inspections)
    monkeypatch.setattr(repository, "load_weather", fake_load_weather)

    records = repository.build_feature_records_for_assets(
        object(), ["T-1", "T-2"], CUTOFF  # type: ignore[arg-type]
    )

    assert calls == ["assets", "telemetry", "work_orders", "inspections", "weather"]
    assert [record["asset_id"] for record in records] == ["T-1", "T-2"]
    assert records[0]["telemetry_temperature_c_mean"] == 10.0
    assert records[1]["telemetry_temperature_c_mean"] == 30.0

