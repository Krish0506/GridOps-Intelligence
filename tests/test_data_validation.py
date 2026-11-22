"""Unit tests for the data-validation helpers."""

from __future__ import annotations

from datetime import datetime

from data_engineering.generators.validation import (
    check_asset_references,
    check_categories,
    check_completed_required,
    check_duplicates,
    check_identifiers,
    check_numeric_ranges,
    check_required_fields,
    check_synthetic,
    check_timestamps,
    check_work_order_dates,
)


def test_check_required_fields_flags_empty_values():
    rows = [{"asset_id": "", "name": "X"}, {"asset_id": "T-00001", "name": ""}]
    issues, affected = check_required_fields(rows, ["asset_id", "name"], "transformers")
    assert {(issue.field, issue.row_index) for issue in issues} == {("asset_id", 0), ("name", 1)}
    assert all(issue.severity == "missing" for issue in issues)
    assert affected == {0, 1}


def test_check_identifiers_rejects_invalid_and_duplicate():
    rows = [{"id": "T-00001"}, {"id": "T-00001"}, {"id": "BAD"}, {"id": ""}]
    errors, duplicates = check_identifiers(rows, "id", "transformers")
    assert any("invalid identifier" in issue.message for issue in errors)
    assert any("'id' is empty" in issue.message for issue in errors)
    assert len(duplicates) == 1
    assert all(issue.severity == "duplicate" for issue in duplicates)


def test_check_timestamps_rejects_invalid_and_future():
    rows = [{"ts": "not-a-timestamp"}, {"ts": "2030-01-01T00:00:00"}]
    errors = check_timestamps(rows, ["ts"], "test", max_date=datetime(2026, 12, 1))
    assert len(errors) == 2
    assert all(issue.severity == "error" for issue in errors)


def test_check_numeric_ranges_rejects_non_numeric_and_out_of_range():
    rows = [{"value": "abc"}, {"value": "-1"}, {"value": "42"}]
    errors = check_numeric_ranges(rows, {"value": (0, 50)}, "test")
    assert len(errors) == 2
    assert any("non-numeric" in issue.message for issue in errors)
    assert any("out of range" in issue.message for issue in errors)


def test_check_categories_rejects_unexpected_values():
    rows = [{"status": "active"}, {"status": "retired"}, {"status": "weird"}]
    errors = check_categories(rows, "status", {"active", "retired"}, "test")
    assert len(errors) == 1
    assert "unexpected category" in errors[0].message


def test_check_asset_references_rejects_broken_references():
    rows = [{"asset_ref": "T-00001"}, {"asset_ref": "T-99999"}, {"asset_ref": ""}]
    errors = check_asset_references(rows, {"T-00001"}, "asset_ref", "test")
    assert len(errors) == 2


def test_check_duplicates_detects_exact_duplicates():
    rows = [{"a": "1"}, {"a": "1"}, {"a": "2"}, {"a": "2"}]
    duplicates = check_duplicates(rows, "test")
    assert len(duplicates) == 2
    assert all(issue.severity == "duplicate" for issue in duplicates)


def test_check_synthetic_requires_true_marker():
    assert check_synthetic([{"synthetic": "true"}], "test") == []
    assert len(check_synthetic([{"synthetic": "false"}], "test")) == 1


def test_check_completed_required_flags_completed_without_completion():
    rows = [
        {"status": "completed", "completed_at": ""},
        {"status": "completed", "completed_at": "2026-01-01T00:00:00"},
    ]
    issues = check_completed_required(rows, "work_orders")
    assert len(issues) == 1
    assert issues[0].field == "completed_at"


def test_check_work_order_dates_rejects_completed_before_opened():
    rows = [{"opened_at": "2026-05-01T00:00:00", "completed_at": "2026-04-01T00:00:00"}]
    errors = check_work_order_dates(rows, "work_orders")
    assert len(errors) == 1
