"""Configuration constants for reproducible synthetic data generation.

All records produced by this package are synthetic. See ``ARCHITECTURE.md``:
``data/generated`` is the generated-data boundary.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "generated"

# Reproducible generation seed.
DEFAULT_SEED = 20261121
# Anchor "now" so runs are independent of the wall clock and fully reproducible.
REFERENCE_DATE = datetime(2026, 11, 21, 12, 0, 0)

ASSET_TABLES = ["transformers", "substations", "circuit_breakers", "feeders"]
TABLES = ASSET_TABLES + ["asset_telemetry", "work_orders", "inspections", "failures", "weather"]

# Identifier column per asset table.
ASSET_ID_FIELDS = {
    "transformers": "transformer_id",
    "substations": "substation_id",
    "circuit_breakers": "breaker_id",
    "feeders": "feeder_id",
}

TABLE_FIELDNAMES = {
    "transformers": [
        "transformer_id", "asset_type", "name", "substation_id", "winding_type",
        "rating_mva", "primary_kv", "secondary_kv", "install_date",
        "operating_hours_cumulative", "status", "synthetic",
    ],
    "substations": [
        "substation_id", "asset_type", "name", "region", "nominal_kv", "area_sq_mi",
        "equipment_count", "install_date", "operating_hours_cumulative", "status", "synthetic",
    ],
    "circuit_breakers": [
        "breaker_id", "asset_type", "name", "substation_id", "panel_id",
        "rated_current_a", "voltage_class", "install_date", "operating_hours_cumulative",
        "status", "synthetic",
    ],
    "feeders": [
        "feeder_id", "asset_type", "name", "substation_id", "voltage_kv", "capacity_kva",
        "length_km", "outage_count", "operating_hours_cumulative", "status", "synthetic",
    ],
    "asset_telemetry": [
        "asset_id", "asset_type", "timestamp", "temperature_c", "load_pct", "voltage_kv",
        "current_a", "vibration_mm_s", "operating_hours_cumulative", "synthetic",
    ],
    "work_orders": [
        "work_order_id", "asset_ref", "work_type", "priority", "status",
        "opened_at", "completed_at", "synthetic",
    ],
    "inspections": [
        "inspection_id", "inspection_date", "asset_ref", "condition", "findings",
        "severity", "synthetic",
    ],
    "failures": [
        "failure_id", "asset_ref", "failure_category", "failure_timestamp",
        "failure_severity", "downtime_hours", "synthetic",
    ],
    "weather": [
        "weather_id", "region", "timestamp", "temperature_c", "wind_speed_ms",
        "precipitation_mm", "severe", "synthetic",
    ],
}

# ---------------------------------------------------------------------------
# Asset counts.
ASSET_COUNT_TARGET = 1_000
TRANSFORMER_COUNT = 1_200
SUBSTATION_COUNT = 300
CIRCUIT_BREAKER_COUNT = 800
FEEDER_COUNT = 300

# ---------------------------------------------------------------------------
# Vocabularies and categories (validated by the validation module).
ID_PATTERNS = {
    "transformers": r"^T-\d{5}$",
    "substations": r"^S-\d{5}$",
    "circuit_breakers": r"^CB-\d{5}$",
    "feeders": r"^F-\d{5}$",
    "work_orders": r"^WO-\d{5}$",
    "inspections": r"^INSP-\d{5}$",
    "failures": r"^FAIL-\d{5}$",
    "weather": r"^WX-\d{5}$",
}

REGIONS = ["DAL", "CHI", "ATL", "DEN", "SEA", "CAL", "HOU", "MIN"]
ASSET_STATUSES = ["active", "retired"]
TRANSFORMER_TYPES = ["Dyn11", "Yd11", "Dyn5"]
ASSET_CATEGORY_FIELDS = {
    "transformers": ("winding_type", set(TRANSFORMER_TYPES)),
    "circuit_breakers": ("voltage_class", {"115kV", "138kV", "230kV", "345kV"}),
}

FAILURE_CATEGORIES = [
    "TransformerOverheating", "BushingFlashover", "WindingInsulationFault",
    "RadialOvercurrent", "CoolingSystemFailure", "InstrumentTransformerFailure",
    "ProtectiveRelayFailure", "ShuntingFailure", "ControlCircuitFailure",
    "SubstationBusFault", "IsolationSwitchFailure", "CircuitBreakerTrip",
    "DisconnectSwitchFault", "MechanicalBoltTightening", "GroundConnectionFault",
    "TransformerBankOverheating", "MechanicalBearingFailure", "ContactWear",
    "ArcQuencherFault", "OperatingTimeExcess", "TripCoilFailure",
    "FeederOvercurrent", "OverheadConductorFailure", "FeederReclosureFailure",
    "GEGFault", "UndervoltageFault", "FeederIsolationSwitchFailure",
]
CATEGORY_BY_ASSET_TYPE = {
    "transformers": [
        "TransformerOverheating", "BushingFlashover", "WindingInsulationFault",
        "RadialOvercurrent", "CoolingSystemFailure", "InstrumentTransformerFailure",
        "ProtectiveRelayFailure", "ShuntingFailure", "ControlCircuitFailure",
    ],
    "substations": [
        "SubstationBusFault", "IsolationSwitchFailure", "CircuitBreakerTrip",
        "DisconnectSwitchFault", "MechanicalBoltTightening",
        "GroundConnectionFault", "TransformerBankOverheating",
    ],
    "circuit_breakers": [
        "CircuitBreakerTrip", "MechanicalBearingFailure", "ContactWear",
        "ArcQuencherFault", "OperatingTimeExcess", "TripCoilFailure",
    ],
    "feeders": [
        "FeederOvercurrent", "OverheadConductorFailure", "FeederReclosureFailure",
        "GEGFault", "UndervoltageFault", "FeederIsolationSwitchFailure",
    ],
}

PRIORITIES = ["low", "medium", "high", "critical"]
PRIORITY_FROM_SEVERITY = {1: "low", 2: "low", 3: "medium", 4: "high", 5: "critical"}
WORK_TYPES = ["corrective", "preventive", "scheduled"]
WORK_STATUSES = ["open", "in_progress", "completed", "cancelled"]
INSPECTION_CONDITIONS = ["excellent", "good", "fair", "poor"]
INSPECTION_SEVERITIES = ["none", "low", "medium", "high"]

# ---------------------------------------------------------------------------
# Generation parameters.
FAILURE_COUNT = 60
INSPECTION_TARGET_COUNT = 120

TELEMETRY_MIN_SAMPLES = {"transformers": 30, "substations": 15, "circuit_breakers": 8, "feeders": 8}
TELEMETRY_MAX_SAMPLES = {"transformers": 60, "substations": 30, "circuit_breakers": 20, "feeders": 15}

TELEMETRY_TEMPERATURE_RANGES = {
    "transformers": (35.0, 75.0),
    "substations": (15.0, 45.0),
    "circuit_breakers": (25.0, 55.0),
    "feeders": (15.0, 40.0),
}
TELEMETRY_LOAD_RANGES = {
    "transformers": (45.0, 100.0),
    "substations": (20.0, 100.0),
    "circuit_breakers": (20.0, 100.0),
    "feeders": (20.0, 100.0),
}
TELEMETRY_VIBRATION_RANGES = {
    "transformers": (0.0, 3.0),
    "substations": (0.0, 1.5),
    "circuit_breakers": (0.0, 1.5),
    "feeders": (0.0, 3.0),
}
ABNORMAL_RANGES = {
    "transformers": {
        "temperature_c": (78.0, 85.0), "vibration_mm_s": (5.0, 10.0),
        "load_pct": (92.0, 100.0),
    },
    "substations": {
        "temperature_c": (45.0, 62.0), "vibration_mm_s": (3.0, 6.0),
        "load_pct": (92.0, 100.0),
    },
    "circuit_breakers": {
        "temperature_c": (48.0, 60.0), "vibration_mm_s": (2.0, 4.0),
        "load_pct": (92.0, 100.0),
    },
    "feeders": {
        "temperature_c": (38.0, 48.0), "vibration_mm_s": (3.0, 5.0),
        "load_pct": (92.0, 100.0),
    },
}
BASE_TEMPERATURE = {
    "transformers": 45.0, "substations": 25.0, "circuit_breakers": 35.0, "feeders": 18.0,
}

# Controlled data-quality artifacts: missing values and duplicates.
TELEMETRY_MISSING_RATE = 0.01
TELEMETRY_MISSING_FIELDS = ("temperature_c", "vibration_mm_s", "load_pct", "current_a")
TELEMETRY_DUPLICATE_COUNT = 5
WORK_ORDER_DUPLICATE_COUNT = 3
INSPECTION_DUPLICATE_COUNT = 2
WEATHER_DUPLICATE_COUNT = 2

WEATHER_BASE_TEMPERATURES = {
    "DAL": 24, "CHI": 8, "ATL": 28, "DEN": 5, "SEA": 14, "CAL": 18, "HOU": 26, "MIN": 5,
}
WEATHER_OBSERVATIONS_RANGE = (80, 160)

# ---------------------------------------------------------------------------
# Validation parameters.
COMPLETENESS_MIN = 0.95
ASSET_REQUIRED_FIELDS = {
    "transformers": [
        "name", "substation_id", "winding_type", "rating_mva", "primary_kv",
        "secondary_kv", "install_date", "operating_hours_cumulative", "status",
    ],
    "substations": [
        "name", "region", "nominal_kv", "area_sq_mi", "equipment_count",
        "install_date", "operating_hours_cumulative", "status",
    ],
    "circuit_breakers": [
        "name", "substation_id", "panel_id", "rated_current_a", "voltage_class",
        "install_date", "operating_hours_cumulative", "status",
    ],
    "feeders": [
        "name", "substation_id", "voltage_kv", "capacity_kva", "length_km",
        "outage_count", "operating_hours_cumulative", "status",
    ],
}
ASSET_TIMESTAMP_FIELDS = {
    "transformers": ["install_date"],
    "substations": ["install_date"],
    "circuit_breakers": ["install_date"],
    "feeders": [],
}
ASSET_RANGES = {
    "transformers": {
        "rating_mva": (0.5, 500), "primary_kv": (10, 500), "secondary_kv": (1, 500),
        "operating_hours_cumulative": (0, 50000),
    },
    "substations": {
        "nominal_kv": (10, 500), "area_sq_mi": (0, 5000), "equipment_count": (1, 200),
        "operating_hours_cumulative": (0, 50000),
    },
    "circuit_breakers": {
        "rated_current_a": (50, 1200), "operating_hours_cumulative": (0, 12000),
    },
    "feeders": {
        "voltage_kv": (1, 20), "capacity_kva": (100, 12000), "length_km": (0, 100),
        "outage_count": (0, 20), "operating_hours_cumulative": (0, 10000),
    },
}
ASSET_STATUS_VALUES = set(ASSET_STATUSES)
TELEMETRY_REQUIRED_FIELDS = [
    "asset_id", "asset_type", "timestamp", "temperature_c", "load_pct", "voltage_kv",
    "current_a", "vibration_mm_s", "operating_hours_cumulative",
]
TELEMETRY_RANGES = {
    "temperature_c": (-40.0, 90.0),
    "load_pct": (0.0, 130.0),
    "voltage_kv": (0.0, 400.0),
    "current_a": (0.0, 6000.0),
    "vibration_mm_s": (0.0, 50.0),
    "operating_hours_cumulative": (0.0, 500000.0),
}
WORK_ORDER_REQUIRED_FIELDS = ["asset_ref", "work_type", "priority", "status", "opened_at"]
INSPECTION_REQUIRED_FIELDS = [
    "inspection_id", "inspection_date", "asset_ref", "condition", "findings", "severity",
]
FAILURE_REQUIRED_FIELDS = [
    "asset_ref", "failure_category", "failure_timestamp", "failure_severity", "downtime_hours",
]
FAILURE_RANGES = {
    "failure_severity": (1.0, 5.0),
    "downtime_hours": (0.0, 720.0),
}
WEATHER_REQUIRED_FIELDS = [
    "region", "timestamp", "temperature_c", "wind_speed_ms", "precipitation_mm", "severe",
]
WEATHER_RANGES = {
    "temperature_c": (-40.0, 80.0),
    "wind_speed_ms": (0.0, 60.0),
    "precipitation_mm": (0.0, 100.0),
}

def id_pattern(table: str) -> re.Pattern[str]:
    """Compiled identifier pattern for a table."""
    return re.compile(ID_PATTERNS[table])
