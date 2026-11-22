"""SQLAlchemy 2.x models for the GridOps Intelligence operational schema.

The schema separates the common asset attributes (``assets``) from the
type-specific attributes (``transformer_details`` and friends).  Telemetry,
maintenance, inspection, failure, and weather records all reference the unified
asset identifier so foreign-key integrity is enforced by PostgreSQL.

All source records are synthetic.  ``synthetic`` is present on every fact and
dimension table and defaults to ``True``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base with deterministic constraint names for Alembic."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Created/updated timestamps maintained by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Asset(TimestampMixin, Base):
    """Unified asset dimension for transformers, substations, breakers, and feeders."""

    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "asset_type IN ('transformers', 'substations', 'circuit_breakers', 'feeders')",
            name="asset_type",
        ),
        CheckConstraint("status IN ('active', 'retired')", name="status"),
        CheckConstraint(
            "operating_hours_cumulative IS NULL OR operating_hours_cumulative >= 0",
            name="operating_hours_non_negative",
        ),
        Index("ix_assets_asset_type_status", "asset_type", "status"),
    )

    asset_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    install_date: Mapped[date | None] = mapped_column(Date)
    operating_hours_cumulative: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    region: Mapped[str | None] = mapped_column(String(8))
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    transformer_detail: Mapped["TransformerDetail | None"] = relationship(
        back_populates="asset",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="TransformerDetail.asset_id",
    )
    substation_detail: Mapped["SubstationDetail | None"] = relationship(
        back_populates="asset",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="SubstationDetail.asset_id",
    )
    circuit_breaker_detail: Mapped["CircuitBreakerDetail | None"] = relationship(
        back_populates="asset",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="CircuitBreakerDetail.asset_id",
    )
    feeder_detail: Mapped["FeederDetail | None"] = relationship(
        back_populates="asset",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="FeederDetail.asset_id",
    )


class SubstationDetail(Base):
    """Substation-only attributes."""

    __tablename__ = "substation_details"
    __table_args__ = (
        CheckConstraint("nominal_kv > 0", name="nominal_kv_positive"),
        CheckConstraint("area_sq_mi >= 0", name="area_non_negative"),
        CheckConstraint("equipment_count >= 0", name="equipment_count_non_negative"),
    )

    asset_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("assets.asset_id", ondelete="CASCADE"), primary_key=True
    )
    nominal_kv: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    area_sq_mi: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    equipment_count: Mapped[int] = mapped_column(Integer, nullable=False)

    asset: Mapped[Asset] = relationship(
        back_populates="substation_detail", foreign_keys=[asset_id]
    )


class TransformerDetail(Base):
    """Transformer-only attributes and substation relationship."""

    __tablename__ = "transformer_details"
    __table_args__ = (
        CheckConstraint("rating_mva > 0", name="rating_positive"),
        CheckConstraint("primary_kv > 0", name="primary_kv_positive"),
        CheckConstraint("secondary_kv > 0", name="secondary_kv_positive"),
    )

    asset_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("assets.asset_id", ondelete="CASCADE"), primary_key=True
    )
    substation_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("substation_details.asset_id", ondelete="RESTRICT"), nullable=False
    )
    winding_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rating_mva: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    primary_kv: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    secondary_kv: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)

    asset: Mapped[Asset] = relationship(
        back_populates="transformer_detail", foreign_keys=[asset_id]
    )


class CircuitBreakerDetail(Base):
    """Circuit-breaker-only attributes and substation relationship."""

    __tablename__ = "circuit_breaker_details"
    __table_args__ = (
        CheckConstraint("rated_current_a > 0", name="rated_current_positive"),
        CheckConstraint(
            "voltage_class IN ('115kV', '138kV', '230kV', '345kV')", name="voltage_class"
        ),
    )

    asset_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("assets.asset_id", ondelete="CASCADE"), primary_key=True
    )
    substation_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("substation_details.asset_id", ondelete="RESTRICT"), nullable=False
    )
    panel_id: Mapped[str] = mapped_column(String(32), nullable=False)
    rated_current_a: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    voltage_class: Mapped[str] = mapped_column(String(8), nullable=False)

    asset: Mapped[Asset] = relationship(
        back_populates="circuit_breaker_detail", foreign_keys=[asset_id]
    )


class FeederDetail(Base):
    """Feeder-only attributes and substation relationship."""

    __tablename__ = "feeder_details"
    __table_args__ = (
        CheckConstraint("voltage_kv > 0", name="voltage_positive"),
        CheckConstraint("capacity_kva > 0", name="capacity_positive"),
        CheckConstraint("length_km >= 0", name="length_non_negative"),
        CheckConstraint("outage_count >= 0", name="outage_count_non_negative"),
    )

    asset_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("assets.asset_id", ondelete="CASCADE"), primary_key=True
    )
    substation_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("substation_details.asset_id", ondelete="RESTRICT"), nullable=False
    )
    voltage_kv: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    capacity_kva: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    length_km: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    outage_count: Mapped[int] = mapped_column(Integer, nullable=False)

    asset: Mapped[Asset] = relationship(
        back_populates="feeder_detail", foreign_keys=[asset_id]
    )


class AssetTelemetry(Base):
    """Time-series sensor readings.

    ``telemetry_id`` is a SHA-256 digest of the canonical source row.  This
    keeps ingestion idempotent for exact duplicate rows while preserving
    distinct readings that share an asset/timestamp (the synthetic generator
    intentionally emits both normal and elevated readings at the same minute).
    Sensor measurement columns are nullable because the source intentionally
    contains missing readings.
    """

    __tablename__ = "asset_telemetry"
    __table_args__ = (
        Index("ix_asset_telemetry_asset_timestamp", "asset_id", "timestamp"),
        Index("ix_asset_telemetry_timestamp", "timestamp"),
    )

    telemetry_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    load_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    voltage_kv: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    current_a: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    vibration_mm_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    operating_hours_cumulative: Mapped[int] = mapped_column(Integer, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    asset: Mapped[Asset] = relationship(foreign_keys=[asset_id])


class MaintenanceWorkOrder(Base):
    """Maintenance work orders tied to an asset."""

    __tablename__ = "maintenance_work_orders"
    __table_args__ = (
        CheckConstraint(
            "work_type IN ('corrective', 'preventive', 'scheduled')", name="work_type"
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')", name="priority"
        ),
        CheckConstraint(
            "status IN ('open', 'in_progress', 'completed', 'cancelled')", name="status"
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= opened_at", name="completion_after_open"
        ),
        Index("ix_work_orders_asset_status", "asset_id", "status"),
        Index("ix_work_orders_opened_at", "opened_at"),
    )

    work_order_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    asset_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False
    )
    work_type: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    asset: Mapped[Asset] = relationship(foreign_keys=[asset_id])


class Inspection(Base):
    """Asset inspection records."""

    __tablename__ = "inspections"
    __table_args__ = (
        CheckConstraint(
            "condition IN ('excellent', 'good', 'fair', 'poor')", name="condition"
        ),
        CheckConstraint(
            "severity IN ('none', 'low', 'medium', 'high')", name="severity"
        ),
        Index("ix_inspections_asset_date", "asset_id", "inspection_date"),
    )

    inspection_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    asset_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False
    )
    inspection_date: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    condition: Mapped[str] = mapped_column(String(16), nullable=False)
    findings: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    asset: Mapped[Asset] = relationship(foreign_keys=[asset_id])


class FailureIncident(Base):
    """Failure incident labels, kept isolated from telemetry features."""

    __tablename__ = "failure_incidents"
    __table_args__ = (
        CheckConstraint("failure_severity BETWEEN 1 AND 5", name="severity_range"),
        CheckConstraint("downtime_hours >= 0", name="downtime_non_negative"),
        Index("ix_failures_asset_timestamp", "asset_id", "failure_timestamp"),
        Index("ix_failures_timestamp", "failure_timestamp"),
    )

    failure_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    asset_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False
    )
    failure_category: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    failure_severity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    downtime_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    asset: Mapped[Asset] = relationship(foreign_keys=[asset_id])


class WeatherObservation(Base):
    """Regional weather observations used as environmental context."""

    __tablename__ = "weather_observations"
    __table_args__ = (
        CheckConstraint("wind_speed_ms >= 0", name="wind_non_negative"),
        CheckConstraint("precipitation_mm >= 0", name="precipitation_non_negative"),
        Index("ix_weather_region_timestamp", "region", "timestamp"),
    )

    weather_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    region: Mapped[str] = mapped_column(String(8), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    temperature_c: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    wind_speed_ms: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    precipitation_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    severe: Mapped[bool] = mapped_column(Boolean, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class IngestionRun(Base):
    """One ETL invocation, including aggregate row counts and status."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'completed_with_rejections', 'failed', 'dry_run')",
            name="status",
        ),
        Index("ix_ingestion_runs_started_at", "started_at"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rows_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    report_path: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    dataset_results: Mapped[list["IngestionDatasetResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    quality_results: Mapped[list["DataQualityResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class IngestionDatasetResult(Base):
    """Per-dataset counts for one ingestion run."""

    __tablename__ = "ingestion_dataset_results"
    __table_args__ = (
        UniqueConstraint("run_id", "dataset_name", name="uq_run_dataset"),
        CheckConstraint(
            "status IN ('completed', 'completed_with_rejections', 'failed')", name="status"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    dataset_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rows_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[IngestionRun] = relationship(back_populates="dataset_results")


class DataQualityResult(Base):
    """Persisted data-quality check result for one dataset and run."""

    __tablename__ = "data_quality_results"
    __table_args__ = (
        Index("ix_data_quality_run_dataset", "run_id", "dataset_name"),
        CheckConstraint("severity IN ('ERROR', 'WARNING', 'INFO')", name="severity"),
    )

    result_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    dataset_name: Mapped[str] = mapped_column(String(64), nullable=False)
    check_name: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    records_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[IngestionRun] = relationship(back_populates="quality_results")
