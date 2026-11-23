"""Tests for the Milestone 3 CLI (pure, small fixtures)."""

from __future__ import annotations

from data_engineering.cli import build_parser


def test_build_parser_requires_command() -> None:
    parser = build_parser()
    with __import__("pytest").raises(SystemExit):
        parser.parse_args([])


def test_build_parser_accepts_assess_readiness() -> None:
    parser = build_parser()
    args = parser.parse_args(["assess-readiness", "--output", "tmp", "--asset-count", "16"])
    assert args.command == "assess-readiness"
    assert args.asset_count == 16
