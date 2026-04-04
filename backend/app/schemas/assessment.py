from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.score import AssessmentScoreResponse


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
    report_url: str | None = None
    created_at: datetime
    updated_at: datetime


class AssessmentDetailResponse(AssessmentResponse):
    """Extended response that embeds computed scores when assessment is complete."""

    scores: AssessmentScoreResponse | None = None


class AssessmentConfigUpdate(BaseModel):
    assessment_config: dict


class ProcessResponse(BaseModel):
    status: str
    assessment_id: UUID
