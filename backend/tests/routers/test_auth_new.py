"""
Tests for new auth endpoints: password reset and signup.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import Invitation
from app.models.organization import Organization
from app.models.password_reset import PasswordResetToken
from app.models.user import ROLE_ORG_MANAGER, ROLE_ORG_UNDERWRITER, User
from app.services.auth_service import hash_password

# ---------------------------------------------------------------------------
# Password Reset - Request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_password_reset_request_existing_user(client: AsyncClient, db: AsyncSession) -> None:
    """Returns 204 and sends email when user exists."""
    user = User(
        email="reset@test.dev",
        hashed_password=hash_password("oldpassword"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()

    with patch("app.services.email_service.send_password_reset_code") as mock_send:
        resp = await client.post("/api/v1/auth/password-reset/request", json={"email": "reset@test.dev"})

    assert resp.status_code == 204
    mock_send.assert_called_once()
    # Check token was stored
    from sqlalchemy import select

    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.email == "reset@test.dev"))
    token = result.scalar_one_or_none()
    assert token is not None
    assert token.used_at is None


@pytest.mark.asyncio
async def test_password_reset_request_unknown_email(client: AsyncClient) -> None:
    """Returns 204 even when email doesn't exist (no enumeration)."""
    with patch("app.services.email_service.send_password_reset_code") as mock_send:
        resp = await client.post("/api/v1/auth/password-reset/request", json={"email": "nobody@test.dev"})

    assert resp.status_code == 204
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_password_reset_request_inactive_user(client: AsyncClient, db: AsyncSession) -> None:
    """Inactive users don't get a code."""
    user = User(
        email="inactive@test.dev",
        hashed_password=hash_password("oldpassword"),
        role="admin",
        is_active=False,
    )
    db.add(user)
    await db.commit()

    with patch("app.services.email_service.send_password_reset_code") as mock_send:
        resp = await client.post("/api/v1/auth/password-reset/request", json={"email": "inactive@test.dev"})

    assert resp.status_code == 204
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Password Reset - Confirm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_password_reset_confirm_success(client: AsyncClient, db: AsyncSession) -> None:
    """Valid code + email resets the password."""
    user = User(
        email="confirm@test.dev",
        hashed_password=hash_password("oldpassword"),
        role="admin",
        is_active=True,
    )
    db.add(user)

    code = "123456"
    token = PasswordResetToken(
        email="confirm@test.dev",
        code_hash=hash_password(code),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db.add(token)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "confirm@test.dev", "code": code, "new_password": "NewPassword1!"},
    )
    assert resp.status_code == 204

    # Token should be marked used
    await db.refresh(token)
    assert token.used_at is not None

    # Can now login with new password
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "confirm@test.dev", "password": "NewPassword1!"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_confirm_wrong_code(client: AsyncClient, db: AsyncSession) -> None:
    user = User(
        email="wrongcode@test.dev",
        hashed_password=hash_password("oldpassword"),
        role="admin",
        is_active=True,
    )
    db.add(user)

    token = PasswordResetToken(
        email="wrongcode@test.dev",
        code_hash=hash_password("999999"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db.add(token)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "wrongcode@test.dev", "code": "000000", "new_password": "NewPassword1!"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_confirm_expired(client: AsyncClient, db: AsyncSession) -> None:
    user = User(
        email="expired@test.dev",
        hashed_password=hash_password("oldpassword"),
        role="admin",
        is_active=True,
    )
    db.add(user)

    code = "123456"
    token = PasswordResetToken(
        email="expired@test.dev",
        code_hash=hash_password(code),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),  # already expired
    )
    db.add(token)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "expired@test.dev", "code": code, "new_password": "NewPassword1!"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_confirm_short_password(client: AsyncClient, db: AsyncSession) -> None:
    user = User(
        email="short@test.dev",
        hashed_password=hash_password("oldpassword"),
        role="admin",
        is_active=True,
    )
    db.add(user)

    code = "123456"
    token = PasswordResetToken(
        email="short@test.dev",
        code_hash=hash_password(code),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db.add(token)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "short@test.dev", "code": code, "new_password": "abc"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Invitation Info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invitation_info_success(client: AsyncClient, db: AsyncSession) -> None:
    org = Organization(name="Test Org", slug="test-org-inv")
    db.add(org)
    admin = User(email="admin@test.dev", hashed_password=hash_password("pw"), role="admin", is_active=True)
    db.add(admin)
    await db.flush()

    inv = Invitation(
        email="manager@test.dev",
        role=ROLE_ORG_MANAGER,
        organization_id=org.id,
        token="invinfo123",
        invited_by_id=admin.id,
        expires_at=datetime.now(UTC) + timedelta(hours=48),
    )
    db.add(inv)
    await db.commit()

    resp = await client.get("/api/v1/auth/invitation-info", params={"token": "invinfo123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "manager@test.dev"
    assert data["role"] == ROLE_ORG_MANAGER
    assert data["org_name"] == "Test Org"


@pytest.mark.asyncio
async def test_invitation_info_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/invitation-info", params={"token": "doesnotexist"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invitation_info_expired(client: AsyncClient, db: AsyncSession) -> None:
    admin = User(email="admin2@test.dev", hashed_password=hash_password("pw"), role="admin", is_active=True)
    db.add(admin)
    await db.flush()

    inv = Invitation(
        email="user@test.dev",
        role=ROLE_ORG_UNDERWRITER,
        organization_id=None,
        token="expiredtoken",
        invited_by_id=admin.id,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db.add(inv)
    await db.commit()

    resp = await client.get("/api/v1/auth/invitation-info", params={"token": "expiredtoken"})
    assert resp.status_code == 410


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signup_org_manager_creates_org(client: AsyncClient, db: AsyncSession) -> None:
    admin = User(email="admin3@test.dev", hashed_password=hash_password("pw"), role="admin", is_active=True)
    db.add(admin)
    await db.flush()

    inv = Invitation(
        email="newmgr@test.dev",
        role=ROLE_ORG_MANAGER,
        organization_id=None,  # no org yet - will be created
        token="signuptoken1",
        invited_by_id=admin.id,
        expires_at=datetime.now(UTC) + timedelta(hours=48),
    )
    db.add(inv)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "token": "signuptoken1",
            "password": "SecurePass1!",
            "first_name": "Jane",
            "last_name": "Smith",
            "org": {"name": "New MGA", "slug": "new-mga", "tier": "tier_1"},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == "newmgr@test.dev"
    assert data["user"]["role"] == ROLE_ORG_MANAGER
    assert data["user"]["organization_id"] is not None

    # Org should exist
    from sqlalchemy import select

    org_result = await db.execute(select(Organization).where(Organization.slug == "new-mga"))
    org = org_result.scalar_one_or_none()
    assert org is not None
    assert org.tier == "tier_1"


@pytest.mark.asyncio
async def test_signup_underwriter_joins_existing_org(client: AsyncClient, db: AsyncSession) -> None:
    admin = User(email="admin4@test.dev", hashed_password=hash_password("pw"), role="admin", is_active=True)
    db.add(admin)
    org = Organization(name="Existing Org", slug="existing-org")
    db.add(org)
    await db.flush()

    inv = Invitation(
        email="newuw@test.dev",
        role=ROLE_ORG_UNDERWRITER,
        organization_id=org.id,
        token="signuptoken2",
        invited_by_id=admin.id,
        expires_at=datetime.now(UTC) + timedelta(hours=48),
    )
    db.add(inv)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/signup",
        json={"token": "signuptoken2", "password": "SecurePass1!", "first_name": "Bob"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["role"] == ROLE_ORG_UNDERWRITER
    assert data["user"]["organization_id"] == str(org.id)


@pytest.mark.asyncio
async def test_signup_org_manager_missing_org_data(client: AsyncClient, db: AsyncSession) -> None:
    admin = User(email="admin5@test.dev", hashed_password=hash_password("pw"), role="admin", is_active=True)
    db.add(admin)
    await db.flush()

    inv = Invitation(
        email="mgr2@test.dev",
        role=ROLE_ORG_MANAGER,
        organization_id=None,
        token="signuptoken3",
        invited_by_id=admin.id,
        expires_at=datetime.now(UTC) + timedelta(hours=48),
    )
    db.add(inv)
    await db.commit()

    # No org payload - should fail
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"token": "signuptoken3", "password": "SecurePass1!"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_signup_short_password(client: AsyncClient, db: AsyncSession) -> None:
    admin = User(email="admin6@test.dev", hashed_password=hash_password("pw"), role="admin", is_active=True)
    db.add(admin)
    await db.flush()

    inv = Invitation(
        email="user@test.dev",
        role=ROLE_ORG_UNDERWRITER,
        organization_id=None,
        token="signuptoken4",
        invited_by_id=admin.id,
        expires_at=datetime.now(UTC) + timedelta(hours=48),
    )
    db.add(inv)
    await db.commit()

    resp = await client.post("/api/v1/auth/signup", json={"token": "signuptoken4", "password": "short"})
    assert resp.status_code == 422
