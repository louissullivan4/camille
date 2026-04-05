from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.assessment import Assessment
from app.models.organization import TIER_MONTHLY_LIMITS, Organization
from app.schemas.assessment import AssessmentResponse
from app.schemas.organization import OrganizationCreate, OrganizationResponse, OrganizationUsageResponse

# Approximate per-assessment cost in USD by tier (midpoint of published ranges)
TIER_COST_PER_ASSESSMENT: dict[str, float] = {
    "tier_1": 1000.0,
    "tier_2": 3500.0,
    "enterprise": 0.0,  # annual flat fee - no per-assessment charge shown
    "demo": 0.0,
}

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


@router.get("/{org_id}/usage", response_model=OrganizationUsageResponse)
async def get_org_usage(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> OrganizationUsageResponse:
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    count_result = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.organization_id == org_id,
            Assessment.created_at >= month_start,
        )
    )
    count = count_result.scalar_one()

    monthly_limit = TIER_MONTHLY_LIMITS.get(org.tier)
    cost_per = TIER_COST_PER_ASSESSMENT.get(org.tier, 0.0)
    estimated_cost = count * cost_per if org.tier not in ("enterprise", "demo") else None

    return OrganizationUsageResponse(
        org_id=org_id,
        tier=org.tier,
        is_demo=org.is_demo,
        assessments_this_month=count,
        monthly_limit=monthly_limit,
        estimated_cost_usd=estimated_cost,
    )
