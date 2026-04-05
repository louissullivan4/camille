import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Valid subscription tiers
TIER_1 = "tier_1"
TIER_2 = "tier_2"
TIER_ENTERPRISE = "enterprise"
TIER_DEMO = "demo"

VALID_TIERS = {TIER_1, TIER_2, TIER_ENTERPRISE, TIER_DEMO}

# Monthly assessment limits per tier (None = unlimited)
TIER_MONTHLY_LIMITS: dict[str, int | None] = {
    TIER_1: 10,
    TIER_2: 50,
    TIER_ENTERPRISE: None,
    TIER_DEMO: None,
}


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # tier_1 | tier_2 | enterprise | demo
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default=TIER_1)
    # Admin override - bypasses billing requirements
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # SQLAlchemy reserves "metadata" - use org_metadata attr mapped to "metadata" column
    org_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
