"""
Admin-only endpoints.

- GET  /admin/organizations        list all orgs with user count
- PATCH /admin/organizations/{id}/demo  toggle is_demo flag
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_admin
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationAdminResponse, OrganizationResponse

router = APIRouter(prefix="/admin", tags=["admin"])
log = structlog.get_logger()


@router.get("/organizations", response_model=list[OrganizationAdminResponse])
async def list_all_organizations(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationAdminResponse]:
    """List all organizations with user counts. Admin only."""
    # Join orgs with user count subquery
    user_count_sq = (
        select(User.organization_id, func.count(User.id).label("user_count")).group_by(User.organization_id).subquery()
    )

    result = await db.execute(
        select(Organization, func.coalesce(user_count_sq.c.user_count, 0).label("user_count"))
        .outerjoin(user_count_sq, Organization.id == user_count_sq.c.organization_id)
        .order_by(Organization.created_at.desc())
    )

    rows = result.all()
    return [
        OrganizationAdminResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            tier=org.tier,
            is_demo=org.is_demo,
            user_count=user_count,
            org_metadata=org.org_metadata,
            created_at=org.created_at,
            updated_at=org.updated_at,
        )
        for org, user_count in rows
    ]


@router.patch("/organizations/{org_id}/demo", response_model=OrganizationResponse)
async def toggle_demo(
    org_id: UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """Toggle the is_demo flag on an organization. Admin only."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org.is_demo = not org.is_demo
    await db.commit()
    await db.refresh(org)

    log.info("admin.org_demo_toggled", org_id=str(org_id), is_demo=org.is_demo)
    return OrganizationResponse.model_validate(org)
