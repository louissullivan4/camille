import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.organization import Organization
from app.models.user import User


@pytest.mark.asyncio
async def test_list_all_users_as_admin(
    client: AsyncClient,
    admin_user: User,
    manager_user: User,
    admin_token: str,
) -> None:
    resp = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    emails = [u["email"] for u in data["users"]]
    assert admin_user.email in emails
    assert manager_user.email in emails


@pytest.mark.asyncio
async def test_list_all_users_forbidden_for_manager(client: AsyncClient, manager_token: str) -> None:
    resp = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_all_users_filter_by_role(
    client: AsyncClient, admin_user: User, manager_user: User, admin_token: str
) -> None:
    resp = await client.get(
        "/api/v1/users",
        params={"role": "org_manager"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for u in data["users"]:
        assert u["role"] == "org_manager"


@pytest.mark.asyncio
async def test_deactivate_user(client: AsyncClient, db: AsyncSession, admin_token: str, manager_user: User) -> None:
    resp = await client.patch(
        f"/api/v1/users/{manager_user.id}/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    await db.refresh(manager_user)
    assert manager_user.is_active is False


@pytest.mark.asyncio
async def test_deactivate_user_not_found(client: AsyncClient, admin_token: str) -> None:
    resp = await client.patch(
        "/api/v1/users/00000000-0000-0000-0000-000000000000/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_org_users_as_manager(
    client: AsyncClient,
    org: Organization,
    manager_user: User,
    underwriter_user: User,
    manager_token: str,
) -> None:
    resp = await client.get(
        f"/api/v1/users/org/{org.id}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data["users"]]
    assert manager_user.email in emails
    assert underwriter_user.email in emails


@pytest.mark.asyncio
async def test_list_org_users_wrong_org_forbidden(client: AsyncClient, db: AsyncSession, manager_token: str) -> None:
    other_org = Organization(name="Other Org", slug="other-org-users")
    db.add(other_org)
    await db.commit()

    resp = await client.get(
        f"/api/v1/users/org/{other_org.id}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_grant_assessment_access(
    client: AsyncClient,
    db: AsyncSession,
    org: Organization,
    manager_user: User,
    underwriter_user: User,
    manager_token: str,
) -> None:
    assessment = Assessment(organization_id=org.id, status="complete")
    db.add(assessment)
    await db.commit()

    resp = await client.post(
        f"/api/v1/users/org/{org.id}/assessments/{assessment.id}/grant",
        json={"user_id": str(underwriter_user.id)},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["granted"] is True
    assert data["user_id"] == str(underwriter_user.id)


@pytest.mark.asyncio
async def test_grant_access_duplicate_is_409(
    client: AsyncClient,
    db: AsyncSession,
    org: Organization,
    underwriter_user: User,
    manager_token: str,
) -> None:
    assessment = Assessment(organization_id=org.id, status="complete")
    db.add(assessment)
    await db.commit()

    await client.post(
        f"/api/v1/users/org/{org.id}/assessments/{assessment.id}/grant",
        json={"user_id": str(underwriter_user.id)},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    resp = await client.post(
        f"/api/v1/users/org/{org.id}/assessments/{assessment.id}/grant",
        json={"user_id": str(underwriter_user.id)},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_grant_access_wrong_role_fails(
    client: AsyncClient,
    db: AsyncSession,
    org: Organization,
    manager_user: User,
    manager_token: str,
) -> None:
    """Cannot grant access to a manager - only underwriters."""
    assessment = Assessment(organization_id=org.id, status="complete")
    db.add(assessment)
    await db.commit()

    resp = await client.post(
        f"/api/v1/users/org/{org.id}/assessments/{assessment.id}/grant",
        json={"user_id": str(manager_user.id)},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_revoke_assessment_access(
    client: AsyncClient,
    db: AsyncSession,
    org: Organization,
    underwriter_user: User,
    manager_token: str,
) -> None:
    assessment = Assessment(organization_id=org.id, status="complete")
    db.add(assessment)
    await db.commit()

    # Grant first
    await client.post(
        f"/api/v1/users/org/{org.id}/assessments/{assessment.id}/grant",
        json={"user_id": str(underwriter_user.id)},
        headers={"Authorization": f"Bearer {manager_token}"},
    )

    # Then revoke
    resp = await client.delete(
        f"/api/v1/users/org/{org.id}/assessments/{assessment.id}/grant/{underwriter_user.id}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_revoke_access_not_found(
    client: AsyncClient,
    db: AsyncSession,
    org: Organization,
    underwriter_user: User,
    manager_token: str,
) -> None:
    assessment = Assessment(organization_id=org.id, status="complete")
    db.add(assessment)
    await db.commit()

    resp = await client.delete(
        f"/api/v1/users/org/{org.id}/assessments/{assessment.id}/grant/{underwriter_user.id}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 404
