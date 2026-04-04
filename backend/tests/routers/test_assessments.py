from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient


async def _create_org(client: AsyncClient, slug: str = "assess-org") -> str:
    resp = await client.post(
        "/api/v1/organizations", json={"name": "Assess Org", "slug": slug}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_assessment(client: AsyncClient) -> None:
    org_id = await _create_org(client, "ao-create")
    resp = await client.post("/api/v1/assessments", json={"organization_id": org_id})
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["organization_id"] == org_id


@pytest.mark.asyncio
async def test_create_assessment_invalid_org(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/assessments",
        json={"organization_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_assessment(client: AsyncClient) -> None:
    org_id = await _create_org(client, "ao-get")
    create = await client.post("/api/v1/assessments", json={"organization_id": org_id})
    a_id = create.json()["id"]
    resp = await client.get(f"/api/v1/assessments/{a_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == a_id


@pytest.mark.asyncio
async def test_get_assessment_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/assessments/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_assessments(client: AsyncClient) -> None:
    org_id = await _create_org(client, "ao-list")
    await client.post("/api/v1/assessments", json={"organization_id": org_id})
    resp = await client.get(f"/api/v1/assessments?org_id={org_id}")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_update_config(client: AsyncClient) -> None:
    org_id = await _create_org(client, "ao-config")
    create = await client.post("/api/v1/assessments", json={"organization_id": org_id})
    a_id = create.json()["id"]
    resp = await client.put(
        f"/api/v1/assessments/{a_id}/config",
        json={"assessment_config": {"weight_overrides": {"model_inventory": 0.20}}},
    )
    assert resp.status_code == 200
    assert resp.json()["assessment_config"]["weight_overrides"]["model_inventory"] == 0.20


@pytest.mark.asyncio
async def test_process_trigger_mocked(client: AsyncClient) -> None:
    org_id = await _create_org(client, "ao-proc")
    create = await client.post("/api/v1/assessments", json={"organization_id": org_id})
    a_id = create.json()["id"]

    with patch("app.workers.tasks.run_pipeline_task", new_callable=AsyncMock):
        resp = await client.post(f"/api/v1/assessments/{a_id}/process")
    assert resp.status_code == 200
    assert resp.json()["status"] == "processing"


@pytest.mark.asyncio
async def test_process_trigger_409_if_already_processing(client: AsyncClient) -> None:
    org_id = await _create_org(client, "ao-409")
    create = await client.post("/api/v1/assessments", json={"organization_id": org_id})
    a_id = create.json()["id"]

    with patch("app.workers.tasks.run_pipeline_task", new_callable=AsyncMock):
        await client.post(f"/api/v1/assessments/{a_id}/process")
        resp = await client.post(f"/api/v1/assessments/{a_id}/process")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_assessments_filter_by_status(client: AsyncClient) -> None:
    org_id = await _create_org(client, "ao-status-filter")
    await client.post("/api/v1/assessments", json={"organization_id": org_id})
    resp = await client.get(f"/api/v1/assessments?org_id={org_id}&status=pending")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(a["status"] == "pending" for a in data)


@pytest.mark.asyncio
async def test_process_trigger_404_if_not_found(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/assessments/00000000-0000-0000-0000-000000000000/process")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_process_trigger_409_if_already_complete(client: AsyncClient, db) -> None:
    from app.models.assessment import Assessment
    from app.models.organization import Organization
    import uuid
    org = Organization(name="CompleteOrg", slug=f"complete-{uuid.uuid4().hex[:6]}")
    db.add(org)
    await db.flush()
    assessment = Assessment(organization_id=org.id, status="complete")
    db.add(assessment)
    await db.commit()
    resp = await client.post(f"/api/v1/assessments/{assessment.id}/process")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_config_404_if_not_found(client: AsyncClient) -> None:
    resp = await client.put(
        "/api/v1/assessments/00000000-0000-0000-0000-000000000000/config",
        json={"assessment_config": {}},
    )
    assert resp.status_code == 404
