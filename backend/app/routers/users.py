"""
User management endpoints.

- Admin: list all users, deactivate user
- Org manager: list users in their org
- Org manager: grant/revoke assessment access for underwriters
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_admin, require_org_manager_or_admin
from app.models.assessment import Assessment
from app.models.user import ROLE_ADMIN, ROLE_ORG_UNDERWRITER, User
from app.models.user_assessment_access import UserAssessmentAccess
from app.schemas.invitation import GrantAccessRequest
from app.schemas.user import UserListResponse, UserResponse

router = APIRouter(prefix="/users", tags=["users"])
log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=UserListResponse)
async def list_all_users(
    role: str | None = Query(None, description="Filter by role"),
    org_id: UUID | None = Query(None, description="Filter by organization"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if org_id:
        query = query.where(User.organization_id == org_id)
    query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    return UserListResponse(users=[UserResponse.model_validate(u) for u in users], total=len(users))


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    log.info("user.deactivated", user_id=str(user_id))
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# Org-scoped endpoints (manager or admin)
# ---------------------------------------------------------------------------


@router.get("/org/{org_id}", response_model=UserListResponse)
async def list_org_users(
    org_id: UUID,
    current_user: User = Depends(require_org_manager_or_admin),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    # Org managers can only see their own org
    if current_user.role != ROLE_ADMIN and current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(select(User).where(User.organization_id == org_id).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return UserListResponse(users=[UserResponse.model_validate(u) for u in users], total=len(users))


@router.post("/org/{org_id}/assessments/{assessment_id}/grant", response_model=dict, status_code=201)
async def grant_assessment_access(
    org_id: UUID,
    assessment_id: UUID,
    payload: GrantAccessRequest,
    current_user: User = Depends(require_org_manager_or_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Grant an underwriter in this org access to a specific assessment."""
    if current_user.role != ROLE_ADMIN and current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Verify assessment belongs to org
    assessment_result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id, Assessment.organization_id == org_id)
    )
    if not assessment_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Assessment not found in this org")

    # Verify target user is an underwriter in this org
    user_result = await db.execute(select(User).where(User.id == payload.user_id))
    target = user_result.scalar_one_or_none()
    if not target or target.role != ROLE_ORG_UNDERWRITER or target.organization_id != org_id:
        raise HTTPException(status_code=422, detail="Target user is not an underwriter in this org")

    access = UserAssessmentAccess(
        user_id=payload.user_id,
        assessment_id=assessment_id,
        granted_by_id=current_user.id,
    )
    db.add(access)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Access already granted")

    log.info(
        "access.granted",
        user_id=str(payload.user_id),
        assessment_id=str(assessment_id),
        granted_by=str(current_user.id),
    )
    return {"granted": True, "user_id": str(payload.user_id), "assessment_id": str(assessment_id)}


@router.delete("/org/{org_id}/assessments/{assessment_id}/grant/{user_id}", status_code=204)
async def revoke_assessment_access(
    org_id: UUID,
    assessment_id: UUID,
    user_id: UUID,
    current_user: User = Depends(require_org_manager_or_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke an underwriter's access to a specific assessment."""
    if current_user.role != ROLE_ADMIN and current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(
        select(UserAssessmentAccess).where(
            UserAssessmentAccess.user_id == user_id,
            UserAssessmentAccess.assessment_id == assessment_id,
        )
    )
    access = result.scalar_one_or_none()
    if not access:
        raise HTTPException(status_code=404, detail="Access grant not found")

    await db.delete(access)
    await db.commit()
    log.info("access.revoked", user_id=str(user_id), assessment_id=str(assessment_id))
