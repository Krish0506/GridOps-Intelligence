"""Shared fixtures for the GridOps Intelligence integration test suite."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models import Base
from data_engineering.etl.config import DEFAULT_BATCH_SIZE, DEFAULT_INPUT_DIR, resolve_database_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_NAME = "gridops_test"
TEST_TABLES = [
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
]


def _test_database_url() -> str:
    """Resolve a dedicated test database URL without credentials in reports."""
    url = make_url(resolve_database_url()).set(database=TEST_DATABASE_NAME)
    return url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def test_engine():
    """Provide a SQLAlchemy engine bound to a dedicated migrated test database."""
    url = _test_database_url()
    admin_url = make_url(url).set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    with admin_engine.connect() as connection:
        database_exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
            {"database_name": TEST_DATABASE_NAME},
        ).scalar_one_or_none()
        if database_exists is None:
            with admin_engine.begin() as connection:
                connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"'))
    admin_engine.dispose()

    engine = create_engine(url, pool_pre_ping=True)
    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(alembic_config, "head")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_session_factory(test_engine):
    """Provide a shared session factory bound to the test engine."""
    return sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def clean_db(test_engine):
    """Truncate all operational tables inside the dedicated test database."""
    with test_engine.begin() as connection:
        connection.execute(
            text("TRUNCATE TABLE " + ", ".join(TEST_TABLES) + " RESTART IDENTITY CASCADE")
        )
    yield test_engine


@pytest.fixture
def db_session(test_engine):
    """Provide a request-scoped session for API tests."""
    session = Session(bind=test_engine, autoflush=False, expire_on_commit=False)
    yield session
    session.close()


@pytest.fixture(scope="session")
def ingested_db(db_session_factory, test_engine):
    """Generate synthetic data and ingest it once into the test database."""
    from pathlib import Path

    from data_engineering.etl.orchestrator import run_ingestion

    report_dir = Path("/tmp") / "gridops_int_test_reports"
    rejected_dir = Path("/tmp") / "gridops_int_test_rejected"
    report_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir.mkdir(parents=True, exist_ok=True)
    with test_engine.begin() as connection:
        connection.execute(
            text("TRUNCATE TABLE " + ", ".join(TEST_TABLES) + " RESTART IDENTITY CASCADE")
        )
    report = run_ingestion(
        input_dir=DEFAULT_INPUT_DIR,
        batch_size=DEFAULT_BATCH_SIZE,
        dry_run=False,
        report_dir=report_dir,
        rejected_dir=rejected_dir,
        database_url=_test_database_url(),
    )
    assert report["status"] == "completed"
    return report


@pytest.fixture
def api_client(db_session):
    """Provide a TestClient with the database dependency overridden to the test DB."""

    def override_get_db():
        yield db_session
        return None

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
