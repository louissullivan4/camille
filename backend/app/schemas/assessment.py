from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssessmentCreate(BaseModel):
    organization_id: UUID
    assessment_config: dict | None = None


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    status: str
    overall_score: float | None = None
    risk_tier: str | None = None
    dimension_scores: dict | None = None
    flags: dict | None = None
    assessment_config: dict | None = None
    created_at: datetime
    updated_at: datetime
