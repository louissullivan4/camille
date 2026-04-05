"""
Invitation management endpoints.

- Admin: invite admins, invite org managers (with optional org creation)
- Org manager: invite underwriters into their org
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_admin, require_org_manager_or_admin
from app.models.invitation import Invitation
from app.models.organization import Organization
from app.models.user import ROLE_ADMIN, ROLE_ORG_MANAGER, ROLE_ORG_UNDERWRITER, User
from app.schemas.invitation import (
    InvitationResponse,
    InviteAdminRequest,
    InviteManagerRequest,
    InviteUnderwriterRequest,
)

router = APIRouter(prefix="/invitations", tags=["invitations"])
log = structlog.get_logger()

_INVITE_TTL_HOURS = 72


def _make_token() -> str:
    return str(uuid.uuid4()).replace("-", "")


def _expires() -> datetime:
    return datetime.now(UTC) + timedelta(hours=_INVITE_TTL_HOURS)


@router.post("/admin", response_model=InvitationResponse, status_code=201)
async def invite_admin(
    payload: InviteAdminRequest,
    inviter: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    """Admin invites another platform admin."""
    invitation = Invitation(
        email=payload.email,
        role=ROLE_ADMIN,
        organization_id=None,
        token=_make_token(),
        invited_by_id=inviter.id,
        expires_at=_expires(),
    )
    db.add(invitation)
    try:
        await db.commit()
        await db.refresh(invitation)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Pending invitation for this email already exists")

    log.info("invitation.created", role=ROLE_ADMIN, email=payload.email, invited_by=str(inviter.id))

    from app.services.email_service import send_invitation_email  # noqa: PLC0415

    try:
        send_invitation_email(invitation.email, invitation.token, invitation.role, org_name=None)
    except Exception as exc:
        log.error("invitation.email_failed", email=invitation.email, error=str(exc))

    return InvitationResponse.model_validate(invitation)


@router.post("/manager", response_model=InvitationResponse, status_code=201)
async def invite_manager(
    payload: InviteManagerRequest,
    inviter: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    """
    Admin invites an org manager.
    If organization_id is provided, uses that org.
    Otherwise, creates a new org using org_name + org_slug.
    """
    org_id: uuid.UUID | None = payload.organization_id

    if org_id is None:
        if not payload.org_name or not payload.org_slug:
            raise HTTPException(
                status_code=422,
                detail="org_name and org_slug are required when organization_id is not provided",
            )
        org = Organization(name=payload.org_name, slug=payload.org_slug)
        db.add(org)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail=f"Slug '{payload.org_slug}' already exists")
        org_id = org.id
    else:
        org_result = await db.execute(select(Organization).where(Organization.id == org_id))
        if not org_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Organization not found")

    invitation = Invitation(
        email=payload.email,
        role=ROLE_ORG_MANAGER,
        organization_id=org_id,
        token=_make_token(),
        invited_by_id=inviter.id,
        expires_at=_expires(),
    )
    db.add(invitation)
    try:
        await db.commit()
        await db.refresh(invitation)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Pending invitation for this email already exists")

    log.info("invitation.created", role=ROLE_ORG_MANAGER, email=payload.email, org_id=str(org_id))

    from app.services.email_service import send_invitation_email  # noqa: PLC0415

    # Fetch org name for the email if we have an org
    email_org_name: str | None = None
    if org_id:
        org_name_result = await db.execute(select(Organization).where(Organization.id == org_id))
        email_org = org_name_result.scalar_one_or_none()
        email_org_name = email_org.name if email_org else None

    try:
        send_invitation_email(invitation.email, invitation.token, invitation.role, org_name=email_org_name)
    except Exception as exc:
        log.error("invitation.email_failed", email=invitation.email, error=str(exc))

    return InvitationResponse.model_validate(invitation)


@router.post("/underwriter", response_model=InvitationResponse, status_code=201)
async def invite_underwriter(
    payload: InviteUnderwriterRequest,
    inviter: User = Depends(require_org_manager_or_admin),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    """
    Org manager (or admin) invites an underwriter into the manager's org.
    Admins must use /manager with an explicit org; this endpoint is for org managers.
    """
    if inviter.role != ROLE_ADMIN and inviter.organization_id is None:
        raise HTTPException(status_code=422, detail="Manager has no organization assigned")

    # Admins calling this endpoint must have an org assigned too; otherwise use /manager
    org_id = inviter.organization_id
    if org_id is None:
        raise HTTPException(
            status_code=422,
            detail="Use POST /invitations/manager to invite into a specific org as admin",
        )

    invitation = Invitation(
        email=payload.email,
        role=ROLE_ORG_UNDERWRITER,
        organization_id=org_id,
        token=_make_token(),
        invited_by_id=inviter.id,
        expires_at=_expires(),
    )
    db.add(invitation)
    try:
        await db.commit()
        await db.refresh(invitation)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Pending invitation for this email already exists")

    log.info("invitation.created", role=ROLE_ORG_UNDERWRITER, email=payload.email, org_id=str(org_id))

    from app.services.email_service import send_invitation_email  # noqa: PLC0415

    email_org_name: str | None = None
    if org_id:
        org_name_result = await db.execute(select(Organization).where(Organization.id == org_id))
        email_org = org_name_result.scalar_one_or_none()
        email_org_name = email_org.name if email_org else None

    try:
        send_invitation_email(invitation.email, invitation.token, invitation.role, org_name=email_org_name)
    except Exception as exc:
        log.error("invitation.email_failed", email=invitation.email, error=str(exc))

    return InvitationResponse.model_validate(invitation)


@router.get("/{token}", response_model=InvitationResponse)
async def get_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    """Look up an invite by token (used by frontend before showing the register form)."""
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return InvitationResponse.model_validate(invitation)
