# Phase 2B — Independent Synthetic Evaluation Data

Status: **Implementation complete** — dataset generation, validation, labels, and
feature integration are implemented and tested. Predictive-model training and
evaluation remain **blocked** on the synthetic-data limitations described below
(see "Modeling readiness" at the end).

## 1. Why the Milestone 1 dataset is insufficient

The original synthetic utility dataset (Milestone 1, generator:
`data_engineering/generators/generate_all.py`) cannot support defensible
predictive-model evaluation:

1. **Circular failure selection.** Failures were chosen from the top of the
   population ranked by `compute_risk`, a telemetry-derived score
   (`data_engineering/generators/telemetry.py`). The outcome therefore leaks the
   observable signal the model would later rely on.
2. **Outcome-correlated telemetry.** Abnormal readings were injected ±2 days
   around each failure timestamp (including pre-failure readings), so the
   predictors and the label are coupled by construction.
3. **Risk-conditioned operational records.** Failed assets received boosted
   risk scores that drove maintenance and inspection generation
   (`data_engineering/generators/maintenance.py`,
   `data_engineering/generators/inspections.py`).
4. **No defensible confirmed negatives.** The schema has no health-confirmation
   source, so assets without failure records cannot become honest negatives.

## 2. Independent evaluation-data design

The new generator (`data_engineering/generators/independent_evaluation.py`)
builds a second, independent synthetic evaluation dataset whose failure events
are driven by hidden degradation / stress processes.

- **Hidden failure mechanisms.** Each asset is assigned, independently of any
  risk score, to one of several hidden degradation mechanisms (thermal stress,
  load-related degradation, environmental/weather stress, mechanical or
  operational stress, insulation or condition deterioration) with an associated
  degradation rate. A failure occurs when the hidden degradation reaches its
  threshold within the future horizon.
- **Historical telemetry** is generated as noisy observations of the hidden
  degradation process. Readings are strictly earlier than the prediction cutoff
  and strictly earlier than the asset's failure event (no post-failure data).
- **Operational records** (maintenance, inspections, weather) are generated
  from independent processes and realistic timelines; corrective maintenance is
  not generated from future failure labels.
- **Labels** reuse the Milestone 2A three-state contract
  (`ml/features/labels.py`): `CONFIRMED_POSITIVE`, `CONFIRMED_NEGATIVE`, or
  `UNKNOWN`.

## 3. Prediction cutoff and outcome horizon

- Prediction cutoff (configurable): `REFERENCE_DATE - observation_days`
  (default: `2025-11-21T12:00:00`).
- Outcome horizon end: cutoff + `horizon_days` (default: `2026-02-19T12:00:00`).
- A failure is a **positive** when `cutoff < failure_timestamp <= horizon_end`.
- A failure at or before the cutoff is never a future positive.

## 4. Label semantics

- **Confirmed positive** — a failure occurred inside the observation window.
- **Confirmed negative** — the asset has a complete observation history (installed
  at least `observation_days` before the cutoff) and no failure occurred in the
  window. Represented through the explicit health-confirmation path of the
  Milestone 2A label contract.
- **Unknown** — incomplete observation history or missing confirmation; never a
  training label.

The training-cohort helper (`build_training_cohort`) refuses to return a binary
cohort without at least one confirmed negative.

## 5. Leakage prevention

- All historical features are evaluated at an explicit `prediction_cutoff`.
- Per-asset event bounds (first known failure per asset) can be supplied as a
  mapping; the earlier of cutoff and event bound is applied, exclusively.
- The independent generator never passes hidden degradation variables into
  feature records; feature snapshots are built through the Milestone 2A builders
  with the per-asset event bound.

## 6. Dataset parameters and reproducibility

Defaults (all configurable via CLI):

| Parameter | Default |
|---|---|
| Seed | `20261122` |
| Asset count | `240` |
| Observation days | `365` |
| Horizon days | `90` |
| Failure prevalence | `0.12` |

Generation command:

```bash
python -m data_engineering.generators.independent_evaluation \
    --output data/evaluation \
    --seed 20261122 \
    --asset-count 240 \
    --observation-days 365 \
    --horizon-days 90 \
    --failure-prevalence 0.12
```

## 7. Generated artifacts and record counts

The generator writes one CSV per table plus `synthetic_manifest.json` into the
output directory (default `data/evaluation`), and runs the shared validation
module before writing the manifest.

Default-run results (seed `20261122`):

- Total assets: 240 (transformers 96, substations 48, circuit breakers 48,
  feeders 48).
- Failures: 26 confirmed positives.
- Label distribution: 26 confirmed positive / 191 confirmed negative / 23 unknown
  (the unknowns correspond to incomplete-history assets).
- All generated tables pass the shared validation suite (no hard errors).

## 8. Using the dataset with the Milestone 2A feature engineering

- Historical records can be loaded through the existing Milestone 2A loaders or
  converted into the typed records via the `ml.features.types` mapping helpers.
- Feature snapshots for a prediction instant are produced with
  `ml.features.asset.build_asset_feature_record` using the explicit prediction
  cutoff and the per-asset failure-time event bound.

## 9. Limitations and what must not be claimed

- The independent evaluation data is still synthetic; it demonstrates that the
  leakage-safe feature pipeline behaves correctly on independently generated
  outcomes, not that it predicts real-world grid failures.
- The failure prevalence (12%) and degradation parameters are assumptions, not
  measurements.
- The dataset remains small (240 assets); results are not statistically
  significant for production claims.
- The original Milestone 1 dataset is unchanged and remains in `data/generated`.

## 10. Tests

`tests/test_independent_evaluation.py` (8 tests) covers: expected files and CSV
headers, synthetic markers, shared validation, deterministic regeneration,
failure-in-horizon and no-post-failure-telemetry guarantees, three-state labels and
the confirmed-negative training-cohort guard, and feature-snapshot event bounds.

## 11. Modeling readiness

**BLOCKED** for predictive-model training and evaluation until a future milestone
addresses:

1. Independent failure generation that fully decouples hidden degradation
   mechanisms from any observable feature computation (current implementation
   already avoids `compute_risk`; remaining work is a fully transparent
   degradation-threshold simulation).
2. An explicit observation/follow-up process that yields confirmed negatives for
   assets that never failed (complete-history assets are now confirmed negative by
   observation).
3. Sufficient positive/negative volume and statistical evaluation.

Feature-engineering correctness (cutoffs, event bounds, aggregation) is complete;
model-training readiness is a separate future milestone.
