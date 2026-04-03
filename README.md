# Camille

AI Liability Risk Assessment Agent - ingests enterprise AI governance documentation and produces structured risk scores for insurance underwriters.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Python 3.12+

---

## Start the database

```bash
docker compose up -d db
```

Starts PostgreSQL 16 with pgvector on port `5432`. Wait for the healthcheck to pass (`docker compose ps` should show `healthy`).

---

## Backend setup

```bash
cd backend
cp .env.example .env
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
```

## Run the API

```bash
uvicorn app.main:app --reload
```

API available at `http://localhost:8000` - docs at `http://localhost:8000/docs`.

Health check: `curl http://localhost:8000/api/v1/health`

## Run tests

```bash
pytest tests/ -x
c
```

Requires the database to be running (`docker compose up -d db`).

---

## Manual extraction verification (Phase 3)

Runs the full pipeline end-to-end against real test documents using a live Claude API call — no database needed.

### 1. Set your API key

Add to `backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Run the verification script

```bash
cd backend
python scripts/verify_extraction.py company_b_quickhire
```

Other available personas:

```bash
python scripts/verify_extraction.py company_a_greenscore   # low risk, target score 78–90
python scripts/verify_extraction.py company_b_quickhire    # medium risk, target score 38–62  ← primary demo
python scripts/verify_extraction.py company_c_autoclaim    # critical risk, target score 8–28
```

### 3. Save output to share

```bash
python scripts/verify_extraction.py company_a_greenscore > results_greenscore.json
python scripts/verify_extraction.py company_b_quickhire > results_quickhire.json
python scripts/verify_extraction.py company_c_autoclaim > results_autoclaim.json
```

Paste `results_quickhire.json` back into the conversation.

### What to check

For QuickHire (`company_b_quickhire`), the pipeline passes when:

| Check | Expected |
|---|---|
| `overall_score` | `38–62` |
| `risk_tier` | `"medium"` |
| Bias audit staleness flag | Present — audit is ~3 years old |
| HITL scope flag | `senior_only` — VP+ only |
| No IR plan flag | Critical flag present |
| LL144 non-compliance flag | Critical flag present |
| ChatGPT without governance | Critical flag present |

### Output format

The script prints a single JSON object:

```
{
  "company": "company_b_quickhire",
  "documents_loaded": [...],        ← files found and chunk counts
  "total_chunks": 42,
  "overall_score": 47.3,
  "risk_tier": "medium",
  "dimension_scores": {             ← per-dimension score + flags
    "model_inventory": { "score": 52.0, "flags": [...] },
    ...
  },
  "all_flags": [...],               ← every flag with dimension label
  "raw_findings": {...}             ← raw LLM extraction output per dimension
}
```
