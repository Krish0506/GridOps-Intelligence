"""Telemetry aggregation features.

Source: ``asset_telemetry``.  Only readings with
``timestamp < prediction_cutoff`` are eligible.  The synthetic generator
appends elevated readings within a few days of each failure; callers that know
a failure time must pass ``exclude_at_or_after`` (or choose a cutoff before the
failure) so nothing at or after the event can enter the feature vector.

Sensor columns (``temperature_c``, ``load_pct``, ``voltage_kv``, ``current_a``,
``vibration_mm_s``) are nullable by design.  Missing values are excluded from
each statistic and reported through explicit missing counters and ratios.

Duplicate timestamps are retained.  The schema deliberately stores distinct
readings that share an asset/timestamp (a normal and an elevated reading at the
same minute), so deduplicating would silently drop signal.  The duplicate count
is surfaced as a feature instead.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from ml.features.cutoff import (
    days_between,
    filter_window,
    normalize_timestamp,
    sorted_by_time,
)
from ml.features.types import TelemetryReading

SENSOR_FIELDS: tuple[str, ...] = (
    "temperature_c",
    "load_pct",
    "voltage_kv",
    "current_a",
    "vibration_mm_s",
)


@dataclass(frozen=True, slots=True)
class SensorStatistics:
    """Descriptive statistics for one sensor series."""

    count: int
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    std: float | None
    first: float | None
    last: float | None
    change: float | None
    trend_per_day: float | None


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def summarize_sensor(points: Sequence[tuple[datetime, float]]) -> SensorStatistics:
    """Summarise ``(timestamp, value)`` points deterministically.

    ``std`` is the population standard deviation.  ``trend_per_day`` is the
    ordinary-least-squares slope of value against days since the first point and
    is ``None`` when fewer than two points or no time spread exists.
    """
    if not points:
        return SensorStatistics(0, None, None, None, None, None, None, None, None, None)

    ordered = sorted(points, key=lambda item: normalize_timestamp(item[0]))
    values = [value for _, value in ordered]
    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    first = values[0]
    last = values[-1]

    trend: float | None = None
    if len(ordered) >= 2:
        origin = normalize_timestamp(ordered[0][0])
        xs = [days_between(origin, ts) for ts, _ in ordered]
        x_mean = statistics.fmean(xs)
        y_mean = mean
        variance = sum((x - x_mean) ** 2 for x in xs)
        if variance > 0:
            covariance = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
            trend = covariance / variance

    return SensorStatistics(
        count=len(values),
        mean=_round(mean),
        median=_round(statistics.median(values)),
        minimum=_round(min(values)),
        maximum=_round(max(values)),
        std=_round(std),
        first=_round(first),
        last=_round(last),
        change=_round(last - first),
        trend_per_day=_round(trend),
    )


def _sensor_points(
    readings: Sequence[TelemetryReading], field: str
) -> list[tuple[datetime, float]]:
    points: list[tuple[datetime, float]] = []
    for reading in readings:
        value = getattr(reading, field)
        if value is not None:
            points.append((reading.timestamp, float(value)))
    return points


def telemetry_features(
    readings: Iterable[TelemetryReading],
    prediction_cutoff: datetime,
    *,
    asset_id: str,
    window_days: int | float | None = None,
    exclude_at_or_after: datetime | None = None,
) -> dict[str, object]:
    """Aggregate telemetry strictly before ``prediction_cutoff``.

    Parameters
    ----------
    readings:
        Telemetry rows for a single asset; rows for other assets must be
        filtered out by the caller before aggregation.
    prediction_cutoff:
        Exclusive upper bound.  A reading exactly at the cutoff is excluded.
    asset_id:
        Asset identifier the rows are scoped to; rows for other assets are
        ignored.
    window_days:
        Optional lookback window, e.g. ``30`` for the last 30 days.
    exclude_at_or_after:
        Optional event bound such as the first known failure timestamp.  The
        earlier of this bound and ``prediction_cutoff`` is applied.
    """
    cutoff = normalize_timestamp(prediction_cutoff)
    scoped_readings = [reading for reading in readings if reading.asset_id == asset_id]
    eligible = filter_window(
        scoped_readings,
        cutoff,
        key=lambda reading: reading.timestamp,
        window_days=window_days,
        exclude_at_or_after=exclude_at_or_after,
    )
    ordered = sorted_by_time(eligible, key=lambda reading: reading.timestamp)

    reading_count = len(ordered)
    timestamps = {normalize_timestamp(reading.timestamp) for reading in ordered}
    first_at = ordered[0].timestamp if ordered else None
    last_at = ordered[-1].timestamp if ordered else None

    record: dict[str, object] = {
        "telemetry_reading_count": reading_count,
        "telemetry_distinct_timestamp_count": len(timestamps),
        "telemetry_duplicate_timestamp_count": reading_count - len(timestamps),
        "telemetry_has_readings": reading_count > 0,
        "telemetry_first_observed_at": first_at,
        "telemetry_last_observed_at": last_at,
        "telemetry_days_since_last_reading": (
            None if last_at is None else round(days_between(last_at, cutoff), 6)
        ),
        "telemetry_observed_span_days": (
            None
            if first_at is None or last_at is None
            else round(days_between(first_at, last_at), 6)
        ),
        "telemetry_coverage_ratio": None,
        "telemetry_missing_value_ratio": None,
        "telemetry_all_sensors_missing_count": 0,
        "telemetry_operating_hours_first": None,
        "telemetry_operating_hours_last": None,
    }

    if window_days is not None and reading_count > 0:
        distinct_days = len({normalize_timestamp(reading.timestamp).date() for reading in ordered})
        record["telemetry_coverage_ratio"] = round(
            min(1.0, distinct_days / float(window_days)), 6
        )

    if reading_count > 0:
        missing_cells = sum(
            1
            for reading in ordered
            for field in SENSOR_FIELDS
            if getattr(reading, field) is None
        )
        record["telemetry_missing_value_ratio"] = round(
            missing_cells / float(reading_count * len(SENSOR_FIELDS)), 6
        )
        record["telemetry_all_sensors_missing_count"] = sum(
            1
            for reading in ordered
            if all(getattr(reading, field) is None for field in SENSOR_FIELDS)
        )

    hours = [
        (reading.timestamp, reading.operating_hours_cumulative)
        for reading in ordered
        if reading.operating_hours_cumulative is not None
    ]
    if hours:
        hours.sort(key=lambda item: normalize_timestamp(item[0]))
        record["telemetry_operating_hours_first"] = int(hours[0][1])  # type: ignore[arg-type]
        record["telemetry_operating_hours_last"] = int(hours[-1][1])  # type: ignore[arg-type]

    for field in SENSOR_FIELDS:
        stats = summarize_sensor(_sensor_points(ordered, field))
        missing = reading_count - stats.count
        prefix = f"telemetry_{field}"
        record.update(
            {
                f"{prefix}_count": stats.count,
                f"{prefix}_missing": missing,
                f"{prefix}_missing_ratio": (
                    None if reading_count == 0 else round(missing / float(reading_count), 6)
                ),
                f"{prefix}_mean": stats.mean,
                f"{prefix}_median": stats.median,
                f"{prefix}_min": stats.minimum,
                f"{prefix}_max": stats.maximum,
                f"{prefix}_std": stats.std,
                f"{prefix}_first": stats.first,
                f"{prefix}_last": stats.last,
                f"{prefix}_change": stats.change,
                f"{prefix}_trend_per_day": stats.trend_per_day,
            }
        )

    return record


def telemetry_feature_names() -> list[str]:
    """Ordered feature names produced by :func:`telemetry_features`."""
    names = [
        "telemetry_reading_count",
        "telemetry_distinct_timestamp_count",
        "telemetry_duplicate_timestamp_count",
        "telemetry_has_readings",
        "telemetry_first_observed_at",
        "telemetry_last_observed_at",
        "telemetry_days_since_last_reading",
        "telemetry_observed_span_days",
        "telemetry_coverage_ratio",
        "telemetry_missing_value_ratio",
        "telemetry_all_sensors_missing_count",
        "telemetry_operating_hours_first",
        "telemetry_operating_hours_last",
    ]
    for field in SENSOR_FIELDS:
        prefix = f"telemetry_{field}"
        names.extend(
            [
                f"{prefix}_count",
                f"{prefix}_missing",
                f"{prefix}_missing_ratio",
                f"{prefix}_mean",
                f"{prefix}_median",
                f"{prefix}_min",
                f"{prefix}_max",
                f"{prefix}_std",
                f"{prefix}_first",
                f"{prefix}_last",
                f"{prefix}_change",
                f"{prefix}_trend_per_day",
            ]
        )
    return names
