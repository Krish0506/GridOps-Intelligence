"""Historical regional weather features.

Source: ``weather_observations``.  Weather rows are keyed by ``region`` rather
than ``asset_id``; an asset inherits the observations for its own region.  An
asset with a missing region gets an explicit "no weather history" result rather
than an imputed value.

Only observations with ``timestamp < prediction_cutoff`` are eligible.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from ml.features.cutoff import (
    days_between,
    filter_window,
    normalize_timestamp,
    sorted_by_time,
)
from ml.features.telemetry import summarize_sensor
from ml.features.types import WeatherRecord


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def weather_features(
    observations: Iterable[WeatherRecord],
    region: str | None,
    prediction_cutoff: datetime,
    window_days: int | float | None = None,
    exclude_at_or_after: datetime | None = None,
) -> dict[str, object]:
    """Aggregate weather strictly before ``prediction_cutoff`` for one region.

    Parameters
    ----------
    observations:
        Weather observations; only rows for ``region`` are considered.
    region:
        Region the observations belong to; ``None`` yields the empty-history
        record without raising.
    prediction_cutoff:
        Exclusive upper bound for observation eligibility.
    window_days:
        Optional lookback window, e.g. ``30`` for the last 30 days.
    exclude_at_or_after:
        Optional event bound (typically the first known failure timestamp).
        Observations at or after the bound are excluded.
    """
    cutoff = normalize_timestamp(prediction_cutoff)
    record: dict[str, object] = {
        "weather_region": region,
        "weather_observation_count": 0,
        "weather_has_history": False,
        "weather_temperature_mean": None,
        "weather_temperature_median": None,
        "weather_temperature_min": None,
        "weather_temperature_max": None,
        "weather_temperature_std": None,
        "weather_temperature_trend_per_day": None,
        "weather_wind_speed_mean": None,
        "weather_wind_speed_max": None,
        "weather_precipitation_mean": None,
        "weather_precipitation_max": None,
        "weather_precipitation_total_mm": None,
        "weather_severe_count": 0,
        "weather_severe_ratio": None,
        "weather_days_since_latest": None,
    }

    if region is None:
        return record

    eligible = filter_window(
        (
            observation
            for observation in observations
            if observation.region == region
        ),
        cutoff,
        key=lambda observation: observation.timestamp,
        window_days=window_days,
        exclude_at_or_after=exclude_at_or_after,
    )
    ordered = sorted_by_time(eligible, key=lambda observation: observation.timestamp)
    total = len(ordered)
    record["weather_observation_count"] = total

    if not ordered:
        return record

    record["weather_has_history"] = True
    temperatures = [float(observation.temperature_c) for observation in ordered]
    winds = [float(observation.wind_speed_ms) for observation in ordered]
    precipitation = [float(observation.precipitation_mm) for observation in ordered]

    temp_stats = summarize_sensor(
        [(observation.timestamp, float(observation.temperature_c)) for observation in ordered]
    )
    record.update(
        {
            "weather_temperature_mean": temp_stats.mean,
            "weather_temperature_median": temp_stats.median,
            "weather_temperature_min": temp_stats.minimum,
            "weather_temperature_max": temp_stats.maximum,
            "weather_temperature_std": temp_stats.std,
            "weather_temperature_trend_per_day": temp_stats.trend_per_day,
            "weather_wind_speed_mean": _round(sum(winds) / total),
            "weather_wind_speed_max": _round(max(winds)),
            "weather_precipitation_mean": _round(sum(precipitation) / total),
            "weather_precipitation_max": _round(max(precipitation)),
            "weather_precipitation_total_mm": _round(sum(precipitation)),
            "weather_severe_count": sum(1 for observation in ordered if observation.severe),
            "weather_days_since_latest": round(
                days_between(ordered[-1].timestamp, cutoff), 6
            ),
        }
    )
    record["weather_severe_ratio"] = round(
        int(record["weather_severe_count"]) / float(total), 6  # type: ignore[arg-type]
    )
    return record


def weather_feature_names() -> list[str]:
    """Ordered feature names produced by :func:`weather_features`."""
    return [
        "weather_region",
        "weather_observation_count",
        "weather_has_history",
        "weather_temperature_mean",
        "weather_temperature_median",
        "weather_temperature_min",
        "weather_temperature_max",
        "weather_temperature_std",
        "weather_temperature_trend_per_day",
        "weather_wind_speed_mean",
        "weather_wind_speed_max",
        "weather_precipitation_mean",
        "weather_precipitation_max",
        "weather_precipitation_total_mm",
        "weather_severe_count",
        "weather_severe_ratio",
        "weather_days_since_latest",
    ]
