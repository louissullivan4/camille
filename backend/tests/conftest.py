import asyncio
import os
import sys
from collections.abc import AsyncGenerator

import pytest_asyncio

# asyncpg is incompatible with Windows ProactorEventLoop (Python 3.8+ default on Windows).
# SelectorEventLoop handles asyncpg teardown correctly.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.base import Base

# Derive test DB URL from settings - swap DB name to camille_test, keep all other config
_default_test_url = settings.DATABASE_URL.rsplit("/", 1)[0] + "/camille_test"
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", _default_test_url)

# NullPool: no connection pooling in tests - each operation gets a fresh connection.
# This avoids asyncpg binding pool connections to a specific event loop, which causes
# "Future attached to a different loop" when pytest-asyncio uses per-test loops.
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
