from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.organization import TIER_1


class OrganizationCreate(BaseModel):
    name: str
    slug: str
    tier: str = TIER_1
    is_demo: bool = False
    org_metadata: dict | None = None


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    tier: str
    is_demo: bool
    org_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime


class OrganizationAdminResponse(BaseModel):
    """Organization row for admin list view - includes user count."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    tier: str
    is_demo: bool
    user_count: int
    org_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime


class OrganizationUsageResponse(BaseModel):
    org_id: UUID
    tier: str
    is_demo: bool
    assessments_this_month: int
    monthly_limit: int | None  # None = unlimited
    estimated_cost_usd: float | None
