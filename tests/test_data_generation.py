"""Tests for the synthetic utility data generation pipeline."""

from __future__ import annotations

import csv

import pytest

from data_engineering.generators.base import load_rows
from data_engineering.generators.config import (
    ASSET_ID_FIELDS,
    ASSET_TABLES,
    DEFAULT_SEED,
    OUTPUT_DIR,
    TABLES,
    TABLE_FIELDNAMES,
)
from data_engineering.generators.generate_all import generate_all
from data_engineering.generators.validation import validate_all


@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> dict:
    """Generate a full synthetic dataset once per test module."""
    directory = tmp_path_factory.mktemp("synthetic-data")
    manifest = generate_all(directory)
    return {"directory": directory, "manifest": manifest}


def test_expected_files_created(generated):
    directory = generated["directory"]
    for table in TABLES:
        assert (directory / f"{table}.csv").is_file(), f"missing {table}.csv"
    assert (directory / "synthetic_manifest.json").is_file()


def test_at_least_1000_assets(generated):
    counts = generated["manifest"]["counts"]
    total = sum(counts[table] for table in ASSET_TABLES)
    assert total >= 1000
    assert generated["manifest"]["total_assets"] == total


def test_csv_headers_match_schema(generated):
    for table in TABLES:
        with open(generated["directory"] / f"{table}.csv", newline="") as handle:
            assert next(csv.reader(handle)) == TABLE_FIELDNAMES[table]


def test_every_record_marked_synthetic(generated):
    for table in TABLES:
        for row in load_rows(generated["directory"] / f"{table}.csv"):
            assert row["synthetic"] == "true", f"{table} row is not marked synthetic"


def test_failure_references_are_valid(generated):
    asset_index = set()
    for table in ASSET_TABLES:
        id_field = ASSET_ID_FIELDS[table]
        for row in load_rows(generated["directory"] / f"{table}.csv"):
            if row[id_field]:
                asset_index.add(row[id_field])
    for row in load_rows(generated["directory"] / "failures.csv"):
        assert row["asset_ref"] in asset_index


def test_controlled_missing_values_present(generated):
    telemetry = load_rows(generated["directory"] / "asset_telemetry.csv")
    assert telemetry
    assert any(not str(row["temperature_c"]).strip() for row in telemetry)


def test_duplicate_records_present(generated):
    for table in ["asset_telemetry", "work_orders", "inspections", "weather"]:
        rows = load_rows(generated["directory"] / f"{table}.csv")
        keys = {tuple(sorted(row.items())) for row in rows}
        assert len(keys) < len(rows), f"expected duplicate records in {table}.csv"


def test_validation_passes_on_generated_data(generated):
    results = validate_all(generated["directory"])
    for table, result in results.items():
        assert result.ok, f"{table}: {[issue.describe() for issue in result.errors[:10]]}"
        assert result.completeness >= 0.95
        assert result.row_count > 0


def test_generation_is_deterministic(tmp_path):
    generate_all(tmp_path / "run1")
    generate_all(tmp_path / "run2")
    for table in TABLES:
        first = (tmp_path / "run1" / f"{table}.csv").read_bytes()
        second = (tmp_path / "run2" / f"{table}.csv").read_bytes()
        assert first == second, f"non-deterministic output for {table}.csv"


def test_generated_output_dir_is_valid():
    """The committed output directory (data/generated) is valid."""
    manifest = generate_all(OUTPUT_DIR)
    assert manifest["seed"] == DEFAULT_SEED
    assert manifest["total_assets"] >= 1000
    results = validate_all(OUTPUT_DIR)
    for table, result in results.items():
        assert result.ok, f"{table}: {[issue.describe() for issue in result.errors[:10]]}"
