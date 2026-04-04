"""
Integration tests — full API surface against a real PostgreSQL container.

Each test operates on a clean database (setup_integration_db fixture runs
drop_all + create_all before every test).

Coverage:
  - Health check
  - Authentication (missing / wrong API key)
  - Organizations: create, conflict, get, 404, list assessments
  - Assessments: create, get, list, process trigger, config update
  - Documents: upload (mocked S3), list, get, 404, wrong type, too large
  - Scores: complete assessment, pending assessment, not found
  - Reports: redirect, 404
"""

from io import BytesIO
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.organization import Organization

# ===========================================================================
# Helpers
# ===========================================================================


async def _create_org(client: AsyncClient, slug: str = "integration-org") -> dict:
    resp = await client.post("/api/v1/organizations", json={"name": "Integration Org", "slug": slug})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_assessment(client: AsyncClient, org_id: str) -> dict:
    resp = await client.post("/api/v1/assessments", json={"organization_id": org_id})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_complete_assessment(db: AsyncSession) -> str:
    """Insert a complete assessment directly into the DB for score tests."""
    import uuid

    org = Organization(name="ScoreOrg", slug=f"score-{uuid.uuid4().hex[:8]}")
    db.add(org)
    await db.flush()

    dim_score = {"score": 60.0, "max_score": 100.0, "flags": []}
    assessment = Assessment(
        organization_id=org.id,
        status="complete",
        overall_score=60.0,
        risk_tier="medium",
        dimension_scores={
            dim: dict(dim_score)
            for dim in [
                "model_inventory",
                "human_oversight",
                "bias_fairness",
                "data_governance",
                "incident_response",
                "monitoring_drift",
                "regulatory_compliance",
                "third_party_risk",
            ]
        },
        flags={"all_flags": [{"severity": "warning", "text": "Test flag", "dimension": "model_inventory"}]},
    )
    db.add(assessment)
    await db.commit()
    return str(assessment.id)


# ===========================================================================
# Health
# ===========================================================================


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ===========================================================================
# Authentication
# ===========================================================================


