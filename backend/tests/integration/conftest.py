"""
Integration test conftest.

Two modes, selected by the ``API_BASE_URL`` environment variable:

**CI mode** (``API_BASE_URL`` is set):
  Assumes a real API server is already running at that URL and a real
  PostgreSQL database is accessible via ``DATABASE_URL``.  No Docker
  containers are started by the test process.  Use this when CI brings
  up the API as a Docker container and exposes it on localhost.

**Local mode** (``API_BASE_URL`` is unset):
  Spins up a ``pgvector/pgvector:pg16`` container via testcontainers-python
  (requires Docker) and hits the FastAPI app through ASGI transport.
  All integration tests are automatically skipped if Docker is unavailable.

Usage:
    # Local dev
    pytest tests/integration/ -v

    # CI (server already running)
    API_BASE_URL=http://localhost:8000 pytest tests/integration/ -v
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models as _models  # noqa: F401 — register all ORM models with Base.metadata
from app.database import get_db
from app.main import app
from app.models.base import Base

_API_BASE_URL: str | None = os.environ.get("API_BASE_URL")
_CI_MODE = _API_BASE_URL is not None


# ── CI mode: real HTTP client, real Postgres already running ────────────────

if _CI_MODE:
    # Session-scoped engine pointing at the CI Postgres service container.
    @pytest_asyncio.fixture(scope="session")
    async def integration_engine():
        db_url = os.environ["DATABASE_URL"]
        engine = create_async_engine(db_url, echo=False, poolclass=NullPool)
        yield engine
        await engine.dispose()

    @pytest_asyncio.fixture(autouse=True)
    async def setup_integration_db(integration_engine) -> AsyncGenerator[None, None]:
        """Drop and recreate all tables before every integration test."""
        async with integration_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        yield

    @pytest_asyncio.fixture
    async def db(integration_engine, setup_integration_db: None) -> AsyncGenerator[AsyncSession, None]:
        SessionLocal = async_sessionmaker(integration_engine, expire_on_commit=False)
        async with SessionLocal() as session:
            yield session

    @pytest_asyncio.fixture
    async def client(setup_integration_db: None) -> AsyncGenerator[AsyncClient, None]:
        async with AsyncClient(
            base_url=_API_BASE_URL,
            timeout=10.0,
        ) as ac:
            yield ac

    @pytest_asyncio.fixture
    async def unauthed_client() -> AsyncGenerator[AsyncClient, None]:
        async with AsyncClient(base_url=_API_BASE_URL, timeout=10.0) as ac:
            yield ac


# ── Local mode: testcontainers Postgres + ASGI transport ───────────────────

else:

    @pytest.fixture(scope="session")
    def pg_container():
        """Start a pgvector/pgvector:pg16 container for the test session.

        Skips all integration tests if Docker is unavailable or testcontainers
        is not installed.
        """
        try:
            from testcontainers.postgres import PostgresContainer  # noqa: PLC0415
        except ImportError:
            pytest.skip("testcontainers not installed — run: pip install 'testcontainers[postgres]'")

        try:
            container = PostgresContainer(
                image="pgvector/pgvector:pg16",
                username="camille",
                password="localdev",
                dbname="camille_integration",
            )
            container.start()
        except Exception as exc:
            pytest.skip(f"Docker unavailable for integration tests: {exc}")

        yield container
        container.stop()

    @pytest.fixture(scope="session")
    def integration_db_url(pg_container) -> str:
        """Return an asyncpg-compatible URL for the test container."""
        url: str = pg_container.get_connection_url()
        url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        url = url.replace("psycopg2://", "asyncpg://")
        if not url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @pytest_asyncio.fixture(scope="session")
    async def integration_engine(integration_db_url: str):
        engine = create_async_engine(integration_db_url, echo=False, poolclass=NullPool)
        yield engine
        await engine.dispose()

    @pytest_asyncio.fixture(autouse=True)
    async def setup_integration_db(integration_engine) -> AsyncGenerator[None, None]:
        """Drop and recreate all tables before every integration test."""
        async with integration_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        yield

    @pytest_asyncio.fixture
    async def db(integration_engine, setup_integration_db: None) -> AsyncGenerator[AsyncSession, None]:
        SessionLocal = async_sessionmaker(integration_engine, expire_on_commit=False)
        async with SessionLocal() as session:
            yield session

    @pytest_asyncio.fixture
    async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield db

        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
        app.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def unauthed_client() -> AsyncGenerator[AsyncClient, None]:
        """Client with no API key — for testing 401 responses."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
