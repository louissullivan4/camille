from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

import app.models as _models  # noqa: F401 — ensure all models are registered with Base.metadata
from app.database import get_db
from app.main import app
from app.models.base import Base


# SQLite does not have a JSONB type; render it as plain JSON (stored as TEXT).
# This must be declared before any engine.begin() / create_all call.
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # type: ignore[misc]
    return compiler.visit_JSON(element, **kw)


# SQLite in-memory with StaticPool: all connections share one in-memory database,
# which avoids the "each connection gets its own DB" pitfall of NullPool + in-memory SQLite.
# check_same_thread=False is required because asyncio may access SQLite from different threads
# internally when using aiosqlite.
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Drop and recreate all tables before each test for complete isolation.

    Function-scoped (default) so every test starts with a clean slate regardless
    of what previous tests committed. Fast for SQLite in-memory.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db(setup_database: None) -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
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
