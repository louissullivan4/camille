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
```

Requires the database to be running (`docker compose up -d db`).
