"""
Shared fixtures for router tests that need authenticated users.
"""

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import Invitation
from app.models.organization import Organization
from app.models.user import ROLE_ADMIN, ROLE_ORG_MANAGER, ROLE_ORG_UNDERWRITER, User
from app.services.auth_service import create_access_token, hash_password


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def org(db: AsyncSession) -> Organization:
    o = Organization(name="Test Org", slug="test-org-rbac")
    db.add(o)
    await db.commit()
    await db.refresh(o)
    return o


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> User:
    u = User(
        email="admin@test.dev",
        hashed_password=hash_password("password"),
        role=ROLE_ADMIN,
        organization_id=None,
        is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def manager_user(db: AsyncSession, org: Organization) -> User:
    u = User(
        email="manager@test.dev",
        hashed_password=hash_password("password"),
        role=ROLE_ORG_MANAGER,
        organization_id=org.id,
        is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def underwriter_user(db: AsyncSession, org: Organization) -> User:
    u = User(
        email="underwriter@test.dev",
        hashed_password=hash_password("password"),
        role=ROLE_ORG_UNDERWRITER,
        organization_id=org.id,
        is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
def admin_token(admin_user: User) -> str:
    return create_access_token(admin_user.id, admin_user.role, admin_user.organization_id)


@pytest_asyncio.fixture
def manager_token(manager_user: User) -> str:
    return create_access_token(manager_user.id, manager_user.role, manager_user.organization_id)


@pytest_asyncio.fixture
def underwriter_token(underwriter_user: User) -> str:
    return create_access_token(underwriter_user.id, underwriter_user.role, underwriter_user.organization_id)


@pytest_asyncio.fixture
async def pending_invite(db: AsyncSession, admin_user: User, org: Organization) -> Invitation:
    """A valid, unaccepted manager invitation."""
    inv = Invitation(
        email="newmanager@test.dev",
        role=ROLE_ORG_MANAGER,
        organization_id=org.id,
        token="validtoken123",
        invited_by_id=admin_user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=72),
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv
