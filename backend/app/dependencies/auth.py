"""
FastAPI dependency functions for authentication and authorization.
"""

from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import ROLE_ADMIN, ROLE_ORG_MANAGER, User
from app.models.user_assessment_access import UserAssessmentAccess
from app.services.auth_service import decode_access_token

log = structlog.get_logger()

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
_FORBIDDEN = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise _UNAUTHORIZED
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise _UNAUTHORIZED

    user_id = payload.get("sub")
    if not user_id:
        raise _UNAUTHORIZED

    result = await db.execute(select(User).where(User.id == UUID(str(user_id))))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise _UNAUTHORIZED
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != ROLE_ADMIN:
        raise _FORBIDDEN
    return current_user


async def require_org_manager_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Allows admin or org_manager."""
    if current_user.role not in (ROLE_ADMIN, ROLE_ORG_MANAGER):
        raise _FORBIDDEN
    return current_user


def require_org_access(allow_admin: bool = True):
    """
    Returns a dependency that verifies the current user has access to the given org_id.
    Admins always pass (if allow_admin). org_manager/underwriter must belong to that org.
    """

    async def _check(
        org_id: UUID,
        current_user: User = Depends(get_current_user),
    ) -> User:
        if allow_admin and current_user.role == ROLE_ADMIN:
            return current_user
        if current_user.organization_id != org_id:
            raise _FORBIDDEN
        return current_user

    return _check


async def require_assessment_access(
    assessment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Admins and org_managers with the right org pass freely.
    org_underwriters need an explicit UserAssessmentAccess row.
    """
    from app.models.assessment import Assessment

    if current_user.role == ROLE_ADMIN:
        return current_user

    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if current_user.role == ROLE_ORG_MANAGER:
        if current_user.organization_id != assessment.organization_id:
            raise _FORBIDDEN
        return current_user

    # org_underwriter: must have explicit grant
    access_result = await db.execute(
        select(UserAssessmentAccess).where(
            UserAssessmentAccess.user_id == current_user.id,
            UserAssessmentAccess.assessment_id == assessment_id,
        )
    )
    if not access_result.scalar_one_or_none():
        raise _FORBIDDEN
    return current_user
