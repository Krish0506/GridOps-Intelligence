"""Asset-aware evidence integration (Milestone 4)."""

from __future__ import annotations

from typing import Any


def asset_context(asset_id: str, risk_record: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a lightweight asset context for evidence queries."""
    equipment = None
    if asset_id.startswith("T-"):
        equipment = "transformers"
    elif asset_id.startswith("S-"):
        equipment = "substations"
    elif asset_id.startswith("CB-"):
        equipment = "circuit_breakers"
    elif asset_id.startswith("F-"):
        equipment = "feeders"
    context: dict[str, Any] = {"asset_id": asset_id, "equipment_type": equipment}
    if risk_record:
        context["risk_category"] = risk_record.get("risk_category")
        context["anomaly_score"] = risk_record.get("anomaly_score")
        context["model_probability"] = risk_record.get("model_probability")
    return context


def equipment_filter_for_asset(asset_id: str) -> str | None:
    """Return an equipment filter string for retrieval, or None."""
    if asset_id.startswith("T-"):
        return "transformers"
    if asset_id.startswith("S-"):
        return "substations"
    if asset_id.startswith("CB-"):
        return "circuit_breakers"
    if asset_id.startswith("F-"):
        return "feeders"
    return None


__all__ = ["asset_context", "equipment_filter_for_asset"]
