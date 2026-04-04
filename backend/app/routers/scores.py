from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.assessment import Assessment
from app.schemas.score import AssessmentScoreResponse, DimensionScoreResponse, FlagResponse

router = APIRouter(tags=["scores"])
log = structlog.get_logger()


@router.get("/assessments/{assessment_id}/scores", response_model=AssessmentScoreResponse)
async def get_scores(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AssessmentScoreResponse:
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.status != "complete":
        raise HTTPException(
            status_code=404,
            detail=f"Assessment is not complete yet (status: {assessment.status})",
        )
    if not assessment.dimension_scores:
        raise HTTPException(status_code=404, detail="No scores available")

    dimensions = [
        DimensionScoreResponse(
            dimension=dim,
            score=ds["score"],
            max_score=ds["max_score"],
            flags=[
                FlagResponse(
                    severity=f["severity"],
                    text=f["text"],
                    dimension=dim,
                )
                for f in ds.get("flags", [])
            ],
        )
        for dim, ds in assessment.dimension_scores.items()
    ]

    stored_flags = (assessment.flags or {}).get("all_flags", [])
    all_flags = [
        FlagResponse(
            severity=f["severity"],
            text=f["text"],
            dimension=f.get("dimension"),
        )
        for f in stored_flags
    ]

    return AssessmentScoreResponse(
        overall_score=assessment.overall_score or 0.0,
        risk_tier=assessment.risk_tier or "critical",
        dimensions=dimensions,
        all_flags=all_flags,
    )
