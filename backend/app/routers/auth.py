"""
Auth endpoints: login, register from invite, current user, password reset.
"""

import random
import string
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.invitation import Invitation
from app.models.organization import Organization
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.auth import (
    InvitationInfoResponse,
    LoginRequest,
    PasswordResetConfirmPayload,
    PasswordResetRequestPayload,
    RegisterRequest,
    SignupPayload,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger()

PASSWORD_RESET_EXPIRE_MINUTES = 15


def _generate_reset_code() -> str:
    return "".join(random.choices(string.digits, k=6))


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


@router.post("/password-reset/request", status_code=204)
async def request_password_reset(
    payload: PasswordResetRequestPayload,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Request a password reset code. Always returns 204 to avoid email enumeration.
    The code is sent to the user's email if the account exists.
    """
    result = await db.execute(select(User).where(User.email == payload.email, User.is_active == True))  # noqa: E712
    user = result.scalar_one_or_none()

    if user:
        code = _generate_reset_code()
        token = PasswordResetToken(
            email=payload.email,
            code_hash=hash_password(code),
            expires_at=datetime.now(UTC) + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
        )
        db.add(token)
        await db.commit()

        # Import here to avoid circular at module level
        from app.services.email_service import send_password_reset_code  # noqa: PLC0415

        try:
            send_password_reset_code(payload.email, code)
        except Exception as exc:
            log.error("auth.reset_email_failed", email=payload.email, error=str(exc))
            # Don't surface the error - user gets 204 either way

    log.info("auth.password_reset_requested", email=payload.email, user_found=user is not None)


@router.post("/password-reset/confirm", status_code=204)
async def confirm_password_reset(
    payload: PasswordResetConfirmPayload,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Verify the 6-digit code and set a new password."""
    now = datetime.now(UTC)

    # Find the most recent unused, unexpired token for this email
    result = await db.execute(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.email == payload.email,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )
    token = result.scalar_one_or_none()

    if not token or not verify_password(payload.code, token.code_hash):
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    # Mark token used
    token.used_at = now

    # Update user password
    user_result = await db.execute(select(User).where(User.email == payload.email, User.is_active == True))  # noqa: E712
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    log.info("auth.password_reset_complete", email=payload.email)


@router.get("/invitation-info", response_model=InvitationInfoResponse)
async def get_invitation_info(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> InvitationInfoResponse:
    """Return invitation metadata so the signup form can be pre-populated."""
    result = await db.execute(select(Invitation).where(Invitation.token == token))
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

    org_name: str | None = None
    if invitation.organization_id:
        org_result = await db.execute(select(Organization).where(Organization.id == invitation.organization_id))
        org = org_result.scalar_one_or_none()
        if org:
            org_name = org.name

    return InvitationInfoResponse(
        email=invitation.email,
        role=invitation.role,
        org_name=org_name,
        org_id=str(invitation.organization_id) if invitation.organization_id else None,
    )


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup_from_invitation(
    payload: SignupPayload,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Accept an invitation and create a user account.
    For org_manager invitations: also creates the organization.
    """
    result = await db.execute(select(Invitation).where(Invitation.token == payload.token))
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

    existing = await db.execute(select(User).where(User.email == invitation.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    if len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    org_id = invitation.organization_id

    # For org_manager invitations without an org - create one
    if invitation.role == "org_manager" and not org_id:
        if not payload.org:
            raise HTTPException(status_code=422, detail="Organization details required for org_manager signup")
        from sqlalchemy.exc import IntegrityError  # noqa: PLC0415

        org = Organization(
            name=payload.org.name,
            slug=payload.org.slug,
            tier=payload.org.tier,
            org_metadata={"industry": payload.org.industry} if payload.org.industry else None,
        )
        db.add(org)
        try:
            await db.flush()  # get org.id without committing
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail=f"Slug '{payload.org.slug}' already exists")
        org_id = org.id

    user = User(
        email=invitation.email,
        hashed_password=hash_password(payload.password),
        role=invitation.role,
        organization_id=org_id,
        is_active=True,
    )
    # Store display name in a future column; for now skip if model doesn't have it
    db.add(user)
    invitation.accepted_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role, user.organization_id)
    log.info("auth.signup_complete", user_id=str(user.id), role=user.role, org_id=str(org_id))
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))
