import asyncio
from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.assessment import Assessment
from app.models.organization import Organization
from app.schemas.assessment import (
    AssessmentConfigUpdate,
    AssessmentCreate,
    AssessmentDetailResponse,
    AssessmentResponse,
    ProcessOptions,
    ProcessResponse,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])
log = structlog.get_logger()


@router.post("", response_model=AssessmentResponse, status_code=201)
async def create_assessment(
    payload: AssessmentCreate,
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    org_result = await db.execute(select(Organization).where(Organization.id == payload.organization_id))
    if not org_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")

    assessment = Assessment(
        organization_id=payload.organization_id,
        assessment_config=payload.assessment_config,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    log.info("assessment.created", assessment_id=str(assessment.id))
    return AssessmentResponse.model_validate(assessment)


@router.get("", response_model=list[AssessmentResponse])
async def list_assessments(
    db: AsyncSession = Depends(get_db),
    org_id: UUID | None = Query(None, description="Filter by organization ID"),
    status: str | None = Query(None, description="Filter by status (pending, processing, complete, failed)"),
    risk_tier: str | None = Query(None, description="Filter by risk tier (low, medium, high, critical)"),
    created_after: datetime | None = Query(None, description="Return assessments created after this ISO datetime"),
    created_before: datetime | None = Query(None, description="Return assessments created before this ISO datetime"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[AssessmentResponse]:
    query = select(Assessment).order_by(Assessment.created_at.desc())
    if org_id:
        query = query.where(Assessment.organization_id == org_id)
    if status:
        query = query.where(Assessment.status == status)
    if risk_tier:
        query = query.where(Assessment.risk_tier == risk_tier)
    if created_after:
        query = query.where(Assessment.created_at >= created_after)
    if created_before:
        query = query.where(Assessment.created_at <= created_before)
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    return [AssessmentResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/{assessment_id}", response_model=AssessmentDetailResponse)
async def get_assessment(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AssessmentDetailResponse:
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return AssessmentDetailResponse.model_validate(assessment)


@router.post("/{assessment_id}/process", response_model=ProcessResponse)
async def trigger_process(
    assessment_id: UUID,
    options: ProcessOptions | None = None,
    db: AsyncSession = Depends(get_db),
) -> ProcessResponse:
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.status in ("processing", "extracting", "scoring", "generating_report"):
        raise HTTPException(status_code=409, detail="Assessment is already processing")
    if assessment.status == "complete":
        raise HTTPException(status_code=409, detail="Assessment is already complete")

    assessment.status = "processing"
    await db.commit()

    resolved_options = options or ProcessOptions()

    # Import here to avoid circular imports at module level
    from app.workers.tasks import run_pipeline_task  # noqa: PLC0415

    asyncio.create_task(run_pipeline_task(assessment_id, resolved_options))
    log.info(
        "assessment.process_triggered",
        assessment_id=str(assessment_id),
        dimensions=resolved_options.dimensions,
        include_external_signals=resolved_options.include_external_signals,
        include_report=resolved_options.include_report,
    )
    return ProcessResponse(status="processing", assessment_id=assessment_id, options=resolved_options)


@router.put("/{assessment_id}/config", response_model=AssessmentResponse)
async def update_config(
    assessment_id: UUID,
    payload: AssessmentConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    assessment.assessment_config = payload.assessment_config
    await db.commit()
    await db.refresh(assessment)
    return AssessmentResponse.model_validate(assessment)
