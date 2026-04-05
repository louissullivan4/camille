from pydantic import BaseModel, EmailStr

from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RegisterRequest(BaseModel):
    password: str


class PasswordResetRequestPayload(BaseModel):
    email: EmailStr


class PasswordResetConfirmPayload(BaseModel):
    email: EmailStr
    code: str
    new_password: str


class InvitationInfoResponse(BaseModel):
    email: str
    role: str
    org_name: str | None = None
    org_id: str | None = None


class SignupOrgPayload(BaseModel):
    """Organization details - only required when token role is org_manager."""

    name: str
    slug: str
    tier: str = "tier_1"
    industry: str | None = None


class SignupPayload(BaseModel):
    """Accept an invitation and create a user account. Optionally create an org."""

    token: str
    password: str
    first_name: str | None = None
    last_name: str | None = None
    # Only for org_manager invitations
    org: SignupOrgPayload | None = None
