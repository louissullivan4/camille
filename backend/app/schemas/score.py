from pydantic import BaseModel


class FlagResponse(BaseModel):
    severity: str  # critical | warning | info
    text: str
    dimension: str | None = None


class DimensionScoreResponse(BaseModel):
    dimension: str
    score: float
    max_score: float
    flags: list[FlagResponse]


class AssessmentScoreResponse(BaseModel):
    overall_score: float
    risk_tier: str
    dimensions: list[DimensionScoreResponse]
    all_flags: list[FlagResponse]
