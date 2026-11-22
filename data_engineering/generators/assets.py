"""Generators for utility asset records: transformers, substations,
circuit breakers, and feeders."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from data_engineering.generators.base import iso_ts
from data_engineering.generators.config import (
    CIRCUIT_BREAKER_COUNT,
    FEEDER_COUNT,
    REGIONS,
    SUBSTATION_COUNT,
    TRANSFORMER_COUNT,
    TRANSFORMER_TYPES,
    REFERENCE_DATE,
    ASSET_ID_FIELDS,
)


def _install_date(rng: random.Random) -> str:
    """A plausible installation date up to 90 days before the reference date."""
    earliest = datetime(2020, 1, 1)
    latest = REFERENCE_DATE - timedelta(days=90)
    return iso_ts(earliest + timedelta(days=rng.randrange(0, max(1, int((latest - earliest).days)))))


def generate_substations(rng: random.Random) -> list[dict[str, str]]:
    """Generate synthetic substation records."""
    rows = []
    for i in range(1, SUBSTATION_COUNT + 1):
        region = rng.choice(REGIONS)
        nominal_kv = rng.choice([115, 230, 345])
        rows.append(
            {
                ASSET_ID_FIELDS["substations"]: f"S-{i:05d}",
                "asset_type": "substations",
                "name": f"{region} Substation {i:03d}",
                "region": region,
                "nominal_kv": str(nominal_kv),
                "area_sq_mi": str(rng.randrange(20, 900)),
                "equipment_count": str(rng.randrange(4, 40)),
                "install_date": _install_date(rng),
                "operating_hours_cumulative": str(rng.randrange(0, 40000)),
                "status": "active" if rng.random() > 0.05 else "retired",
                "synthetic": "true",
            }
        )
    return rows


def generate_transformers(rng: random.Random, substations: list[dict[str, str]]) -> list[dict[str, str]]:
    """Generate synthetic transformer records with valid substation references."""
    rows = []
    for i in range(1, TRANSFORMER_COUNT + 1):
        substation = rng.choice(substations)
        rows.append(
            {
                ASSET_ID_FIELDS["transformers"]: f"T-{i:05d}",
                "asset_type": "transformers",
                "name": f"Transformer T-{i:04d}",
                "substation_id": substation["substation_id"],
                "winding_type": rng.choice(TRANSFORMER_TYPES),
                "rating_mva": str(rng.choice([5, 10, 25, 50, 100, 200])),
                "primary_kv": str(rng.choice([115, 138, 230, 345])),
                "secondary_kv": str(rng.choice([13.8, 34.5, 4.16, 6.6])),
                "install_date": _install_date(rng),
                "operating_hours_cumulative": str(rng.randrange(0, 50000)),
                "status": "active" if rng.random() > 0.05 else "retired",
                "synthetic": "true",
            }
        )
    return rows


def generate_circuit_breakers(rng: random.Random, substations: list[dict[str, str]]) -> list[dict[str, str]]:
    """Generate synthetic circuit-breaker records with valid substation references."""
    rows = []
    for i in range(1, CIRCUIT_BREAKER_COUNT + 1):
        substation = rng.choice(substations)
        rows.append(
            {
                ASSET_ID_FIELDS["circuit_breakers"]: f"CB-{i:05d}",
                "asset_type": "circuit_breakers",
                "name": f"Circuit Breaker CB-{i:04d}",
                "substation_id": substation["substation_id"],
                "panel_id": f"PAN-{i:04d}",
                "rated_current_a": str(rng.choice([125, 250, 400, 630, 1000])),
                "voltage_class": rng.choice(["115kV", "138kV", "230kV", "345kV"]),
                "install_date": _install_date(rng),
                "operating_hours_cumulative": str(rng.randrange(0, 12000)),
                "status": "active",
                "synthetic": "true",
            }
        )
    return rows


def generate_feeders(rng: random.Random, substations: list[dict[str, str]]) -> list[dict[str, str]]:
    """Generate synthetic feeder records with valid substation references."""
    rows = []
    for i in range(1, FEEDER_COUNT + 1):
        rows.append(
            {
                ASSET_ID_FIELDS["feeders"]: f"F-{i:05d}",
                "asset_type": "feeders",
                "name": f"Feeder F-{i:04d}",
                "substation_id": rng.choice(substations)["substation_id"],
                "voltage_kv": str(rng.choice([4.16, 12.5, 13.8])),
                "capacity_kva": str(rng.choice([500, 1000, 2000, 4000, 8000])),
                "length_km": str(round(rng.uniform(1.0, 40.0), 1)),
                "outage_count": str(rng.randrange(0, 8)),
                "operating_hours_cumulative": str(rng.randrange(0, 10000)),
                "status": "active",
                "synthetic": "true",
            }
        )
    return rows
