# Camille

AI Liability Risk Assessment Agent — ingests enterprise AI governance documentation and produces structured risk scores for insurance underwriters.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Postgres)
- Python 3.12+

---

## Quick start

### 1. Start backing services

```bash
docker compose up -d db minio minio-init
```

| Service | What | Port |
|---|---|---|
| `db` | PostgreSQL 16 + pgvector | 5433 |
| `minio` | S3-compatible local storage | 9000 (API), 9001 (UI) |
| `minio-init` | Creates the `camille-documents-local` bucket | — |

MinIO web UI: `http://localhost:9001` — login `minioadmin` / `minioadmin`

Wait for healthy:

```bash
docker compose ps
```

### 2. Backend setup

```bash
cd backend
cp .env.example .env
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
```

### 3. Run the API

```bash
uvicorn app.main:app --reload
```

- API: `http://localhost:8000`
- Docs (Swagger): `http://localhost:8000/docs`
- Health: `curl http://localhost:8000/api/v1/health`

> **Auth:** All endpoints except `/health` and `/docs` require the header `X-API-Key: <your API_KEY_SECRET from .env>`. Default dev value: `change-me-in-production-use-a-long-random-string`.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | Claude API key — used for document extraction and classification |
| `API_KEY_SECRET` | **Yes** | Shared secret for `X-API-Key` header auth; change before any deployment |
| `DATABASE_URL` | Yes | asyncpg connection string; default points to docker-compose Postgres on port 5433 |
| `LLM_EXTRACTION_MODEL` | No | Claude model for governance extraction (default: `claude-sonnet-4-6`) |
| `LLM_CLASSIFICATION_MODEL` | No | Claude model for doc classification (default: `claude-sonnet-4-6`) |
| `LLM_REPORT_MODEL` | No | Claude model for report narrative (default: `claude-sonnet-4-6`) |
| `EXTRACTION_CONCURRENCY` | No | Max parallel LLM calls per pipeline run (default: `3`) |
| `AWS_ACCESS_KEY_ID` | No | S3 uploads — leave blank for local dev (document upload will fail) |
| `AWS_SECRET_ACCESS_KEY` | No | S3 uploads |
| `AWS_REGION` | No | S3 region (default: `us-east-1`) |
| `S3_BUCKET_NAME` | No | S3 bucket for documents and reports (default: `camille-documents-local`) |
| `NEWS_API_KEY` | No | External signals — media sentiment enrichment |
| `PACER_API_KEY` | No | External signals — litigation data |
| `SENTRY_DSN` | No | Error tracking — leave blank to disable |

---

## Run tests

Requires the database to be running.

```bash
cd backend
pytest tests/ -x --tb=short
pytest tests/ --cov=app --cov-report=term-missing   # with coverage
```

---

## Full pipeline walkthrough (via API)

```bash
cd backend
python scripts/run_pipeline.py
```

## Manual extraction verification (no database)

Runs the full extraction + scoring pipeline against real documents using the Claude API directly — useful for prompt calibration.

```bash
cd backend
python scripts/verify_extraction.py company_b_quickhire   # medium risk, target 48–58
python scripts/verify_extraction.py company_a_greenscore  # low risk, target 77–85
python scripts/verify_extraction.py company_c_autoclaim   # critical risk, target 8–20
```

Save output: `python scripts/verify_extraction.py company_b_quickhire > results_quickhire.json`

---

## Database migrations

```bash
alembic upgrade head
```

---

## Lint & type check

```bash
ruff check app/
mypy app/
```
