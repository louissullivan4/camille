from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class InviteAdminRequest(BaseModel):
    """Admin inviting another admin - no org needed."""

    email: EmailStr


class InviteManagerRequest(BaseModel):
    """Admin inviting an org manager - creates org if org_id not provided."""

    email: EmailStr
    organization_id: UUID | None = None
    # Required when organization_id is None - creates a new org
    org_name: str | None = None
    org_slug: str | None = None


class InviteUnderwriterRequest(BaseModel):
    """Manager inviting an underwriter to their org."""

    email: EmailStr


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: str
    organization_id: UUID | None = None
    token: str
    invited_by_id: UUID
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime


class GrantAccessRequest(BaseModel):
    user_id: UUID
