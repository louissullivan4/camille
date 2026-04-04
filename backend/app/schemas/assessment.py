from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.score import AssessmentScoreResponse

GOVERNANCE_DIMENSIONS = [
    "model_inventory",
    "human_oversight",
    "bias_fairness",
    "data_governance",
    "incident_response",
    "monitoring_drift",
    "regulatory_compliance",
    "third_party_risk",
]


class AssessmentCreate(BaseModel):
    organization_id: UUID
    assessment_config: dict | None = None


class ProcessOptions(BaseModel):
    """Options for controlling which parts of the pipeline run."""

    dimensions: list[str] | None = None
    """Subset of governance dimensions to extract and score. Defaults to all 8.
    Unrecognized dimension names are ignored."""

    include_external_signals: bool = True
    """Whether to fetch and incorporate external signals (news, regulatory) during scoring."""

    include_report: bool = True
    """Whether to generate the PDF report after scoring."""


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
    options: ProcessOptions | None = None
