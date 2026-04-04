from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


async def _setup(client: AsyncClient, slug: str) -> str:
    org = await client.post("/api/v1/organizations", json={"name": "DocOrg", "slug": slug})
    a = await client.post(
        "/api/v1/assessments", json={"organization_id": org.json()["id"]}
    )
    return a.json()["id"]


@pytest.mark.asyncio
async def test_upload_document(client: AsyncClient) -> None:
    a_id = await _setup(client, "doc-org-upload")

    with (
        patch("app.routers.documents.upload_bytes", new_callable=AsyncMock),
        patch("app.workers.tasks.process_document_task", new_callable=AsyncMock),
    ):
        resp = await client.post(
            f"/api/v1/assessments/{a_id}/documents",
            files={"file": ("test.txt", BytesIO(b"some content"), "text/plain")},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["filename"] == "test.txt"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_document_wrong_type(client: AsyncClient) -> None:
    a_id = await _setup(client, "doc-org-type")

    with patch("app.routers.documents.upload_bytes", new_callable=AsyncMock):
        resp = await client.post(
            f"/api/v1/assessments/{a_id}/documents",
            files={"file": ("test.csv", BytesIO(b"a,b,c"), "text/csv")},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_document_assessment_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/assessments/00000000-0000-0000-0000-000000000000/documents",
        files={"file": ("test.txt", BytesIO(b"data"), "text/plain")},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient) -> None:
    a_id = await _setup(client, "doc-org-list")
    resp = await client.get(f"/api/v1/assessments/{a_id}/documents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient) -> None:
    a_id = await _setup(client, "doc-org-404")
    resp = await client.get(
        f"/api/v1/assessments/{a_id}/documents/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_document_storage_error_returns_502(client: AsyncClient) -> None:
    from app.services.storage import StorageError
    a_id = await _setup(client, "doc-org-s3err")
    with patch("app.routers.documents.upload_bytes", new_callable=AsyncMock, side_effect=StorageError("S3 down")):
        resp = await client.post(
            f"/api/v1/assessments/{a_id}/documents",
            files={"file": ("test.txt", BytesIO(b"data"), "text/plain")},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_upload_document_file_too_large(client: AsyncClient) -> None:
    a_id = await _setup(client, "doc-org-toobig")
    big_data = b"x" * (50 * 1024 * 1024 + 1)
    with patch("app.routers.documents.upload_bytes", new_callable=AsyncMock):
        resp = await client.post(
            f"/api/v1/assessments/{a_id}/documents",
            files={"file": ("big.txt", BytesIO(big_data), "text/plain")},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_documents_assessment_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/assessments/00000000-0000-0000-0000-000000000000/documents")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_document_success(client: AsyncClient) -> None:
    from io import BytesIO
    a_id = await _setup(client, "doc-org-get-ok")
    with (
        patch("app.routers.documents.upload_bytes", new_callable=AsyncMock),
        patch("app.workers.tasks.process_document_task", new_callable=AsyncMock),
    ):
        upload = await client.post(
            f"/api/v1/assessments/{a_id}/documents",
            files={"file": ("found.txt", BytesIO(b"content"), "text/plain")},
        )
    doc_id = upload.json()["id"]
    resp = await client.get(f"/api/v1/assessments/{a_id}/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id
