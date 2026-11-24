"""Database and Alembic integration tests for the GridOps Intelligence schema."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url

from backend.app.models import AssetTelemetry, MaintenanceWorkOrder  # noqa: F401
from data_engineering.etl.config import resolve_database_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DATABASE_NAME = "gridops_migration_scratch"

EXPECTED_TABLES = {
    "assets",
    "transformer_details",
    "substation_details",
    "circuit_breaker_details",
    "feeder_details",
    "asset_telemetry",
    "maintenance_work_orders",
    "inspections",
    "failure_incidents",
    "weather_observations",
    "ingestion_dataset_results",
    "data_quality_results",
    "ingestion_runs",
}

EXPECTED_REVISION = "5e6f7a8b9c0d"


def _database_url(database_name: str) -> str:
    """Resolve a database URL for a dedicated integration-test database."""
    url = make_url(resolve_database_url()).set(database=database_name)
    return url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def migration_engine():
    """Provide a session-scoped engine on a dedicated scratch database at head."""
    url = _database_url(MIGRATION_DATABASE_NAME)
    admin_engine = create_engine(
        make_url(url).set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
            {"database_name": MIGRATION_DATABASE_NAME},
        ).scalar_one_or_none()
        if exists is None:
            with admin_engine.begin() as connection:
                connection.execute(text(f'CREATE DATABASE "{MIGRATION_DATABASE_NAME}"'))
    admin_engine.dispose()

    engine = create_engine(url, pool_pre_ping=True)
    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(alembic_config, "head")
    yield engine
    engine.dispose()


def test_database_connectivity(test_engine) -> None:
    """The integration test database is reachable and queryable."""
    with test_engine.begin() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_expected_tables_exist(test_engine) -> None:
    """All operational tables from the initial Alembic migration exist."""
    inspector = inspect(test_engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES.issubset(tables)
    assert "alembic_version" in tables


def test_primary_keys_and_foreign_keys(test_engine) -> None:
    """Assets, telemetry, and work orders expose the expected keys and FKs."""
    inspector = inspect(test_engine)
    assert inspector.get_pk_constraint("assets")["constrained_columns"] == ["asset_id"]
    assert inspector.get_pk_constraint("asset_telemetry")["constrained_columns"] == [
        "telemetry_id"
    ]

    telemetry_fks = inspector.get_foreign_keys("asset_telemetry")
    assert any(
        fk["referred_table"] == "assets" and fk["referred_columns"] == ["asset_id"]
        for fk in telemetry_fks
    )
    assert any(
        fk["referred_table"] == "assets" and fk["referred_columns"] == ["asset_id"]
        for fk in inspector.get_foreign_keys("maintenance_work_orders")
    )


def test_models_are_declared(test_engine) -> None:
    """The SQLAlchemy metadata declares the expected operational models."""
    from backend.app import models

    assert models.Asset is not None
    assert models.AssetTelemetry is not None
    assert models.MaintenanceWorkOrder is not None
    assert models.IngestionRun is not None


def test_alembic_upgrade_and_downgrade_are_reversible(migration_engine) -> None:
    """The initial revision can be downgraded and upgraded again."""
    config = Config("alembic.ini")
    config.set_main_option(
        "sqlalchemy.url", _database_url(MIGRATION_DATABASE_NAME).replace("%", "%%")
    )
    command.downgrade(config, "base")
    with migration_engine.begin() as connection:
        remaining = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            ).fetchall()
        }
        assert not (EXPECTED_TABLES | {"alembic_version"}).issubset(remaining)
    command.upgrade(config, "head")
    with migration_engine.begin() as connection:
        assert connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one() == EXPECTED_REVISION
