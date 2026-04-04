# Camille

AI Liability Risk Assessment Agent — ingests enterprise AI governance documentation and produces structured risk scores for insurance underwriters.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Postgres + MinIO)
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

```bash
docker compose ps   # wait until all services are healthy
```

### 2. Backend setup

```bash
cd backend
cp .env.example .env          # edit ANTHROPIC_API_KEY at minimum
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
```

### 3. Run the API

```bash
uvicorn app.main:app --reload
```

- API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- Health: `curl http://localhost:8000/health`

> **Auth:** All endpoints except `/health` require the header
> `X-API-Key: <API_KEY_SECRET>`.
> Default dev value: `change-me-in-production-use-a-long-random-string`

---

## Testing with curl

Set the key once:

```bash
KEY="change-me-in-production-use-a-long-random-string"
```

### Health check

```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

### Create an organisation

```bash
curl -s -X POST http://localhost:8000/api/v1/organizations \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme AI Corp", "slug": "acme-ai"}' | jq .
```

### Create an assessment

```bash
# Replace <org_id> with the id from the previous response
curl -s -X POST http://localhost:8000/api/v1/assessments \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"organization_id": "<org_id>"}' | jq .
```

### Upload a governance document

```bash
# Replace <assessment_id> with the id from above
curl -s -X POST http://localhost:8000/api/v1/assessments/<assessment_id>/documents \
  -H "X-API-Key: $KEY" \
  -F "file=@test_data/company_b_quickhire/hitl_policy_v2_jan2026.txt" | jq .
```

Upload all QuickHire documents at once:

```bash
A_ID="<assessment_id>"
for f in test_data/company_b_quickhire/*.txt; do
  echo "Uploading $f ..."
  curl -s -X POST http://localhost:8000/api/v1/assessments/$A_ID/documents \
    -H "X-API-Key: $KEY" \
    -F "file=@$f" | jq -r '.filename + " → " + .status'
done
```

### Trigger the pipeline

```bash
curl -s -X POST http://localhost:8000/api/v1/assessments/<assessment_id>/process \
  -H "X-API-Key: $KEY" | jq .
```

### Poll status

```bash
# Repeat until status == "complete"
curl -s http://localhost:8000/api/v1/assessments/<assessment_id> \
  -H "X-API-Key: $KEY" | jq '{status, overall_score, risk_tier}'
```

### Get dimension scores + flags

```bash
curl -s http://localhost:8000/api/v1/assessments/<assessment_id>/scores \
  -H "X-API-Key: $KEY" | jq .
```

### Download the PDF report

```bash
# Follows the presigned-URL redirect and saves the PDF locally
curl -s -L http://localhost:8000/api/v1/assessments/<assessment_id>/report \
  -H "X-API-Key: $KEY" \
  -o report.pdf

# macOS
open report.pdf

# Windows
start report.pdf

# Linux
xdg-open report.pdf
```

### List all assessments for an org

```bash
curl -s http://localhost:8000/api/v1/organizations/<org_id>/assessments \
  -H "X-API-Key: $KEY" | jq '.[].status'
```

### Update carrier scoring weights

```bash
# Increase human_oversight weight, decrease third_party_risk
curl -s -X PUT http://localhost:8000/api/v1/assessments/<assessment_id>/config \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"weight_overrides": {"human_oversight": 0.30, "third_party_risk": 0.02}}' | jq .
```

---

## Automated pipeline walkthrough

Runs the full QuickHire pipeline, prints scores, and downloads the PDF report to `report_output.pdf`:

```bash
cd backend
python scripts/run_pipeline.py
```

Expected output:
- Overall score in **[48, 58]** → risk tier **medium**
- 5 critical flags: ChatGPT ungoverned, EEOC complaint, LL144 non-compliance, no AI IR plan, HITL senior-only
- PDF saved to `backend/report_output.pdf`

---

## Manual extraction verification (no database)

Runs extraction + scoring against real documents via Claude API directly — useful for prompt calibration:

```bash
cd backend
python scripts/verify_extraction.py company_b_quickhire   # medium risk, target 48–58
python scripts/verify_extraction.py company_a_greenscore  # low risk, target 77–85
python scripts/verify_extraction.py company_c_autoclaim   # critical risk, target 8–20
```

Save output: `python scripts/verify_extraction.py company_b_quickhire > results_quickhire.json`

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | Claude API key — extraction, classification, report narrative |
| `API_KEY_SECRET` | **Yes** | Shared secret for `X-API-Key` header; change before any deployment |
| `DATABASE_URL` | Yes | asyncpg connection string; default points to docker-compose Postgres on port 5433 |
| `S3_ENDPOINT_URL` | Yes (local) | MinIO endpoint for local dev: `http://localhost:9000` |
| `AWS_ACCESS_KEY_ID` | Yes (local) | MinIO access key: `minioadmin` |
| `AWS_SECRET_ACCESS_KEY` | Yes (local) | MinIO secret key: `minioadmin` |
| `S3_BUCKET_NAME` | No | Document + report bucket (default: `camille-documents-local`) |
| `LLM_EXTRACTION_MODEL` | No | Claude model for governance extraction (default: `claude-sonnet-4-6`) |
| `LLM_CLASSIFICATION_MODEL` | No | Claude model for doc classification (default: `claude-sonnet-4-6`) |
| `LLM_REPORT_MODEL` | No | Claude model for report narrative (default: `claude-opus-4-6`) |
| `EXTRACTION_CONCURRENCY` | No | Max parallel LLM calls per pipeline run (default: `3`) |
| `NEWS_API_KEY` | No | External signals — media sentiment enrichment |
| `SENTRY_DSN` | No | Error tracking — leave blank to disable |

---

## Run tests

Unit tests (no Docker required):

```bash
cd backend
pytest tests/ --ignore=tests/integration -x --tb=short
pytest tests/ --ignore=tests/integration --cov=app --cov-report=term-missing
```

Integration tests (require Docker):

```bash
pytest tests/integration/ -v
```

---

## Database migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "describe change"   # after model changes
```

---

## Lint & type check

```bash
ruff check app/
mypy app/
```
