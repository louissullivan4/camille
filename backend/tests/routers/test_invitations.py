import pytest
from httpx import AsyncClient

from app.models.organization import Organization
from app.models.user import User


@pytest.mark.asyncio
async def test_invite_admin(client: AsyncClient, admin_user: User, admin_token: str) -> None:
    resp = await client.post(
        "/api/v1/invitations/admin",
        json={"email": "newadmin@test.dev"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newadmin@test.dev"
    assert data["role"] == "admin"
    assert data["organization_id"] is None
    assert "token" in data


@pytest.mark.asyncio
async def test_invite_admin_requires_admin_role(client: AsyncClient, manager_token: str) -> None:
    resp = await client.post(
        "/api/v1/invitations/admin",
        json={"email": "x@test.dev"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invite_manager_creates_org(client: AsyncClient, admin_user: User, admin_token: str) -> None:
    resp = await client.post(
        "/api/v1/invitations/manager",
        json={"email": "mgr@neworg.dev", "org_name": "New Org", "org_slug": "new-org-slug"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "mgr@neworg.dev"
    assert data["role"] == "org_manager"
    assert data["organization_id"] is not None


@pytest.mark.asyncio
async def test_invite_manager_missing_org_details(client: AsyncClient, admin_token: str) -> None:
    resp = await client.post(
        "/api/v1/invitations/manager",
        json={"email": "mgr@test.dev"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invite_manager_existing_org(client: AsyncClient, admin_token: str, org: Organization) -> None:
    resp = await client.post(
        "/api/v1/invitations/manager",
        json={"email": "mgr2@test.dev", "organization_id": str(org.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["organization_id"] == str(org.id)


@pytest.mark.asyncio
async def test_invite_manager_org_not_found(client: AsyncClient, admin_token: str) -> None:
    resp = await client.post(
        "/api/v1/invitations/manager",
        json={
            "email": "mgr@test.dev",
            "organization_id": "00000000-0000-0000-0000-000000000000",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invite_manager_slug_conflict(client: AsyncClient, admin_token: str, org: Organization) -> None:
    resp = await client.post(
        "/api/v1/invitations/manager",
        json={"email": "mgr@test.dev", "org_name": "Dupe", "org_slug": org.slug},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_invite_underwriter_by_manager(client: AsyncClient, manager_user: User, manager_token: str) -> None:
    resp = await client.post(
        "/api/v1/invitations/underwriter",
        json={"email": "uw@test.dev"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "uw@test.dev"
    assert data["role"] == "org_underwriter"
    assert data["organization_id"] == str(manager_user.organization_id)


@pytest.mark.asyncio
async def test_invite_underwriter_requires_manager_or_admin(client: AsyncClient, underwriter_token: str) -> None:
    resp = await client.post(
        "/api/v1/invitations/underwriter",
        json={"email": "uw2@test.dev"},
        headers={"Authorization": f"Bearer {underwriter_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_invitation_by_token(client: AsyncClient, pending_invite: object) -> None:
    resp = await client.get("/api/v1/invitations/validtoken123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] == "validtoken123"


@pytest.mark.asyncio
async def test_get_invitation_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/invitations/nosuchtoken")
    assert resp.status_code == 404
