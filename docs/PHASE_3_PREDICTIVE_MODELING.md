# Phase 3 — Predictive Modeling & Anomaly Detection

Status: **Implemented** (CPU-only; pure Python plus scikit-learn, which is now an
explicit dependency).

## 1. Data-readiness criteria

Supervised classification is gated by `ml.data.assess_readiness`. A dataset is
ready only when all of the following hold:

- At least 100 confirmed positives.
- At least 100 confirmed negatives.
- At least one feature snapshot.

The default independent evaluation dataset (seed `20261122`, 1500 assets) yields
176 confirmed positives / 1181 confirmed negatives / 143 unknown, so the gate
passes. Minimum sample requirements are configurable and never silently lowered.

## 2. Modeling dataset

- Built from feature snapshots and three-state outcome decisions via
  `ml.data.cohort.build_modeling_dataset`.
- Only `ml.features.asset.model_feature_names()` are used (numeric, boolean,
  categorical).
- Identifiers, metadata, timestamps, cutoffs, event bounds, labels, severity,
  and downtime are excluded.
- Unknown outcomes are excluded; the cohort is never manufactured into negatives.

## 3. Feature selection and exclusions

- Predictors: `numeric_feature_names() + boolean_feature_names() + categorical_feature_names()`.
- Excluded: `identifier_columns()` (`asset_id`), `metadata_columns()` (names,
  install dates, current status, observation timestamps, cutoff metadata, event
  bounds, weather region), plus all label attributes.
- Preprocessing (median imputation + standardization for numeric; constant
  imputation + one-hot encoding for categorical) is fitted only on training rows.

## 4. Validation strategy

- Deterministic asset-level three-way split: 60% training, 20% validation, 20%
  final test.
- Split is stratified by label and seeded (`random.Random`) so class
  representation is preserved across partitions.
- Asset identifiers are never sorted and split sequentially; a seeded shuffle
  avoids asset-type and generation-order bias.
- Preprocessing and model parameters are fitted on training data only.
- Validation data is used for model selection and classification-threshold
  decisions (threshold tuned by F1 maximization on validation only).
- Final test data is used only for final evaluation after model selection.
- Unknown labels are excluded from supervised classification.

## 5. Model choices

- Logistic regression (pure Python, L2-regularized gradient descent).
- Random Forest (scikit-learn).
- HistGradientBoosting (scikit-learn).

All three share the same fitted preprocessing pipeline. scikit-learn was added
as an explicit dependency (`scikit-learn>=1.5,<2.0`) because the project's
intended ML stack includes it and the two additional baselines require it.

## 6. Metrics and interpretation

`ml.evaluation.metrics.classification_metrics` reports accuracy, precision,
recall, F1, ROC-AUC, average precision, Brier score, confusion-matrix counts,
and class prevalence. The held-out validation and final-test metrics for the
default dataset are all 1.0 (accuracy/precision/recall/F1/ROC-AUC/average
precision) with Brier ~0.0003 (validation) / ~0.0001 (test). These are
synthetic-data results and are not a claim of real-world utility performance;
the perfect separability is a legitimate consequence of the strong hidden
degradation signal in the synthetic features, not a leakage artifact (see the
leakage regression tests).

## 7. Anomaly detection methodology

- Transparent statistical baseline: robust z-scores (median/MAD) over numeric
  model features, aggregated to a per-asset magnitude.
- Independent of the classification readiness gate.
- Anomaly score is not a calibrated failure probability.

## 8. Risk prioritization

- Reusable `RiskRecord` schema separating model probability (when valid),
  anomaly score, data-quality indicators, primary drivers, model version, and
  limitations.
- When no classifier is available, category is anomaly/normal based on anomaly
  score only, and the output is labelled as anomaly-based prioritization.

## 9. Explainability

- Global feature importance via robust-z driver ranking.
- Individual prediction explanations via per-asset feature deviation ranking.
- Direction of influence reported where supported.
- No causality claims; no SHAP dependency.

## 10. Limitations

- Single holdout-style three-way split (no repeated cross-validation).
- Anomaly scores are raw robust-z magnitudes, not calibrated.
- Synthetic data — not a real-world performance claim.
- No frontend integration in this milestone.

## 11. Commands and output locations

```bash
python -m data_engineering.cli generate-evaluation --output data/evaluation
python -m data_engineering.cli assess-readiness --output data/evaluation
python -m data_engineering.cli build-snapshots --output data/evaluation
python -m data_engineering.cli train --output data/evaluation --model logistic_regression
python -m data_engineering.cli train --output data/evaluation --model random_forest
python -m data_engineering.cli train --output data/evaluation --model hist_gradient_boosting
python -m data_engineering.cli evaluate --output data/evaluation --model logistic_regression
python -m data_engineering.cli anomaly --output data/evaluation --top-n 10
python -m data_engineering.cli risk --output data/evaluation
```

Artifacts: `ml/artifacts/models/*.pkl` and `*.json` (gitignored model binaries).
Documentation: `docs/PHASE_3_PREDICTIVE_MODELING.md`.
