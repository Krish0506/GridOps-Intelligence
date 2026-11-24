# GridOps Intelligence — User Guide

This guide explains how to run and use the **GridOps Intelligence** local demonstration platform. It is written for operators, reviewers, and interviewers who need to understand what the product does, where its data comes from, and how to interpret what the screens are telling them.

---

## 1. What this product is

GridOps Intelligence is an AI-assisted utility asset reliability platform. It combines:

- a synthetic utility asset inventory,
- telemetry, maintenance work orders, inspections, failure incidents, and weather observations,
- a leakage-safe predictive feature pipeline and persisted logistic-regression artifact,
- unsupervised anomaly detection against a persisted population baseline,
- risk prioritization with transparent priority rules,
- model explainability,
- retrieval-augmented engineering evidence with citations,
- a human-in-the-loop engineering decision workflow,
- governance and audit reporting.

**Important:** all data, documents, model metrics, citations, and anomaly scores in this application are **synthetic demonstration material**. They are not real utility operational data, and model outputs must not be presented as calibrated real-world failure probabilities or as a production readiness certification.

---

## 2. Running the application locally

From the repository root:

```powershell
.\scripts\start-gridops.ps1
```

Optional switches:

- `-SkipDemoInit` — do not run one-time demo initialization.
- `-NoBuild` — do not rebuild the API container image.

The script:

1. Checks Docker availability.
2. Starts PostgreSQL (host port `55432`).
3. Runs Alembic migrations (`upgrade head`) with the host virtualenv.
4. Rebuilds and starts the FastAPI container.
5. Waits for API health and database reachability.
6. Starts the Vite frontend as a detached process (PID file in `.run/vite.pid`).
7. Waits for frontend health and runs proxy smoke checks (`/api/v1/overview`, `/api/v1/risk/summary`, `/api/v1/predictive`, `/api/v1/governance`).

Stop with:

```powershell
.\scripts\stop-gridops.ps1
```

The stop script stops the frontend process tree and the API container, and leaves the database volume intact. Destructive volume removal (`docker compose down -v`) is intentionally not automated.

### Local URLs

- Frontend: `http://localhost:5173`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

---

## 3. Page-by-page guide

### 3.1 Operations Overview (`/`)

The command center. Shows database-derived counts:

- assets under management (2,600 in the synthetic estate; 2,538 active / 62 retired),
- active work orders (509; 3 critical / 5 high),
- failures in the last 90 days (23 in-window; 60 incidents in synthetic history),
- decisions awaiting review,
- risk review bands (P1–P5 counts),
- persisted model artifact in use,
- decision threshold,
- top review priorities table.

Navigation: “Open risk workbench” and “Inspect model evaluation” deep links.

### 3.2 Asset Explorer (`/assets`)

Server-side paginated, globally searchable asset inventory.

- Search by asset ID, name, or region (server-side, full-text).
- Filters: equipment type, status, region; clear filters action.
- Server-side sorting and pagination with Previous / Next controls and page-size behaviour.
- Row actions: “View risk” deep link into risk prioritization for that asset.

### 3.3 Predictive Analytics (`/predictive`)

- Preferred model: `Logistic Regression` (`logistic_regression@7c6f0fc80872`).
- Persisted artifact path: `ml/artifacts/models/logistic_regression.pkl`.
- Metrics: validation ROC AUC, precision, recall, F1, average precision, Brier score; held-out confusion matrix; feature contract (171 features).
- Model registry: persisted logistic regression, random forest, histogram gradient boosting entries.
- Evaluation context clearly states the metrics are from the **independent synthetic evaluation cohort**, not operational or real-world data.

### 3.4 Risk Prioritization (`/risk`)

- Ranked risk workspace over persisted risk records (snapshot cutoff `2026-11-21T12:00:00Z`).
- Band chart (population counts, not failure probabilities).
- Probability distribution chart (0–0.05, 0.05–0.2, 0.2–0.5, 0.5–0.9, 0.9–1.0, unavailable).
- Filters: equipment, priority, model category; sorting by rank / probability / anomaly / criticality / asset ID.
- Selected asset drawer: rank, probability, percentile, anomaly score, criticality, drivers, data quality, decision CTA.

