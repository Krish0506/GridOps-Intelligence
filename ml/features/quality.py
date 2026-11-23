"""Data-completeness and missingness indicators.

These features make gaps explicit instead of silently imputing them.  They are
derived from the already-computed group dictionaries, so they introduce no new
database reads and no new source columns.

``quality_telemetry_sparse`` is ``True`` when there are no readings, or when a
lookback window was supplied and telemetry covers less than
``sparse_coverage_threshold`` of its calendar days.  Without a window the flag
only reflects the presence/absence of readings, because coverage has no
denominator.
"""

from __future__ import annotations

from ml.features.telemetry import SENSOR_FIELDS

DEFAULT_SPARSE_COVERAGE_THRESHOLD = 0.5


def quality_features(
    telemetry: dict[str, object],
    maintenance: dict[str, object],
    inspection: dict[str, object],
    weather: dict[str, object],
    sparse_coverage_threshold: float = DEFAULT_SPARSE_COVERAGE_THRESHOLD,
) -> dict[str, object]:
    """Build missingness indicators from the other feature groups."""
    reading_count = int(telemetry.get("telemetry_reading_count") or 0)
    coverage = telemetry.get("telemetry_coverage_ratio")
    coverage_value = None if coverage is None else float(coverage)  # type: ignore[arg-type]

    if reading_count == 0:
        sparse = True
    elif coverage_value is not None:
        sparse = coverage_value < sparse_coverage_threshold
    else:
        sparse = False

    sensor_missing_count = sum(
        1
        for field in SENSOR_FIELDS
        if int(telemetry.get(f"telemetry_{field}_missing") or 0) > 0
    )
    sensors_observed = sum(
        1
        for field in SENSOR_FIELDS
        if int(telemetry.get(f"telemetry_{field}_count") or 0) > 0
    )

    has_maintenance = bool(maintenance.get("maintenance_has_history"))
    has_inspection = bool(inspection.get("inspection_has_history"))
    has_weather = bool(weather.get("weather_has_history"))

    return {
        "quality_telemetry_has_readings": reading_count > 0,
        "quality_telemetry_sparse": sparse,
        "quality_telemetry_coverage_ratio": coverage_value,
        "quality_telemetry_missing_value_ratio": telemetry.get(
            "telemetry_missing_value_ratio"
        ),
        "quality_sensor_missing_count": sensor_missing_count,
        "quality_sensors_observed_count": sensors_observed,
        "quality_all_sensors_observed": sensors_observed == len(SENSOR_FIELDS),
        "quality_missing_maintenance_history": not has_maintenance,
        "quality_missing_inspection_history": not has_inspection,
        "quality_missing_weather_history": not has_weather,
        "quality_history_group_count": int(has_maintenance)
        + int(has_inspection)
        + int(has_weather),
    }


def quality_feature_names() -> list[str]:
    """Ordered feature names produced by :func:`quality_features`."""
    return [
        "quality_telemetry_has_readings",
        "quality_telemetry_sparse",
        "quality_telemetry_coverage_ratio",
        "quality_telemetry_missing_value_ratio",
        "quality_sensor_missing_count",
        "quality_sensors_observed_count",
        "quality_all_sensors_observed",
        "quality_missing_maintenance_history",
        "quality_missing_inspection_history",
        "quality_missing_weather_history",
        "quality_history_group_count",
    ]
