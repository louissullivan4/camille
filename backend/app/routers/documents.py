import asyncio
import uuid
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.assessment import Assessment
from app.models.document import Document
from app.schemas.document import DocumentResponse
from app.services.storage import StorageError, upload_bytes

router = APIRouter(tags=["documents"])
log = structlog.get_logger()

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post(
    "/assessments/{assessment_id}/documents",
    response_model=DocumentResponse,
    status_code=201,
)
async def upload_document(
    assessment_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    # Verify assessment exists
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, DOCX, TXT",
        )

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail="File exceeds 50 MB limit")

    s3_key = f"assessments/{assessment_id}/documents/{uuid.uuid4()}/{file.filename}"
    try:
        await upload_bytes(s3_key, data, file.content_type or "application/octet-stream")
    except StorageError as exc:
        log.error("document.upload_failed", assessment_id=str(assessment_id), error=str(exc))
        raise HTTPException(status_code=502, detail="Storage upload failed") from exc

    doc = Document(
        assessment_id=assessment_id,
        filename=file.filename or "upload",
        s3_key=s3_key,
        status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Trigger classification in background
    from app.workers.tasks import process_document_task  # noqa: PLC0415

    asyncio.create_task(process_document_task(doc.id, data, doc.filename))
    log.info("document.uploaded", doc_id=str(doc.id), filename=doc.filename)
    return DocumentResponse.model_validate(doc)


@router.get("/assessments/{assessment_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Assessment not found")

    docs_result = await db.execute(
        select(Document).where(Document.assessment_id == assessment_id).order_by(Document.created_at)
    )
    return [DocumentResponse.model_validate(d) for d in docs_result.scalars().all()]


@router.get(
    "/assessments/{assessment_id}/documents/{doc_id}",
    response_model=DocumentResponse,
)
async def get_document(
    assessment_id: UUID,
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.assessment_id == assessment_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)
