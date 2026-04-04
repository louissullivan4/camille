import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExternalSignal(Base):
    __tablename__ = "external_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False, index=True
    )
    # litigation | regulatory_action | media_sentiment | incident
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # low | medium | high | critical
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
