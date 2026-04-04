from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.assessment import Assessment
from app.schemas.score import AssessmentScoreResponse, DimensionScoreResponse, FlagResponse

router = APIRouter(tags=["scores"])
log = structlog.get_logger()

_SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


@router.get("/assessments/{assessment_id}/scores", response_model=AssessmentScoreResponse)
async def get_scores(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    dimensions: list[str] | None = Query(
        None,
        description="Subset of dimensions to include in the response (e.g. model_inventory,human_oversight). "
        "Defaults to all 8.",
    ),
    flag_severity: str | None = Query(
        None,
        description="Minimum flag severity to include: critical (only critical), "
        "warning (critical + warning), info (all). Defaults to all.",
    ),
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

    min_rank = _SEVERITY_RANK.get(flag_severity or "info", 2)

    def _keep_flag(f: dict) -> bool:
        return _SEVERITY_RANK.get(f.get("severity", "info"), 2) <= min_rank

    dim_scores = assessment.dimension_scores
    if dimensions:
        dim_scores = {k: v for k, v in dim_scores.items() if k in dimensions}

    dimension_responses = [
        DimensionScoreResponse(
            dimension=dim,
            score=ds["score"],
            max_score=ds["max_score"],
            flags=[
                FlagResponse(severity=f["severity"], text=f["text"], dimension=dim)
                for f in ds.get("flags", [])
                if _keep_flag(f)
            ],
        )
        for dim, ds in dim_scores.items()
    ]

    stored_flags = (assessment.flags or {}).get("all_flags", [])
    all_flags = [
        FlagResponse(severity=f["severity"], text=f["text"], dimension=f.get("dimension"))
        for f in stored_flags
        if _keep_flag(f) and (not dimensions or f.get("dimension") in dimensions)
    ]

    return AssessmentScoreResponse(
        overall_score=assessment.overall_score or 0.0,
        risk_tier=assessment.risk_tier or "critical",
        dimensions=dimension_responses,
        all_flags=all_flags,
    )
