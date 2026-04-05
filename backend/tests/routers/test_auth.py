from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import Invitation
from app.models.user import ROLE_ORG_MANAGER, User
from app.services.auth_service import create_access_token, hash_password


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db: AsyncSession) -> None:
    user = User(
        email="login@test.dev",
        hashed_password=hash_password("correctpassword"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@test.dev", "password": "correctpassword"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login@test.dev"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db: AsyncSession) -> None:
    user = User(
        email="wrong@test.dev",
        hashed_password=hash_password("correctpassword"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@test.dev", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.dev", "password": "whatever"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db: AsyncSession) -> None:
    user = User(
        email="inactive@test.dev",
        hashed_password=hash_password("password"),
        role="admin",
        is_active=False,
    )
    db.add(user)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@test.dev", "password": "password"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_from_invite(client: AsyncClient, db: AsyncSession, pending_invite: Invitation) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        params={"invite_token": pending_invite.token},
        json={"password": "NewPassword1!"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == pending_invite.email
    assert data["user"]["role"] == ROLE_ORG_MANAGER
    assert "access_token" in data

    # Invitation should be marked accepted
    await db.refresh(pending_invite)
    assert pending_invite.accepted_at is not None


@pytest.mark.asyncio
async def test_register_invite_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        params={"invite_token": "doesnotexist"},
        json={"password": "Password1!"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_register_invite_already_accepted(
    client: AsyncClient, db: AsyncSession, pending_invite: Invitation
) -> None:
    pending_invite.accepted_at = datetime.now(UTC)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/register",
        params={"invite_token": pending_invite.token},
        json={"password": "Password1!"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_invite_expired(client: AsyncClient, db: AsyncSession, pending_invite: Invitation) -> None:
    pending_invite.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/register",
        params={"invite_token": pending_invite.token},
        json={"password": "Password1!"},
    )
    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, admin_user: User, admin_token: str) -> None:
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(admin_user.id)
    assert data["email"] == admin_user.email
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_get_me_missing_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer notavalidtoken"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_inactive_user(client: AsyncClient, db: AsyncSession) -> None:
    user = User(
        email="deactivated@test.dev",
        hashed_password=hash_password("password"),
        role="admin",
        is_active=False,
    )
    db.add(user)
    await db.commit()
    token = create_access_token(user.id, user.role, None)

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401
