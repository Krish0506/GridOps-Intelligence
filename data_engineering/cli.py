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


OPERATIONAL_RISK_LIMITATIONS = [
    "Synthetic demonstration data; not real utility asset condition or failure history.",
    "The model probability is a classifier output on synthetic data, not a calibrated field failure probability.",
    "The anomaly score is an unsupervised deviation magnitude and must not be read as a failure probability.",
    "Review priority is a transparent triage band over probability and anomaly percentiles plus asset criticality.",
    "Model inference is a batch snapshot at the prediction cutoff; the system does not retrain automatically.",
]


def _persist_operational_risk(session, records, *, batch_size: int = 500) -> int:
    """Replace the derived risk workspace in one transaction.

    Risk records are derived artifacts, so a full rebuild is idempotent: every
    run writes exactly one record per operational asset at the prediction
    cutoff.  No source fact table is touched.
    """
    from backend.app.models import RiskRecord as RiskRecordModel

    session.query(RiskRecordModel).delete(synchronize_session=False)
    for start in range(0, len(records), batch_size):
        for record in records[start : start + batch_size]:
            session.add(
                RiskRecordModel(
                    asset_id=record.asset_id,
                    asset_type=record.asset_type,
                    prediction_cutoff=record.prediction_cutoff,
                    risk_category=record.risk_category,
                    anomaly_score=record.anomaly_score,
                    model_probability=record.model_probability,
                    data_quality=record.data_quality,
                    primary_drivers=record.primary_drivers,
                    model_version=record.model_version,
                    limitations=record.limitations,
                )
            )
        session.flush()
    session.commit()
    return len(records)


