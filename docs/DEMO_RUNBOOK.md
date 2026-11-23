# Demo Runbook

## Prerequisites
- Python 3.11, Node 20, Docker (Rancher Desktop).
- `.env` configured (see `.env.example`).

## Startup
1. Start database: `docker compose up -d db`
2. Apply migrations: `alembic upgrade head`
3. Start API: `uvicorn backend.app.main:app --reload`
4. Start frontend: `cd frontend && npm install && npm run dev`

## Data generation
```bash
python -m data_engineering.generators.independent_evaluation --output data/evaluation
python -m data_engineering.cli generate-knowledge-documents
python -m data_engineering.cli ingest-knowledge-documents
python -m data_engineering.cli train --output data/evaluation --model logistic_regression
```

## API access
- Swagger: http://localhost:8000/docs
- Frontend: http://localhost:5173

## Demo walkthrough
1. Open Operations Overview.
2. Select a synthetic transformer in Asset Explorer.
3. Review predictive risk in Risk Prioritization.
4. Inspect model explanation.
5. Open Evidence Intelligence; ask "Why might this transformer be at elevated risk?"
6. Inspect citations.
7. Create an engineering decision and associate evidence.
8. Record an approve/reject/override with reason.
9. Open Governance and Audit; inspect decision history.

## Troubleshooting
- If DB unavailable, check Docker and port 55432.
- If frontend cannot reach API, set `VITE_API_BASE`.