### 3.5 Model Explainability (`/explainability`)

- Asset selector (top review priorities plus free-text lookup).
- Robust z-score deviation against persisted population baseline (median + robust scale; MAD/IQR/std fallback; cap at 50).
- Global model importance (aggregated from fitted coefficients; not local attribution; no SHAP computed).
- Methodology limits: deviation, importance, probability semantics; imputation notes; causality guardrail.

### 3.6 Evidence Intelligence (`/evidence`)

- Knowledge corpus stats (36 documents / 36 chunks; 7 categories; formats).
- Ask-an-engineering-question interface:
  - asset context optional,
  - document category filter,
  - equipment filter,
  - question + submit / suggestion chips.
- Structured database questions route to PostgreSQL with structured breakdowns.
- Document retrieval questions use hybrid retrieval with citations (title, revision, page, excerpt, source checksum, key facts, limitations).
- Corpus browser with search / category / equipment filters and source content preview.

### 3.7 Engineering Decision Review (`/decisions`)

- Decision queue with status, reviewer, rationale, risk category, probability.
- Decision detail drawer with asset context, current risk, rationale, audit history, attached evidence.
- Actions: Start review → Approve / Reject / Escalate / Defer / Override.
- **A rationale is mandatory** before any action; action buttons stay disabled until provided.
- No auto-approval exists; the human reviewer is recorded on every transition.

### 3.8 Governance and Audit (`/governance`)

- Warehouse inventory counts by dataset.
- Database / migration state, risk generation lineage, quality posture.
- Pipeline ingestion runs.
- Data-quality posture (checks, records checked/failed, severity buckets, failing checks with details).
- Knowledge corpus governance and latest ingestion.
- Model registry and evaluation metadata.
- Decision audit trail and recent decisions.

---

## 4. How to interpret the key numbers

### 4.1 Model probability vs anomaly score

- **Model probability**: the persisted classifier output for the synthetic asset at the prediction cutoff. Range [0, 1]. It represents ranking of the synthetic asset against a training cohort, **not** a calibrated real-world failure probability.
- **Anomaly score**: an unsupervised robust deviation magnitude against the persisted population baseline. Range is capped (cap applied at 50 in the operational run). It is **not** a failure probability; it flags how unusual a feature observation was.

### 4.2 Risk priorities (P1–P5)

- P1: model-probability percentile ≥ 99 and (criticality High/Critical or anomaly percentile ≥ 99).
- P2: model-probability percentile ≥ 95, or anomaly percentile ≥ 99 with High/Critical criticality.
- P3–P5: descending percentile thresholds (see `/risk` “How the review priority is assigned”).

Priorities are deterministic ranks over persisted probabilities with tie-breaking, because model probabilities can saturate at 1.0.

### 4.3 Model evaluation metrics

Perfect or near-perfect metrics reflect deliberately separable synthetic outcomes and a synthetic evaluation cohort. They are evidence that the pipeline runs end-to-end, not evidence of real utility performance or production readiness.

### 4.4 Citations and evidence

Answers cite retrieved chunks with document identity, revision, page, excerpt, and checksum. Synthetic documents are labelled as demonstration material, not official engineering standards.

### 4.5 Decisions and audit

Every decision has an append-only transition history. Rationale is mandatory. The platform never auto-approves and never executes maintenance.

---

## 5. Known limitations

- Synthetic demonstration data only; no real operational data.
- No authentication or authorization.
- No compliance certification.
- No model drift monitoring or automated retraining.
- No production maintenance execution.
- Evidence answers for document questions are extractive over synthetic text (no hosted LLM was used).
- Anomaly score is not calibrated; model probability is not calibrated failure probability.

For deeper context see:

- `docs/ARCHITECTURE.md`
- `docs/INTERVIEW_PREPARATION.md`
- `docs/FINAL_REPORT.md`
- `docs/engineering/M9_HANDOFF.md`