def run_operational_risk(args: argparse.Namespace) -> int:
    """Build risk records for the operational assets using the trained model.

    Unlike ``risk`` (which scores the independent evaluation cohort), this
    workflow loads the live asset dimension from PostgreSQL, builds
    leakage-safe feature snapshots at the reference cutoff, applies the
    persisted classifier, fits the population anomaly baseline, persists that
    baseline artifact, and optionally writes the risk workspace.
    """
    import json
    from datetime import timezone

    from backend.app.database import get_db
    from backend.app.settings import (
        DEFAULT_MODEL_NAME,
        EXPLAINABILITY_DIR,
        MODEL_DIR,
        artifact_version,
        model_artifact_path,
        safe_artifact_reference,
    )
    from ml.features.repository import (
        build_feature_records_for_assets,
        load_assets,
        load_failures,
    )
    from ml.risk.prioritization import build_risk_records

    session = next(get_db())
    try:
        model_name = getattr(args, "model", DEFAULT_MODEL_NAME)
        artifact = model_artifact_path(model_name)
        if not artifact.exists():
            print(
                f"No trained model artifact at {safe_artifact_reference(artifact)}. "
                "Run: python -m data_engineering.cli train --model logistic_regression"
            )
            return 4
        model = load_model(artifact)
        cutoff = REFERENCE_DATE
        assets = load_assets(session)
        if not assets:
            print("No operational assets found. Run the data ingestion pipeline first.")
            return 5
        asset_ids = [asset.asset_id for asset in assets]
        failures = load_failures(session)
        first_failure: dict[str, datetime] = {}
        for failure in failures:
            if failure.failure_timestamp < cutoff:
                first_failure.setdefault(failure.asset_id, failure.failure_timestamp)

        print(f"Building feature snapshots for {len(asset_ids)} assets at {cutoff.isoformat()} ...")
        snapshots = build_feature_records_for_assets(
            session,
            asset_ids,
            cutoff,
            exclude_at_or_after=first_failure or None,
        )
        if not snapshots:
            print("No feature snapshots could be built.")
            return 6
        print(f"Built {len(snapshots)} snapshots; fitting population anomaly baseline ...")
        medians, mads = fit_robust_baseline(snapshots)
        probabilities = {
            str(snapshot.get("asset_id") or ""): predict_positive_probability(model, snapshot)
            for snapshot in snapshots
        }
        version = artifact_version(model_name)
        records = build_risk_records(
            snapshots=snapshots,
            model_probabilities=probabilities,
            model_version=version,
            prediction_cutoff=cutoff,
            medians=medians,
            mads=mads,
            limitations=OPERATIONAL_RISK_LIMITATIONS,
        )

        EXPLAINABILITY_DIR.mkdir(parents=True, exist_ok=True)
        baseline_path = EXPLAINABILITY_DIR / "baseline.json"
        baseline = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "prediction_cutoff": cutoff.isoformat(),
            "asset_count": len(snapshots),
            "model_name": model_name,
            "model_version": version,
            "z_cap": 50.0,
            "medians": medians,
            "scales": mads,
            "feature_count": len(medians),
            "methodology": (
                "Population median and robust scale (MAD with IQR and standard-deviation "
                "fallbacks plus a feature-scale floor) fitted on the operational synthetic "
                "asset snapshots at the prediction cutoff."
            ),
            "artifact": safe_artifact_reference(baseline_path),
        }
        baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        print(f"Baseline artifact: {safe_artifact_reference(baseline_path)}")

        # Refresh model metadata with the fields the API reports, without
        # retraining or replacing the pickle artifact.
        metadata_path = MODEL_DIR / f"{model_name}.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            metadata = {}
        metadata.update(
            {
                "model_name": model_name,
                "model_version": version,
                "threshold": float(getattr(model, "threshold", 0.5)),
                "metrics": getattr(model, "metrics", {}) or metadata.get("metrics"),
                "test_metrics": getattr(model, "test_metrics", {}) or metadata.get("test_metrics"),
                "positive_count": getattr(model, "positive_count", metadata.get("positive_count")),
                "negative_count": getattr(model, "negative_count", metadata.get("negative_count")),
                "train_assets": len(getattr(model, "train_asset_ids", []) or []),
                "validation_assets": len(getattr(model, "validation_asset_ids", []) or []),
                "test_assets": len(getattr(model, "test_asset_ids", []) or []),
                "metadata_refreshed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        if getattr(args, "persist", False):
            persisted = _persist_operational_risk(session, records)
            print(f"Persisted {persisted} risk records at {cutoff.isoformat()}.")
        else:
            print(
                {
                    "risk_records": len(records),
                    "predicted_failure": sum(
                        1 for record in records if record.risk_category == "predicted_failure"
                    ),
                    "model_version": version,
                }
            )
        return 0
    finally:
        session.close()


def run_risk(args: argparse.Namespace) -> int:
    """Score the independent evaluation cohort (legacy Milestone 3 workflow)."""
    from backend.app.database import get_db
    from ml.risk.prioritization import build_risk_records

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
        limitations=["Evaluation-cohort records have no operational asset identity."],
    )
    if getattr(args, "persist", False):
        session = next(get_db())
        try:
            _persist_operational_risk(session, records)
        finally:
            session.close()
        print(f"Persisted {len(records)} evaluation risk records.")
    else:
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

    p_risk = subparsers.add_parser("risk", help="Build risk records for the independent evaluation cohort.")
    p_risk.add_argument("--output", default="data/evaluation")
    p_risk.add_argument("--observation-days", type=int, default=365)
    p_risk.add_argument("--persist", action="store_true", help="Persist risk records to the database.")
    p_risk.set_defaults(func=run_risk)

    p_operational_risk = subparsers.add_parser(
        "operational-risk",
        help="Score operational assets with the persisted model and persist the risk workspace.",
    )
    p_operational_risk.add_argument("--model", default="logistic_regression")
    p_operational_risk.add_argument("--persist", action="store_true", help="Write risk records to PostgreSQL.")
    p_operational_risk.set_defaults(func=run_operational_risk)

    p_list_decisions = subparsers.add_parser("list-pending-decisions", help="List pending engineering decisions.")
    p_list_decisions.set_defaults(func=run_list_pending_decisions)

    p_get_decision = subparsers.add_parser("get-decision", help="Retrieve an engineering decision.")
    p_get_decision.add_argument("decision_id")
    p_get_decision.set_defaults(func=run_get_decision)

    p_history = subparsers.add_parser("show-decision-history", help="Show decision audit history.")
    p_history.add_argument("decision_id")
    p_history.set_defaults(func=run_show_decision_history)

    p_gen_docs = subparsers.add_parser("generate-knowledge-documents", help="Generate the synthetic engineering document corpus.")
    p_gen_docs.add_argument("--output", default="data/knowledge_base/source_documents")
    p_gen_docs.set_defaults(func=run_generate_knowledge)

    p_ingest = subparsers.add_parser("ingest-knowledge-documents", help="Ingest synthetic engineering documents.")
    p_ingest.add_argument("--source-dir", default="data/knowledge_base/source_documents")
    p_ingest.add_argument("--force", action="store_true", help="Re-parse and rebuild unchanged documents.")
    p_ingest.set_defaults(func=run_ingest_knowledge)

    p_search = subparsers.add_parser("search-knowledge", help="Search engineering evidence.")
    p_search.add_argument("query")
    p_search.add_argument("--top-k", type=int, default=5)
    p_search.set_defaults(func=run_search_knowledge)

    p_ask = subparsers.add_parser("ask-knowledge", help="Ask a grounded engineering question.")
    p_ask.add_argument("question")
    p_ask.add_argument("--asset-id", default=None)
    p_ask.add_argument("--top-k", type=int, default=5)
    p_ask.set_defaults(func=run_ask_knowledge)

    p_init = subparsers.add_parser("initialize-demo", help="Prepare the application for demonstration.")
    p_init.add_argument("--output", default="data/evaluation")
    p_init.add_argument("--seed", type=int, default=20261122)
    p_init.add_argument("--asset-count", type=int, default=1500)
    p_init.add_argument("--observation-days", type=int, default=365)
    p_init.add_argument("--horizon-days", type=int, default=90)
    p_init.add_argument("--failure-prevalence", type=float, default=0.12)
    p_init.set_defaults(func=run_initialize_demo)

    return parser


def run_generate_knowledge(args: argparse.Namespace) -> int:
    from rag.documents import generate_corpus

    manifest = generate_corpus(Path(args.output))
    print(f"Generated {len(manifest)} documents in {args.output}")
    return 0


def run_ingest_knowledge(args: argparse.Namespace) -> int:
    from rag.embeddings import MockEmbeddingProvider
    from rag.ingestion import ingest_directory
    from rag.repository import SQLAlchemyKnowledgeRepository

    from backend.app.database import get_db

    session = next(get_db())
    try:
        repository = SQLAlchemyKnowledgeRepository(session)
        provider = MockEmbeddingProvider()
        result = ingest_directory(
            Path(args.source_dir), repository, provider, force=getattr(args, "force", False)
        )
        session.commit()
    finally:
        session.close()
    print(result)
    return 0


def run_search_knowledge(args: argparse.Namespace) -> int:
    from rag.embeddings import MockEmbeddingProvider
    from rag.repository import SQLAlchemyKnowledgeRepository
    from rag.service import EvidenceService

    from backend.app.database import get_db

    session = next(get_db())
    repository = SQLAlchemyKnowledgeRepository(session)
    provider = MockEmbeddingProvider()
    service = EvidenceService(repository, provider)
    results = service.search(args.query, top_k=args.top_k)
    for item in results:
        print(item["chunk_id"], round(item.get("rerank_score", item.get("combined_score", 0.0)), 4), item.get("text", "")[:80])
    return 0


def run_ask_knowledge(args: argparse.Namespace) -> int:
    from rag.embeddings import MockEmbeddingProvider
    from rag.generation import MockGenerationProvider
    from rag.repository import SQLAlchemyKnowledgeRepository
    from rag.service import EvidenceService

    from backend.app.database import get_db

    session = next(get_db())
    repository = SQLAlchemyKnowledgeRepository(session)
    provider = MockEmbeddingProvider()
    generator = MockGenerationProvider()
    service = EvidenceService(repository, provider, generator)
    result = service.ask(args.question, asset_id=args.asset_id, top_k=args.top_k)
    print(result["answer"])
    print("Citations:", [c.get("chunk_id") for c in result["citations"]])
    return 0


def run_list_pending_decisions(args: argparse.Namespace) -> int:
    from backend.app.database import get_db
    from decisions.service import list_decisions

    session = next(get_db())
    items, total = list_decisions(session, status="PENDING_REVIEW")
    print({"total": total, "items": [str(d.decision_id) for d in items]})
    return 0


def run_get_decision(args: argparse.Namespace) -> int:
    from uuid import UUID

    from backend.app.database import get_db
    from decisions.service import get_decision

    session = next(get_db())
    decision = get_decision(session, UUID(args.decision_id))
    print(decision.decision_status if decision else "not found")
    return 0 if decision else 4


def run_show_decision_history(args: argparse.Namespace) -> int:
    from uuid import UUID

    from backend.app.database import get_db
    from decisions.service import get_history

    session = next(get_db())
    events = get_history(session, UUID(args.decision_id))
    print([{"action": e.action, "new_status": e.new_status} for e in events])
    return 0


def run_initialize_demo(args: argparse.Namespace) -> int:
    from backend.app.database import get_db
    from backend.app.models import RiskRecord as RiskRecordModel

    params, directory, cutoff, horizon_end = _evaluation_context(args)
    # 1. Verify DB connectivity
    session = next(get_db())
    from sqlalchemy import text

    session.execute(text("SELECT 1"))
    print("DB OK")
    # 2. Generate eval data
    manifest = generate_independent_evaluation(directory, params=params)
    print("Eval data generated:", manifest["counts"])
    # 3. Train model
    failures = []
    for row in load_rows(directory / "failures.csv"):
        mapped = dict(row)
        mapped["asset_id"] = mapped.get("asset_ref") or ""
        failures.append(failure_from_mapping(mapped))
    snapshots = build_independent_feature_snapshots(directory, prediction_cutoff=cutoff)
    failed_ids = {f.asset_id for f in failures}
    confirmed = confirmed_healthy_until_for_snapshots(snapshots, cutoff, params.observation_days, horizon_end, failed_ids)
    decisions = classify_outcomes(failures, [str(s.get("asset_id")) for s in snapshots], cutoff, horizon_end, confirmed_healthy_until=confirmed)
    dataset = build_modeling_dataset(snapshots, decisions)
    trained = train_baseline(dataset, "logistic_regression", seed=args.seed)
    from ml.artifacts.registry import save_model

    save_model(trained, Path("ml/artifacts/models"))
    print("Model trained; metrics:", trained.metrics)
    # 4. Generate operational risk records with the trained model (persisted)
    import types

    print("Building operational risk workspace ...")
    result_code = run_operational_risk(
        types.SimpleNamespace(model="logistic_regression", persist=True)
    )
    if result_code != 0:
        print("Operational risk generation failed with code", result_code)
    # 5. Generate + ingest knowledge docs
    from rag.documents import generate_corpus
    from rag.embeddings import MockEmbeddingProvider
    from rag.ingestion import ingest_directory
    from rag.repository import SQLAlchemyKnowledgeRepository

    source_dir = Path("data/knowledge_base/source_documents")
    generate_corpus(source_dir)
    repo = SQLAlchemyKnowledgeRepository(session)
    provider = MockEmbeddingProvider()
    result = ingest_directory(source_dir, repo, provider, force=True)
    session.commit()
    print("Knowledge ingestion:", result)
    # 6. Seed a demo decision
    from decisions.service import create_decision

    try:
        create_decision(session, asset_id="T-00001", asset_type="transformers", reviewer="demo-reviewer", reason="Demo seed decision")
        session.commit()
        print("Seeded demo decision.")
    except Exception as exc:
        session.rollback()
        print("Decision seed skipped:", exc)
    print("Demo initialization complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
