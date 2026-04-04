import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.organization import Organization


async def _make_complete_assessment(db: AsyncSession) -> str:
    """Create an org + complete assessment directly in DB for score endpoint tests."""
    import uuid

    org = Organization(name="ScoreOrg", slug=f"score-org-{uuid.uuid4().hex[:8]}")
    db.add(org)
    await db.flush()

    # dimension_scores stores the already-computed scored output from the pipeline,
    # not raw extraction findings. Format: {score, max_score, flags}.
    dim_score = {"score": 50.0, "max_score": 100.0, "flags": []}
    assessment = Assessment(
        organization_id=org.id,
        status="complete",
        overall_score=55.0,
        risk_tier="medium",
        dimension_scores={
            dim: dict(dim_score)
            for dim in [
                "model_inventory",
                "human_oversight",
                "bias_fairness",
                "data_governance",
                "incident_response",
                "monitoring_drift",
                "regulatory_compliance",
                "third_party_risk",
            ]
        },
        flags={"all_flags": [{"severity": "warning", "text": "Test flag", "dimension": "model_inventory"}]},
    )
    db.add(assessment)
    await db.commit()
    return str(assessment.id)


@pytest.mark.asyncio
async def test_get_scores_complete_assessment(client: AsyncClient, db: AsyncSession) -> None:
    a_id = await _make_complete_assessment(db)
    resp = await client.get(f"/api/v1/assessments/{a_id}/scores")
    assert resp.status_code == 200
    data = resp.json()
    assert "overall_score" in data
    assert "risk_tier" in data
    assert len(data["dimensions"]) == 8


@pytest.mark.asyncio
async def test_get_scores_pending_assessment(client: AsyncClient) -> None:
    # Create org + pending assessment
    org = await client.post("/api/v1/organizations", json={"name": "PendOrg", "slug": "pend-score-org"})
    a = await client.post("/api/v1/assessments", json={"organization_id": org.json()["id"]})
    a_id = a.json()["id"]
    resp = await client.get(f"/api/v1/assessments/{a_id}/scores")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_scores_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/assessments/00000000-0000-0000-0000-000000000000/scores")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_scores_complete_but_no_scores_stored(client: AsyncClient, db: AsyncSession) -> None:
    """complete assessment with no dimension_scores returns 404."""
    import uuid

    org = Organization(name="NoScoreOrg", slug=f"no-score-{uuid.uuid4().hex[:8]}")
    db.add(org)
    await db.flush()
    assessment = Assessment(
        organization_id=org.id,
        status="complete",
        overall_score=None,
        risk_tier=None,
        dimension_scores=None,
    )
    db.add(assessment)
    await db.commit()
    resp = await client.get(f"/api/v1/assessments/{assessment.id}/scores")
    assert resp.status_code == 404
