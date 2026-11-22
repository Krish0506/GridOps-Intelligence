"""Configuration and dataset contracts for the CSV-to-PostgreSQL ETL."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

from data_engineering.generators.config import (
    ASSET_ID_FIELDS,
    ASSET_TABLES,
    TABLE_FIELDNAMES,
    TABLES,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "generated"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "reports"
DEFAULT_REJECTED_DIR = PROJECT_ROOT / "data" / "rejected"
DEFAULT_BATCH_SIZE = 1_000

ASSET_DATASETS = list(ASSET_TABLES)
# Substation details must exist before transformer/breaker/feeder detail rows
# that reference them.
DETAIL_LOAD_ORDER = ["substations", "transformers", "circuit_breakers", "feeders"]
DEPENDENT_DATASETS = ["asset_telemetry", "work_orders", "inspections", "failures", "weather"]
DATASET_ORDER = ASSET_DATASETS + DEPENDENT_DATASETS

DATASET_FILES = {name: f"{name}.csv" for name in TABLES}
EXPECTED_COLUMNS = {name: list(TABLE_FIELDNAMES[name]) for name in TABLES}

# Source identifier column for every dataset.  Telemetry has no source id; its
# deterministic SHA-256 key is derived from the row content in transformers.py.
DATASET_ID_FIELDS = {
    **ASSET_ID_FIELDS,
    "work_orders": "work_order_id",
    "inspections": "inspection_id",
    "failures": "failure_id",
    "weather": "weather_id",
}

DATASET_ASSET_FIELDS = {
    "asset_telemetry": "asset_id",
    "work_orders": "asset_ref",
    "inspections": "asset_ref",
    "failures": "asset_ref",
}

DATASET_DISPLAY_NAMES = {
    "transformers": "Transformers",
    "substations": "Substations",
    "circuit_breakers": "Circuit breakers",
    "feeders": "Feeders",
    "asset_telemetry": "Asset telemetry",
    "work_orders": "Maintenance work orders",
    "inspections": "Inspections",
    "failures": "Failure incidents",
    "weather": "Weather observations",
}


class EtlSettings(BaseSettings):
    """Environment-backed ETL settings.

    ``GRIDOPS_DATABASE_URL`` takes precedence over ``DATABASE_URL`` so a host
    run can point at a test database without editing ``.env``.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    gridops_database_url: str | None = None
    database_url: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    # Published host port for the Docker PostgreSQL service.  The development
    # machine has local PostgreSQL servers on 5432/5433, so Compose publishes
    # the container on 55432.
    gridops_host_db_port: int = 55432
    postgres_db: str = "gridops"
    postgres_user: str = "gridops"
    postgres_password: str = Field(default="gridops_dev_only", repr=False)

    input_dir: Path = DEFAULT_INPUT_DIR
    report_dir: Path = DEFAULT_REPORT_DIR
    rejected_dir: Path = DEFAULT_REJECTED_DIR
    batch_size: int = Field(default=DEFAULT_BATCH_SIZE, ge=1, le=10_000)


def _built_url(settings: EtlSettings) -> URL:
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )


def resolve_database_url(explicit: str | None = None) -> str:
    """Resolve the target database URL without ever logging credentials.

    Docker Compose injects a ``db`` hostname.  When the ETL runs on the Windows
    host, that hostname is mapped to ``localhost`` because PostgreSQL is
    published on port 5432.  An explicit URL or ``GRIDOPS_DATABASE_URL`` always
    wins and is never rewritten.
    """
    settings = EtlSettings()
    if explicit:
        url = make_url(explicit)
    elif settings.gridops_database_url:
        url = make_url(settings.gridops_database_url)
    elif settings.database_url:
        url = make_url(settings.database_url)
    else:
        url = _built_url(settings)

    if os.name == "nt" and url.host == "db" and not explicit and not settings.gridops_database_url:
        # Use IPv4 explicitly; Docker's Windows port proxy can stall on ::1.
        url = url.set(host="127.0.0.1", port=settings.gridops_host_db_port)
    return url.render_as_string(hide_password=False)


def sanitized_destination(database_url: str) -> str:
    """Return ``host:port/database`` with credentials removed."""
    url = make_url(database_url)
    return f"{url.host or 'unknown'}:{url.port or 'default'}/{url.database or 'unknown'}"


def ensure_safe_database_name(database_url: str, *, require_suffix: str = "_test") -> str:
    """Guard destructive test helpers: refuse to operate on non-test databases."""
    database = make_url(database_url).database or ""
    if not database.endswith(require_suffix):
        raise RuntimeError(
            f"Refusing to modify database '{database}': name must end with '{require_suffix}'"
        )
    return database
