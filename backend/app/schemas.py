"""Pydantic response schemas for the GridOps Intelligence API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from backend.app.models import (
    Asset,
    AssetTelemetry,
    CircuitBreakerDetail,
    DataQualityResult,
    FailureIncident,
    FeederDetail,
    IngestionDatasetResult,
    IngestionRun,
    MaintenanceWorkOrder,
    SubstationDetail,
    TransformerDetail,
)

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """One paginated API response."""

    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)


class AssetOut(BaseModel):
    """Read-only asset response."""

    model_config = {"from_attributes": True}

    asset_id: str
    asset_type: str
    name: str
    install_date: date | None
    operating_hours_cumulative: int | None
    status: str
    region: str | None
    synthetic: bool


class TransformerDetailOut(BaseModel):
    """Transformer-specific detail response."""

    model_config = {"from_attributes": True}

    asset_id: str
    substation_id: str
    winding_type: str
    rating_mva: float
    primary_kv: float
    secondary_kv: float


class SubstationDetailOut(BaseModel):
    """Substation-specific detail response."""

    model_config = {"from_attributes": True}

    asset_id: str
    nominal_kv: float
    area_sq_mi: float
    equipment_count: int


class CircuitBreakerDetailOut(BaseModel):
    """Circuit-breaker-specific detail response."""

    model_config = {"from_attributes": True}

    asset_id: str
    substation_id: str
    panel_id: str
    rated_current_a: float
    voltage_class: str


class FeederDetailOut(BaseModel):
    """Feeder-specific detail response."""

    model_config = {"from_attributes": True}

    asset_id: str
    substation_id: str
    voltage_kv: float
    capacity_kva: float
    length_km: float
    outage_count: int


class AssetDetailOut(AssetOut):
    """Asset response including the type-specific detail when present."""

    model_config = {"from_attributes": True}

    substation_detail: SubstationDetailOut | None = None
    transformer_detail: TransformerDetailOut | None = None
    circuit_breaker_detail: CircuitBreakerDetailOut | None = None
    feeder_detail: FeederDetailOut | None = None


class TelemetryOut(BaseModel):
    """Telemetry reading response."""

    model_config = {"from_attributes": True}

    telemetry_id: str
    asset_id: str
    asset_type: str
    timestamp: datetime
    temperature_c: float | None
    load_pct: float | None
    voltage_kv: float
    current_a: float | None
    vibration_mm_s: float | None
    operating_hours_cumulative: int
    synthetic: bool


class FailureOut(BaseModel):
    """Failure incident response."""

    model_config = {"from_attributes": True}

    failure_id: str
    asset_id: str
    failure_category: str
    failure_timestamp: datetime
    failure_severity: int
    downtime_hours: float
    synthetic: bool


class WorkOrderOut(BaseModel):
    """Maintenance work-order response."""

    model_config = {"from_attributes": True}

    work_order_id: str
    asset_id: str
    work_type: str
    priority: str
    status: str
    opened_at: datetime
    completed_at: datetime | None
    synthetic: bool


class IngestionDatasetResultOut(BaseModel):
    """Per-dataset ingestion result response."""

    model_config = {"from_attributes": True}

    dataset_name: str
    source_file: str
    status: str
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    rows_rejected: int
    validation_errors: int
    validation_warnings: int
    duration_ms: int
    error_summary: str | None


class IngestionRunOut(BaseModel):
    """Ingestion run response."""

    model_config = {"from_attributes": True}

    run_id: str
    source_name: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    dry_run: bool
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    rows_rejected: int
    error_summary: str | None
    report_path: str | None
    dataset_results: list[IngestionDatasetResultOut] = []
    quality_results: list[DataQualityResultOut] = []


class DataQualityResultOut(BaseModel):
    """Data-quality check response."""

    model_config = {"from_attributes": True}

    result_id: int
    run_id: str
    dataset_name: str
    check_name: str
    severity: str
    records_checked: int
    records_passed: int
    records_failed: int
    details: dict | None
    created_at: datetime


class AssetFilters(BaseModel):
    """Query filters for asset listing."""

    asset_type: str | None = None
    status: str | None = None
    region: str | None = None


class TelemetryFilters(BaseModel):
    """Query filters for telemetry."""

    asset_id: str
    start: datetime | None = None
    end: datetime | None = None


class FailureFilters(BaseModel):
    """Query filters for failure listing."""

    failure_category: str | None = None
    failure_severity: int | None = None
    asset_id: str | None = None


class WorkOrderFilters(BaseModel):
    """Query filters for maintenance work-order listing."""

    work_type: str | None = None
    priority: str | None = None
    status: str | None = None
    asset_id: str | None = None


def asset_response(asset: Asset) -> AssetOut:
    """Convert a SQLAlchemy asset to its API response."""
    return AssetOut.model_validate(asset)


def asset_detail_response(asset: Asset) -> AssetDetailOut:
    """Convert a SQLAlchemy asset with type-specific detail to the API response."""
    base = asset_response(asset)
    response = AssetDetailOut(
        asset_id=base.asset_id,
        asset_type=base.asset_type,
        name=base.name,
        install_date=base.install_date,
        operating_hours_cumulative=base.operating_hours_cumulative,
        status=base.status,
        region=base.region,
        synthetic=base.synthetic,
    )
    response.substation_detail = (
        SubstationDetailOut.model_validate(asset.substation_detail)
        if asset.substation_detail
        else None
    )
    response.transformer_detail = (
        TransformerDetailOut.model_validate(asset.transformer_detail)
        if asset.transformer_detail
        else None
    )
    response.circuit_breaker_detail = (
        CircuitBreakerDetailOut.model_validate(asset.circuit_breaker_detail)
        if asset.circuit_breaker_detail
        else None
    )
    response.feeder_detail = (
        FeederDetailOut.model_validate(asset.feeder_detail) if asset.feeder_detail else None
    )
    return response


def telemetry_response(row: AssetTelemetry) -> TelemetryOut:
    """Convert a telemetry row to its API response."""
    return TelemetryOut.model_validate(row)


def failure_response(row: FailureIncident) -> FailureOut:
    """Convert a failure row to its API response."""
    return FailureOut.model_validate(row)


def work_order_response(row: MaintenanceWorkOrder) -> WorkOrderOut:
    """Convert a work-order row to its API response."""
    return WorkOrderOut.model_validate(row)


__all__ = [
    "AssetDetailOut",
    "AssetFilters",
    "AssetOut",
    "DataQualityResultOut",
    "FailureFilters",
    "FailureOut",
    "IngestionDatasetResultOut",
    "IngestionRunOut",
    "Page",
    "TelemetryFilters",
    "TelemetryOut",
    "WorkOrderFilters",
    "WorkOrderOut",
]