@pytest.mark.asyncio
async def test_no_api_key_returns_401(unauthed_client: AsyncClient) -> None:
    resp = await unauthed_client.get("/api/v1/organizations/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_api_key_returns_401(unauthed_client: AsyncClient) -> None:
    resp = await unauthed_client.get(
        "/api/v1/organizations/00000000-0000-0000-0000-000000000000",
        headers={"X-API-Key": "definitely-wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_does_not_require_api_key(unauthed_client: AsyncClient) -> None:
    resp = await unauthed_client.get("/health")
    assert resp.status_code == 200


# ===========================================================================
# Organizations
# ===========================================================================


@pytest.mark.asyncio
async def test_create_organization_success(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Acme Corp", "slug": "acme-corp"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "acme-corp"
    assert data["name"] == "Acme Corp"
    assert UUID(data["id"])  # valid UUID


@pytest.mark.asyncio
async def test_create_organization_slug_conflict(client: AsyncClient) -> None:
    await client.post("/api/v1/organizations", json={"name": "Org A", "slug": "dup-slug"})
    resp = await client.post("/api/v1/organizations", json={"name": "Org B", "slug": "dup-slug"})
    assert resp.status_code == 409
    assert "dup-slug" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_organization_success(client: AsyncClient) -> None:
    org = await _create_org(client, "get-org-integ")
    resp = await client.get(f"/api/v1/organizations/{org['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == org["id"]
    assert resp.json()["slug"] == "get-org-integ"


@pytest.mark.asyncio
async def test_get_organization_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/organizations/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_org_assessments_empty(client: AsyncClient) -> None:
    org = await _create_org(client, "list-assmt-org")
    resp = await client.get(f"/api/v1/organizations/{org['id']}/assessments")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_org_assessments_with_data(client: AsyncClient) -> None:
    org = await _create_org(client, "list-assmt-with-data")
    await _create_assessment(client, org["id"])
    await _create_assessment(client, org["id"])
    resp = await client.get(f"/api/v1/organizations/{org['id']}/assessments")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_org_assessments_org_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/organizations/00000000-0000-0000-0000-000000000000/assessments")
    assert resp.status_code == 404


# ===========================================================================
# Assessments
# ===========================================================================


@pytest.mark.asyncio
async def test_create_assessment_success(client: AsyncClient) -> None:
    org = await _create_org(client, "create-assmt-org")
    resp = await client.post("/api/v1/assessments", json={"organization_id": org["id"]})
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert UUID(data["id"])


@pytest.mark.asyncio
async def test_create_assessment_org_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/assessments",
        json={"organization_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_assessment_success(client: AsyncClient) -> None:
    org = await _create_org(client, "get-assmt-org")
    assmt = await _create_assessment(client, org["id"])
    resp = await client.get(f"/api/v1/assessments/{assmt['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == assmt["id"]


@pytest.mark.asyncio
async def test_get_assessment_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/assessments/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_assessments(client: AsyncClient) -> None:
    org = await _create_org(client, "list-assmt-all")
    await _create_assessment(client, org["id"])
    resp = await client.get("/api/v1/assessments")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_list_assessments_filter_by_org(client: AsyncClient) -> None:
    org_a = await _create_org(client, "filter-org-a")
    org_b = await _create_org(client, "filter-org-b")
    await _create_assessment(client, org_a["id"])
    await _create_assessment(client, org_b["id"])

    resp = await client.get(f"/api/v1/assessments?org_id={org_a['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["organization_id"] == org_a["id"]


@pytest.mark.asyncio
async def test_trigger_process_success(client: AsyncClient) -> None:
    org = await _create_org(client, "proc-trigger-org")
    assmt = await _create_assessment(client, org["id"])

    with patch("app.workers.tasks.run_pipeline_task", new_callable=AsyncMock):
        resp = await client.post(f"/api/v1/assessments/{assmt['id']}/process")
    assert resp.status_code == 200
    assert resp.json()["status"] == "processing"


@pytest.mark.asyncio
async def test_trigger_process_not_found(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/assessments/00000000-0000-0000-0000-000000000000/process")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_trigger_process_already_processing(client: AsyncClient) -> None:
    org = await _create_org(client, "already-proc-org")
    assmt = await _create_assessment(client, org["id"])

    with patch("app.workers.tasks.run_pipeline_task", new_callable=AsyncMock):
        await client.post(f"/api/v1/assessments/{assmt['id']}/process")
        # Second trigger while processing
        resp = await client.post(f"/api/v1/assessments/{assmt['id']}/process")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_assessment_config(client: AsyncClient) -> None:
    org = await _create_org(client, "config-update-org")
    assmt = await _create_assessment(client, org["id"])
    config = {"weights": {"human_oversight": 0.25, "bias_fairness": 0.20}}

    resp = await client.put(
        f"/api/v1/assessments/{assmt['id']}/config",
        json={"assessment_config": config},
    )
    assert resp.status_code == 200
    assert resp.json()["assessment_config"] == config


@pytest.mark.asyncio
async def test_update_assessment_config_not_found(client: AsyncClient) -> None:
    resp = await client.put(
        "/api/v1/assessments/00000000-0000-0000-0000-000000000000/config",
        json={"assessment_config": {}},
    )
    assert resp.status_code == 404


# ===========================================================================
# Documents
# ===========================================================================


@pytest.mark.asyncio
async def test_upload_document_success(client: AsyncClient) -> None:
    org = await _create_org(client, "doc-upload-org")
    assmt = await _create_assessment(client, org["id"])

    with (
        patch("app.routers.documents.upload_bytes", new_callable=AsyncMock),
        patch("app.workers.tasks.process_document_task", new_callable=AsyncMock),
    ):
        resp = await client.post(
            f"/api/v1/assessments/{assmt['id']}/documents",
            files={"file": ("policy.txt", BytesIO(b"HITL policy content"), "text/plain")},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["filename"] == "policy.txt"
    assert data["status"] == "pending"
    assert UUID(data["id"])


@pytest.mark.asyncio
async def test_upload_document_wrong_content_type(client: AsyncClient) -> None:
    org = await _create_org(client, "doc-wrongtype-org")
    assmt = await _create_assessment(client, org["id"])

    resp = await client.post(
        f"/api/v1/assessments/{assmt['id']}/documents",
        files={"file": ("data.csv", BytesIO(b"a,b,c"), "text/csv")},
    )
    assert resp.status_code == 422
    assert "Unsupported file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_document_too_large(client: AsyncClient) -> None:
    org = await _create_org(client, "doc-toobig-org")
    assmt = await _create_assessment(client, org["id"])

    big = b"x" * (50 * 1024 * 1024 + 1)
    with patch("app.routers.documents.upload_bytes", new_callable=AsyncMock):
        resp = await client.post(
            f"/api/v1/assessments/{assmt['id']}/documents",
            files={"file": ("big.txt", BytesIO(big), "text/plain")},
        )
    assert resp.status_code == 422
    assert "50 MB" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_document_assessment_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/assessments/00000000-0000-0000-0000-000000000000/documents",
        files={"file": ("policy.txt", BytesIO(b"data"), "text/plain")},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_document_s3_failure(client: AsyncClient) -> None:
    from app.services.storage import StorageError

    org = await _create_org(client, "doc-s3fail-org")
    assmt = await _create_assessment(client, org["id"])

    with patch(
        "app.routers.documents.upload_bytes",
        new_callable=AsyncMock,
        side_effect=StorageError("S3 is down"),
    ):
        resp = await client.post(
            f"/api/v1/assessments/{assmt['id']}/documents",
            files={"file": ("policy.txt", BytesIO(b"data"), "text/plain")},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_list_documents_empty(client: AsyncClient) -> None:
    org = await _create_org(client, "list-docs-empty-org")
    assmt = await _create_assessment(client, org["id"])
    resp = await client.get(f"/api/v1/assessments/{assmt['id']}/documents")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_documents_with_data(client: AsyncClient) -> None:
    org = await _create_org(client, "list-docs-data-org")
    assmt = await _create_assessment(client, org["id"])

    with (
        patch("app.routers.documents.upload_bytes", new_callable=AsyncMock),
        patch("app.workers.tasks.process_document_task", new_callable=AsyncMock),
    ):
        await client.post(
            f"/api/v1/assessments/{assmt['id']}/documents",
            files={"file": ("doc1.txt", BytesIO(b"content"), "text/plain")},
        )
        await client.post(
            f"/api/v1/assessments/{assmt['id']}/documents",
            files={"file": ("doc2.txt", BytesIO(b"content"), "text/plain")},
        )

    resp = await client.get(f"/api/v1/assessments/{assmt['id']}/documents")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_documents_assessment_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/assessments/00000000-0000-0000-0000-000000000000/documents")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_document_success(client: AsyncClient) -> None:
    org = await _create_org(client, "get-doc-ok-org")
    assmt = await _create_assessment(client, org["id"])

    with (
        patch("app.routers.documents.upload_bytes", new_callable=AsyncMock),
        patch("app.workers.tasks.process_document_task", new_callable=AsyncMock),
    ):
        upload = await client.post(
            f"/api/v1/assessments/{assmt['id']}/documents",
            files={"file": ("found.txt", BytesIO(b"content"), "text/plain")},
        )
    doc_id = upload.json()["id"]

    resp = await client.get(f"/api/v1/assessments/{assmt['id']}/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id
    assert resp.json()["filename"] == "found.txt"


@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient) -> None:
    org = await _create_org(client, "get-doc-404-org")
    assmt = await _create_assessment(client, org["id"])
    resp = await client.get(f"/api/v1/assessments/{assmt['id']}/documents/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ===========================================================================
# Scores
# ===========================================================================


@pytest.mark.asyncio
async def test_get_scores_complete_assessment(client: AsyncClient, db: AsyncSession) -> None:
    a_id = await _create_complete_assessment(db)
    resp = await client.get(f"/api/v1/assessments/{a_id}/scores")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_score"] == 60.0
    assert data["risk_tier"] == "medium"
    assert len(data["dimensions"]) == 8
    assert len(data["all_flags"]) == 1
    assert data["all_flags"][0]["severity"] == "warning"


@pytest.mark.asyncio
async def test_get_scores_pending_assessment(client: AsyncClient) -> None:
    org = await _create_org(client, "scores-pending-org")
    assmt = await _create_assessment(client, org["id"])
    resp = await client.get(f"/api/v1/assessments/{assmt['id']}/scores")
    assert resp.status_code == 404
    assert "not complete" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_scores_assessment_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/assessments/00000000-0000-0000-0000-000000000000/scores")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_scores_complete_but_no_dimension_scores(client: AsyncClient, db: AsyncSession) -> None:
    """A complete assessment with no dimension_scores returns 404."""
    import uuid

    org = Organization(name="NoScoreOrg", slug=f"no-score-{uuid.uuid4().hex[:8]}")
    db.add(org)
    await db.flush()
    assessment = Assessment(
        organization_id=org.id,
        status="complete",
        overall_score=None,
        risk_tier=None,
        dimension_scores=None,
    )
    db.add(assessment)
    await db.commit()

    resp = await client.get(f"/api/v1/assessments/{assessment.id}/scores")
    assert resp.status_code == 404
    assert "No scores" in resp.json()["detail"]


# ===========================================================================
# Reports
# ===========================================================================


@pytest.mark.asyncio
async def test_get_report_not_found(client: AsyncClient) -> None:
    org = await _create_org(client, "report-404-org")
    assmt = await _create_assessment(client, org["id"])
    resp = await client.get(
        f"/api/v1/assessments/{assmt['id']}/report",
        follow_redirects=False,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_report_assessment_not_found(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/assessments/00000000-0000-0000-0000-000000000000/report",
        follow_redirects=False,
    )
    assert resp.status_code == 404
