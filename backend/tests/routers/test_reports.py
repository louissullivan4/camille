from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.organization import Organization


async def _make_assessment_with_report(db: AsyncSession, report_url: str | None) -> str:
    import uuid

    org = Organization(name="RepOrg", slug=f"rep-org-{uuid.uuid4().hex[:8]}")
    db.add(org)
    await db.flush()
    assessment = Assessment(
        organization_id=org.id,
        status="complete",
        report_url=report_url,
    )
    db.add(assessment)
    await db.commit()
    return str(assessment.id)


@pytest.mark.asyncio
async def test_get_report_redirects(client: AsyncClient, db: AsyncSession) -> None:
    a_id = await _make_assessment_with_report(db, "assessments/some-key/report.pdf")
    with patch(
        "app.routers.reports.generate_download_url",
        new_callable=AsyncMock,
        return_value="https://s3.example.com/presigned",
    ):
        resp = await client.get(f"/api/v1/assessments/{a_id}/report", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://s3.example.com/presigned"


@pytest.mark.asyncio
async def test_get_report_not_generated(client: AsyncClient, db: AsyncSession) -> None:
    a_id = await _make_assessment_with_report(db, None)
    resp = await client.get(f"/api/v1/assessments/{a_id}/report")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_report_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/assessments/00000000-0000-0000-0000-000000000000/report")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_report_storage_error_returns_502(client: AsyncClient, db: AsyncSession) -> None:
    from app.services.storage import StorageError

    a_id = await _make_assessment_with_report(db, "assessments/key/report.pdf")
    with patch(
        "app.routers.reports.generate_download_url",
        new_callable=AsyncMock,
        side_effect=StorageError("S3 down"),
    ):
        resp = await client.get(f"/api/v1/assessments/{a_id}/report")
    assert resp.status_code == 502
