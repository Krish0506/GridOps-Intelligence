"""API integration tests for the read-only GridOps Intelligence endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(api_client: TestClient) -> None:
    """The health endpoint responds while the API test client is active."""
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "gridops-api"}


def test_assets_list_is_paginated(api_client, ingested_db) -> None:
    """Asset listing returns a paginated page of the full asset set."""
    response = api_client.get("/api/v1/assets", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2600
    assert len(payload["items"]) == 5
    assert payload["limit"] == 5
    assert payload["offset"] == 0

    second_page = api_client.get("/api/v1/assets", params={"limit": 5, "offset": 5})
    assert second_page.status_code == 200
    assert second_page.json()["offset"] == 5


def test_assets_filter_by_type(api_client, ingested_db) -> None:
    """Asset listing can filter by asset type."""
    response = api_client.get("/api/v1/assets", params={"asset_type": "transformers", "limit": 100})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] > 0
    assert all(item["asset_type"] == "transformers" for item in payload["items"])


def test_asset_detail_includes_transformer_detail(api_client, ingested_db) -> None:
    """Asset detail returns the base asset plus its type-specific detail."""
    response = api_client.get("/api/v1/assets/T-00001")
    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == "T-00001"
    assert body["synthetic"] is True
    assert body["transformer_detail"] is not None
    assert body["transformer_detail"]["asset_id"] == "T-00001"


def test_asset_detail_not_found(api_client) -> None:
    """Asset detail returns a structured 404 for unknown identifiers."""
    response = api_client.get("/api/v1/assets/NOPE-99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "asset not found"


def test_telemetry_list_for_asset(api_client, ingested_db) -> None:
    """Telemetry retrieval returns readings for a known asset."""
    response = api_client.get("/api/v1/telemetry/T-00001", params={"limit": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] > 0
    assert len(payload["items"]) == 3
    assert payload["items"][0]["asset_id"] == "T-00001"
    assert "telemetry_id" in payload["items"][0]

    missing = api_client.get("/api/v1/telemetry/NOPE-99999")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "asset not found"


def test_failures_list(api_client, ingested_db) -> None:
    """Failure listing returns the ingested failure set with pagination."""
    response = api_client.get("/api/v1/failures", params={"limit": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 60
    assert len(payload["items"]) == 10
    assert payload["items"][0]["failure_id"].startswith("FAIL-")


def test_work_orders_list(api_client, ingested_db) -> None:
    """Work-order listing returns the ingested work-order set with pagination."""
    response = api_client.get("/api/v1/work-orders", params={"limit": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1528
    assert len(payload["items"]) == 10
    assert payload["items"][0]["work_order_id"].startswith("WO-")


def test_ingestion_runs_list_and_detail(api_client, ingested_db) -> None:
    """Ingestion run listing and detail expose persisted run and quality results."""
    listing = api_client.get("/api/v1/ingestion/runs", params={"limit": 5})
    assert listing.status_code == 200
    listing_payload = listing.json()
    assert listing_payload["total"] >= 1
    assert len(listing_payload["items"]) == 1

    detail_response = api_client.get("/api/v1/ingestion/runs", params={"limit": 1})
    assert detail_response.status_code == 200
    run_id = detail_response.json()["items"][0]["run_id"]
    detail = api_client.get(f"/api/v1/ingestion/runs/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["run_id"] == run_id
    assert body["status"] == "completed"
    assert len(body["dataset_results"]) == 9
    assert len(body["quality_results"]) >= 1
