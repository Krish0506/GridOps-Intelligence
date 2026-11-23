"""Command-line workflows for GridOps Intelligence synthetic evaluation (Milestone 3)."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from data_engineering.generators.base import load_rows
from data_engineering.generators.config import REFERENCE_DATE
from data_engineering.generators.independent_evaluation import (
    IndependentEvaluationParams,
    build_independent_feature_snapshots,
    generate_independent_evaluation,
)
from ml.anomaly import asset_anomaly_score, fit_robust_baseline, robust_z_scores
from ml.artifacts.registry import load_model, save_model
from ml.data import (
    MINIMUM_CONFIRMED_NEGATIVES,
    MINIMUM_CONFIRMED_POSITIVES,
    assess_readiness,
    confirmed_healthy_until_for_snapshots,
)
from ml.data.cohort import build_modeling_dataset
from ml.data.readiness import DataReadinessReport
from ml.evaluation.metrics import classification_metrics
from ml.features.labels import classify_outcomes
from ml.features.types import failure_from_mapping
from ml.pipelines.inference import predict_positive_probability
from ml.pipelines.train import train_baseline
from ml.risk.prioritization import build_risk_records


def _evaluation_context(args: argparse.Namespace) -> tuple[IndependentEvaluationParams, Path, datetime, datetime]:
    params = IndependentEvaluationParams(
        seed=getattr(args, "seed", 20261122),
        asset_count=getattr(args, "asset_count", 1500),
        observation_days=getattr(args, "observation_days", 365),
        horizon_days=getattr(args, "horizon_days", 90),
        failure_prevalence=getattr(args, "failure_prevalence", 0.12),
    )
    cutoff = REFERENCE_DATE - timedelta(days=params.observation_days)
    horizon_end = cutoff + timedelta(days=params.horizon_days)
    return params, Path(args.output), cutoff, horizon_end


def _label_distribution(manifest: dict) -> dict:
    distribution = manifest.get("label_distribution") or {}
    return {
        "confirmed_positive": int(distribution.get("confirmed_positive") or 0),
        "confirmed_negative": int(distribution.get("confirmed_negative") or 0),
        "unknown": int(distribution.get("unknown") or 0),
        "total": int(distribution.get("total") or 0),
    }


def _readiness_from_manifest(manifest: dict, args: argparse.Namespace) -> DataReadinessReport:
    label_distribution = _label_distribution(manifest)
    return assess_readiness(
        dataset_name=str(manifest.get("name") or "gridops-independent-synthetic-evaluation"),
        generator=str(manifest.get("generator") or "data_engineering.generators.independent_evaluation"),
        seed=int(manifest.get("seed") or 0),
        asset_count=int(manifest.get("total_assets") or 0),
        snapshot_count=int(manifest.get("total_assets") or 0),
        prediction_cutoff=datetime.fromisoformat(str(manifest.get("prediction_cutoff") or "")),
        horizon_end=datetime.fromisoformat(str(manifest.get("horizon_end") or "")),
        confirmed_positive=label_distribution["confirmed_positive"],
        confirmed_negative=label_distribution["confirmed_negative"],
        unknown=label_distribution["unknown"],
        min_confirmed_positives=args.min_confirmed_positives,
        min_confirmed_negatives=args.min_confirmed_negatives,
    )


def run_generate_evaluation(args: argparse.Namespace) -> int:
    manifest = generate_independent_evaluation(
        args.output,
        params=IndependentEvaluationParams(
            seed=args.seed,
            asset_count=args.asset_count,
            observation_days=args.observation_days,
            horizon_days=args.horizon_days,
            failure_prevalence=args.failure_prevalence,
        ),
    )
    print(f"Output directory: {args.output}")
    print(f"Seed: {manifest['seed']}")
    print(f"Counts: {manifest['counts']}")
    print(f"Label distribution: {manifest['label_distribution']}")
    return 0


def run_assess_readiness(args: argparse.Namespace) -> int:
    params, directory, cutoff, horizon_end = _evaluation_context(args)
    manifest = generate_independent_evaluation(directory, params=params)
    report = _readiness_from_manifest(manifest, args)
    print(report)
    return 0 if report.ready else 2


def run_build_snapshots(args: argparse.Namespace) -> int:
    _params, directory, cutoff, _horizon = _evaluation_context(args)
    snapshots = build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)
    print(f"Snapshots built: {len(snapshots)}")
    return 0


def run_train(args: argparse.Namespace) -> int:
    params, directory, cutoff, horizon_end = _evaluation_context(args)
    manifest = generate_independent_evaluation(directory, params=params)
    report = _readiness_from_manifest(manifest, args)
    if not report.ready:
        print("Training blocked: data readiness requirements not met.")
        print(report.reasons)
        return 3
    failures = []
    for row in load_rows(directory / "failures.csv"):
        mapped = dict(row)
        mapped["asset_id"] = mapped.get("asset_ref") or ""
        failures.append(failure_from_mapping(mapped))
    snapshots = build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)
    failed_asset_ids = {failure.asset_id for failure in failures}
    confirmed = confirmed_healthy_until_for_snapshots(
        snapshots, cutoff, params.observation_days, horizon_end, failed_asset_ids
    )
    decisions = classify_outcomes(
        failures,
        [str(s.get("asset_id")) for s in snapshots],
        cutoff,
        horizon_end,
        confirmed_healthy_until=confirmed,
    )
    dataset = build_modeling_dataset(snapshots, decisions)
    trained = train_baseline(dataset, args.model, seed=args.seed)
    path = save_model(trained, Path("ml/artifacts/models"))
    print(f"Trained {trained.model_name} with validation metrics {trained.metrics}")
    print(f"Final test metrics {trained.test_metrics}")
    print(f"Threshold tuned on validation: {trained.threshold}")
    print(f"Saved artifact: {path}")
    return 0


def run_evaluate(args: argparse.Namespace) -> int:
    candidate = Path("ml/artifacts/models") / f"{args.model}.pkl"
    if not candidate.exists():
        print(f"No trained artifact found for model '{args.model}' at {candidate}")
        return 4
    loaded = load_model(candidate)
    _params, directory, cutoff, horizon_end = _evaluation_context(args)
    snapshots = build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)
    failures = []
    for row in load_rows(directory / "failures.csv"):
        mapped = dict(row)
        mapped["asset_id"] = mapped.get("asset_ref") or ""
        failures.append(failure_from_mapping(mapped))
    decisions = classify_outcomes(
        failures,
        [str(s.get("asset_id")) for s in snapshots],
        cutoff,
        horizon_end,
        confirmed_healthy_until=confirmed_healthy_until_for_snapshots(
            snapshots, cutoff, _params.observation_days, horizon_end, {f.asset_id for f in failures}
        ),
    )
    predictions = [(str(s.get("asset_id")), predict_positive_probability(loaded, s)) for s in snapshots]
    y_true = []
    for asset_id, _proba in predictions:
        decision = next((d for d in decisions if d.asset_id == asset_id), None)
        y_true.append(1 if decision is not None and decision.label.value == "confirmed_positive" else 0)
    metrics = classification_metrics(y_true, [proba for _asset_id, proba in predictions])
    print(metrics)
    return 0


def run_anomaly(args: argparse.Namespace) -> int:
    _params, directory, cutoff, _horizon = _evaluation_context(args)
    snapshots = build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)
    medians, mads = fit_robust_baseline(snapshots)
    z_scores = robust_z_scores(snapshots, medians, mads)
    scores = [max(z.values()) for z in z_scores]
    top = sorted(range(len(snapshots)), key=lambda i: scores[i])[: max(0, args.top_n)]
    print({"anomaly_scores": scores, "top_n": top})
    return 0


def run_risk(args: argparse.Namespace) -> int:
    _params, directory, cutoff, _horizon = _evaluation_context(args)
    snapshots = build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)
    medians, mads = fit_robust_baseline(snapshots)
    records = build_risk_records(
        snapshots=snapshots,
        model_probabilities=None,
        model_version=None,
        prediction_cutoff=cutoff,
        medians=medians,
        mads=mads,
    )
    print({"risk_records": len(records)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GridOps Intelligence Milestone 3 CLI workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_generate = subparsers.add_parser("generate-evaluation", help="Generate the independent evaluation dataset.")
    p_generate.add_argument("--output", default="data/evaluation")
    p_generate.add_argument("--seed", type=int, default=20261122)
    p_generate.add_argument("--asset-count", type=int, default=1500)
    p_generate.add_argument("--observation-days", type=int, default=365)
    p_generate.add_argument("--horizon-days", type=int, default=90)
    p_generate.add_argument("--failure-prevalence", type=float, default=0.12)
    p_generate.set_defaults(func=run_generate_evaluation)

    p_readiness = subparsers.add_parser("assess-readiness", help="Assess data readiness for classification.")
    p_readiness.add_argument("--output", default="data/evaluation")
    p_readiness.add_argument("--seed", type=int, default=20261122)
    p_readiness.add_argument("--asset-count", type=int, default=1500)
    p_readiness.add_argument("--observation-days", type=int, default=365)
    p_readiness.add_argument("--horizon-days", type=int, default=90)
    p_readiness.add_argument("--failure-prevalence", type=float, default=0.12)
    p_readiness.add_argument("--min-confirmed-positives", type=int, default=MINIMUM_CONFIRMED_POSITIVES)
    p_readiness.add_argument("--min-confirmed-negatives", type=int, default=MINIMUM_CONFIRMED_NEGATIVES)
    p_readiness.set_defaults(func=run_assess_readiness)

    p_snapshots = subparsers.add_parser("build-snapshots", help="Build feature snapshots from generated data.")
    p_snapshots.add_argument("--output", default="data/evaluation")
    p_snapshots.add_argument("--observation-days", type=int, default=365)
    p_snapshots.set_defaults(func=run_build_snapshots)

    p_train = subparsers.add_parser("train", help="Train a baseline model when data readiness permits.")
    p_train.add_argument("--output", default="data/evaluation")
    p_train.add_argument("--seed", type=int, default=20261122)
    p_train.add_argument("--asset-count", type=int, default=1500)
    p_train.add_argument("--observation-days", type=int, default=365)
    p_train.add_argument("--horizon-days", type=int, default=90)
    p_train.add_argument("--failure-prevalence", type=float, default=0.12)
    p_train.add_argument("--model", default="logistic_regression")
    p_train.add_argument("--min-confirmed-positives", type=int, default=MINIMUM_CONFIRMED_POSITIVES)
    p_train.add_argument("--min-confirmed-negatives", type=int, default=MINIMUM_CONFIRMED_NEGATIVES)
    p_train.set_defaults(func=run_train)

    p_eval = subparsers.add_parser("evaluate", help="Evaluate a trained baseline model on generated snapshots.")
    p_eval.add_argument("--output", default="data/evaluation")
    p_eval.add_argument("--model", default="logistic_regression")
    p_eval.add_argument("--observation-days", type=int, default=365)
    p_eval.set_defaults(func=run_evaluate)

    p_anomaly = subparsers.add_parser("anomaly", help="Run anomaly detection over feature snapshots.")
    p_anomaly.add_argument("--output", default="data/evaluation")
    p_anomaly.add_argument("--observation-days", type=int, default=365)
    p_anomaly.add_argument("--top-n", type=int, default=10)
    p_anomaly.set_defaults(func=run_anomaly)

    p_risk = subparsers.add_parser("risk", help="Build operational risk prioritization records.")
    p_risk.add_argument("--output", default="data/evaluation")
    p_risk.add_argument("--observation-days", type=int, default=365)
    p_risk.set_defaults(func=run_risk)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
