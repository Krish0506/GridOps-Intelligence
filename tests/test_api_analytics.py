"""Integration tests for the analytics, risk, and governance API surfaces."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.app.models import RiskRecord

CUTOFF = datetime(2026, 1, 2, tzinfo=timezone.utc)


@pytest.fixture
def seeded_risks(db_session, ingested_db):
    """Replace the derived risk workspace with a deterministic three-asset sample."""
    db_session.execute(delete(RiskRecord))
    db_session.add_all(
        [
            RiskRecord(
                asset_id="T-00001",
                asset_type="transformers",
                prediction_cutoff=CUTOFF,
                risk_category="predicted_failure",
                anomaly_score=42.5,
                model_probability=0.997,
                data_quality={"telemetry_coverage_ratio": 0.9},
                primary_drivers=["telemetry_load_pct_trend_per_day"],
                model_version="logistic_regression@test",
                limitations=["Synthetic evaluation only."],
            ),
            RiskRecord(
                asset_id="T-00002",
                asset_type="transformers",
                prediction_cutoff=CUTOFF,
                risk_category="predicted_no_failure",
                anomaly_score=2.5,
                model_probability=0.08,
                data_quality={"telemetry_coverage_ratio": 0.8},
                primary_drivers=["telemetry_temperature_c_mean"],
                model_version="logistic_regression@test",
                limitations=["Synthetic evaluation only."],
            ),
            RiskRecord(
                asset_id="CB-00001",
                asset_type="circuit_breakers",
                prediction_cutoff=CUTOFF,
                risk_category="predicted_failure",
                anomaly_score=18.0,
                model_probability=0.91,
                data_quality={"telemetry_coverage_ratio": 1.0},
                primary_drivers=["telemetry_current_a_trend_per_day"],
                model_version="logistic_regression@test",
                limitations=["Synthetic evaluation only."],
            ),
        ]
    )
    db_session.commit()
    yield
    db_session.execute(delete(RiskRecord))
    db_session.commit()


def test_overview_is_database_derived(api_client: TestClient, ingested_db) -> None:
    response = api_client.get("/api/v1/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["assets"]["total"] == 2600
    assert body["failures"]["total"] == 60
    assert body["work_orders"]["active_total"] > 0
    assert body["knowledge"]["documents"] >= 0
    assert "risks" in body and "by_priority" in body["risks"]
    assert body["model"]["available"] is True
    assert body["synthetic"] is True


def test_predictive_returns_persisted_artifacts(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/predictive")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["preferred_model"]["available"] is True
    assert body["preferred_model"]["validation_metrics"] is not None
    assert body["preferred_model"]["test_metrics"] is not None
    assert "artifact_path" in body["preferred_model"]
    assert body["synthetic_warning"]


def test_risk_summary_and_ranking(api_client: TestClient, seeded_risks) -> None:
    summary = api_client.get("/api/v1/risk/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["total"] == 3
    assert sum(body["by_priority"].values()) == 3
    assert body["by_category"]["predicted_failure"] == 2
    assert body["model_versions"] == ["logistic_regression@test"]
    assert body["data_quality_warning_count"] >= 0
    assert "P1" in body["filter_options"]["priorities"]

    listing = api_client.get("/api/v1/risk", params={"limit": 10})
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["total"] == 3
    assert len(payload["items"]) == 3
    ranks = [item["rank"] for item in payload["items"]]
    assert ranks == sorted(ranks)
    assert all(item["review_priority"].startswith("P") for item in payload["items"])


def test_risk_filters_search_and_sort(api_client: TestClient, seeded_risks) -> None:
    filtered = api_client.get("/api/v1/risk", params={"asset_type": "transformers"})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 2
    assert all(item["asset_type"] == "transformers" for item in filtered.json()["items"])

    searched = api_client.get("/api/v1/risk", params={"search": "CB-00001"})
    assert searched.status_code == 200
    assert searched.json()["total"] == 1
    assert searched.json()["items"][0]["asset_id"] == "CB-00001"

    descending = api_client.get(
        "/api/v1/risk", params={"sort": "model_probability", "direction": "desc"}
    )
    probabilities = [item["model_probability"] for item in descending.json()["items"]]
    assert probabilities == sorted(probabilities, reverse=True)


def test_risk_detail_includes_explanation(api_client: TestClient, seeded_risks) -> None:
    response = api_client.get("/api/v1/risk/T-00001")
    assert response.status_code == 200
    body = response.json()
    assert body["item"]["asset_id"] == "T-00001"
    assert body["item"]["criticality"]["tier"] in {"low", "medium", "high", "critical"}
    explanation = body["explanation"]
    assert explanation is not None
    if not explanation.get("unavailable"):
        assert explanation["asset_id"] == "T-00001"
        assert explanation["methodology"]["deviation"]

    missing = api_client.get("/api/v1/risk/NOPE-99999")
    assert missing.status_code == 404


def test_governance_reports_lineage_and_limitations(api_client: TestClient, seeded_risks) -> None:
    response = api_client.get("/api/v1/governance")
    assert response.status_code == 200
    body = response.json()
    assert body["database"]["alembic_revision"]
    assert body["datasets"]["assets"] == 2600
    assert body["datasets"]["risk_records"] == 3
    assert body["risk_generation"]["records"] == 3
    assert body["knowledge"]["documents"] >= 0
    assert body["data_quality"]["checks"] >= 1
    assert len(body["limitations"]) >= 3
    assert body["synthetic"] is True


def test_asset_search_sorting_and_filter_options(api_client: TestClient, ingested_db) -> None:
    response = api_client.get(
        "/api/v1/assets",
        params={"search": "T-0000", "sort_by": "asset_id", "sort_dir": "desc", "limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 9
    identifiers = [item["asset_id"] for item in body["items"]]
    assert identifiers == sorted(identifiers, reverse=True)
    assert all("T-0000" in identifier for identifier in identifiers)

    options = api_client.get("/api/v1/assets/filters")
    assert options.status_code == 200
    payload = options.json()
    assert {entry["value"] for entry in payload["asset_types"]} == {
        "transformers",
        "substations",
        "circuit_breakers",
        "feeders",
    }
    assert len(payload["statuses"]) >= 1
    assert len(payload["regions"]) >= 1


def test_knowledge_stats_and_document_filters(api_client: TestClient) -> None:
    stats = api_client.get("/api/v1/knowledge/stats")
    assert stats.status_code == 200
    body = stats.json()
    assert isinstance(body["documents"], int)
    assert isinstance(body["chunks"], int)
    assert isinstance(body["categories"], list)
    assert isinstance(body["equipment"], list)
    assert all("equipment" in entry and "documents" in entry for entry in body["equipment"])
    assert body["synthetic"] is True

    filtered = api_client.get("/api/v1/knowledge/documents", params={"equipment": "transformers"})
    assert filtered.status_code == 200
    assert isinstance(filtered.json(), list)
