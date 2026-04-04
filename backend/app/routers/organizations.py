from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.assessment import Assessment
from app.models.organization import Organization
from app.schemas.assessment import AssessmentResponse
from app.schemas.organization import OrganizationCreate, OrganizationResponse

router = APIRouter(prefix="/organizations", tags=["organizations"])
log = structlog.get_logger()


@router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    payload: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    org = Organization(
        name=payload.name,
        slug=payload.slug,
        org_metadata=payload.org_metadata,
    )
    db.add(org)
    try:
        await db.commit()
        await db.refresh(org)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Slug '{payload.slug}' already exists")
    log.info("org.created", org_id=str(org.id), slug=org.slug)
    return OrganizationResponse.model_validate(org)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationResponse.model_validate(org)


@router.get("/{org_id}/assessments", response_model=list[AssessmentResponse])
async def list_org_assessments(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None, description="Filter by status (pending, processing, complete, failed)"),
    risk_tier: str | None = Query(None, description="Filter by risk tier (low, medium, high, critical)"),
    created_after: datetime | None = Query(None, description="Return assessments created after this ISO datetime"),
    created_before: datetime | None = Query(None, description="Return assessments created before this ISO datetime"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[AssessmentResponse]:
    # Verify org exists
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    if not org_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")

    query = select(Assessment).where(Assessment.organization_id == org_id).order_by(Assessment.created_at.desc())
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
    assessments = result.scalars().all()
    return [AssessmentResponse.model_validate(a) for a in assessments]
