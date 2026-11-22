"""CLI entrypoint for synthetic data generation and validation.

Usage:
    python scripts/generate_synthetic_data.py [--output DIR]

Writes CSVs to ``data/generated`` by default and validates every table.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data_engineering.generators.config import TABLES  # noqa: E402
from data_engineering.generators.generate_all import generate_all  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and validate synthetic utility data.")
    parser.add_argument("--output", type=Path, default=None, help="Output directory (default: data/generated)")
    args = parser.parse_args()

    manifest = generate_all(args.output)
    print(f"Output directory: {Path(manifest['files']['transformers']['path']).parent}")
    print("Counts:")
    for name in TABLES:
        print(f"  {name}: {manifest['counts'][name]} rows")
    print("Validation summary:")
    errors = 0
    for table in sorted(manifest["validation"]):
        summary = manifest["validation"][table]
        print(
            f"  {table}: ok={summary['ok']} errors={summary['errors']} "
            f"missing_fields={summary['missing_fields']} duplicates={summary['duplicates']} "
            f"completeness={summary['completeness']}"
        )
        errors += summary["errors"]
    print(f"Synthetic: {manifest['synthetic']}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
