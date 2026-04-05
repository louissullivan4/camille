"""
Auth endpoints: login, register from invite, current user.
"""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.invitation import Invitation
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger()


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        log.warning("auth.login_failed", email=payload.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id, user.role, user.organization_id)
    log.info("auth.login_success", user_id=str(user.id), role=user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register_from_invite(
    invite_token: str,
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Complete registration using an invite token.
    The invite token is passed as a query parameter: POST /auth/register?invite_token=<token>
    """
    result = await db.execute(select(Invitation).where(Invitation.token == invite_token))
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=409, detail="Invitation already accepted")
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Invitation expired")

    # Check email not already registered
    existing = await db.execute(select(User).where(User.email == invitation.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=invitation.email,
        hashed_password=hash_password(payload.password),
        role=invitation.role,
        organization_id=invitation.organization_id,
        is_active=True,
    )
    db.add(user)
    invitation.accepted_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role, user.organization_id)
    log.info("auth.registered", user_id=str(user.id), role=user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
