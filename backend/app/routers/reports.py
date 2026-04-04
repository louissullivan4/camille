from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.assessment import Assessment
from app.services.storage import StorageError, generate_download_url

router = APIRouter(tags=["reports"])
log = structlog.get_logger()


@router.get("/assessments/{assessment_id}/report")
async def get_report(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not assessment.report_url:
        raise HTTPException(status_code=404, detail="Report not generated yet")

    # report_url stores the S3 key; generate a fresh presigned URL on each request
    try:
        presigned = await generate_download_url(assessment.report_url)
    except StorageError as exc:
        log.error("report.presign_failed", assessment_id=str(assessment_id), error=str(exc))
        raise HTTPException(status_code=502, detail="Could not generate report URL") from exc

    return RedirectResponse(url=presigned, status_code=302)
