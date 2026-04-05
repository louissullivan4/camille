import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_organization(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Test Org", "slug": "test-org"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "test-org"
    assert data["name"] == "Test Org"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_organization_slug_conflict(client: AsyncClient) -> None:
    await client.post("/api/v1/organizations", json={"name": "Org A", "slug": "conflict-slug"})
    resp = await client.post("/api/v1/organizations", json={"name": "Org B", "slug": "conflict-slug"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_organization(client: AsyncClient) -> None:
    create = await client.post("/api/v1/organizations", json={"name": "GetOrg", "slug": "get-org-unique"})
    org_id = create.json()["id"]
    resp = await client.get(f"/api/v1/organizations/{org_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == org_id


@pytest.mark.asyncio
async def test_get_organization_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/organizations/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_org_assessments(client: AsyncClient) -> None:
    org = await client.post("/api/v1/organizations", json={"name": "ListOrg", "slug": "list-org-unique"})
    org_id = org.json()["id"]
    resp = await client.get(f"/api/v1/organizations/{org_id}/assessments")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_org_assessments_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/organizations/00000000-0000-0000-0000-000000000000/assessments")
    assert resp.status_code == 404
