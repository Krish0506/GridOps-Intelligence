"""Generators for weather observations."""

from __future__ import annotations

import math
import random
from datetime import timedelta

from data_engineering.generators.base import iso_ts
from data_engineering.generators.config import (
    REFERENCE_DATE,
    WEATHER_BASE_TEMPERATURES,
    WEATHER_DUPLICATE_COUNT,
    WEATHER_OBSERVATIONS_RANGE,
    REGIONS,
)


def generate_weather(rng: random.Random) -> list[dict[str, str]]:
    """Generate synthetic weather observations for each region."""
    rows: list[dict[str, str]] = []
    counter = 0
    for region in REGIONS:
        for _ in range(rng.randint(*WEATHER_OBSERVATIONS_RANGE)):
            counter += 1
            day_of_year = rng.randrange(0, 366)
            seasonal = 12.0 * math.sin(2 * math.pi * day_of_year / 365.0)
            temperature = round(WEATHER_BASE_TEMPERATURES[region] + seasonal + rng.uniform(-3, 3), 1)
            wind_speed = round(rng.uniform(0, 40) + (rng.uniform(0, 5) if day_of_year > 300 else 0), 1)
            if rng.random() < 0.8:
                precipitation = round(rng.uniform(0, 5), 1)
            else:
                precipitation = round(rng.uniform(10, 60), 1)
            severe = "true" if (precipitation >= 20 and wind_speed >= 25) or rng.random() < 0.03 else "false"
            timestamp = REFERENCE_DATE - timedelta(days=rng.randrange(0, 370), hours=rng.randrange(0, 24))
            rows.append(
                {
                    "weather_id": f"WX-{counter:05d}",
                    "region": region,
                    "timestamp": iso_ts(timestamp),
                    "temperature_c": str(temperature),
                    "wind_speed_ms": str(wind_speed),
                    "precipitation_mm": str(precipitation),
                    "severe": severe,
                    "synthetic": "true",
                }
            )
    # Controlled duplicates for data-quality testing.
    for _ in range(WEATHER_DUPLICATE_COUNT):
        if rows:
            rows.append(dict(rng.choice(rows)))
    return rows
