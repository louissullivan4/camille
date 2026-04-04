"""
Unit tests for app/services/report_generator.py.

Mocks: Claude Opus client, WeasyPrint, and S3 upload.
Only the data-loading and template-rendering logic is exercised against the
real test DB (SQLite in-memory via conftest).
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.document import Document
from app.models.organization import Organization

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _seed_assessment(db: AsyncSession, *, overall_score: float = 55.0) -> Assessment:
    org = Organization(name="TestCo", slug=f"testco-{uuid4().hex[:6]}")
    db.add(org)
    await db.flush()

    assessment = Assessment(
        organization_id=org.id,
        status="complete",
        overall_score=overall_score,
        risk_tier="medium",
        dimension_scores={
            "model_inventory": {"score": 60.0, "max_score": 100, "flags": []},
            "human_oversight": {
                "score": 50.0,
                "max_score": 100,
                "flags": [{"severity": "critical", "text": "HITL limited to senior staff"}],
            },
            "bias_fairness": {"score": 40.0, "max_score": 100, "flags": []},
            "data_governance": {"score": 55.0, "max_score": 100, "flags": []},
            "incident_response": {
                "score": 0.0,
                "max_score": 100,
                "flags": [{"severity": "critical", "text": "No AI-specific incident response plan"}],
            },
            "monitoring_drift": {"score": 70.0, "max_score": 100, "flags": []},
            "regulatory_compliance": {
                "score": 30.0,
                "max_score": 100,
                "flags": [{"severity": "critical", "text": "LL144 non-compliance"}],
            },
            "third_party_risk": {"score": 45.0, "max_score": 100, "flags": []},
        },
        flags={
            "all_flags": [
                {"severity": "critical", "dimension": "human_oversight", "text": "HITL limited to senior staff"},
                {"severity": "critical", "dimension": "incident_response", "text": "No AI-specific IR plan"},
                {"severity": "critical", "dimension": "regulatory_compliance", "text": "LL144 non-compliance"},
            ]
        },
    )
    db.add(assessment)
    await db.flush()

    doc = Document(
        assessment_id=assessment.id,
        filename="hitl_policy.txt",
        doc_type="hitl_policy",
        status="processed",
        raw_text="Human-in-the-loop policy document.",
    )
    db.add(doc)
    await db.commit()

    return assessment


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_report_returns_s3_key(db: AsyncSession) -> None:
    """generate_report() should return an S3 key string containing the assessment ID."""
    assessment = await _seed_assessment(db)

    mock_pdf = b"%PDF-1.4 fake pdf bytes"

    with (
        patch(
            "app.services.report_generator._generate_narrative",
            new_callable=AsyncMock,
            return_value="TestCo presents a medium risk profile. The primary gap is limited HITL coverage. Recommend acceptance with conditions.",
        ),
        patch("app.services.report_generator._render_pdf", return_value=mock_pdf),
        patch("app.services.report_generator.upload_bytes", new_callable=AsyncMock),
    ):
        from app.services.report_generator import generate_report

        key = await generate_report(assessment.id, db)

    assert str(assessment.id) in key
    assert key.endswith(".pdf")


@pytest.mark.asyncio
async def test_generate_report_uploads_pdf_bytes(db: AsyncSession) -> None:
    """S3 upload_bytes should be called with the PDF bytes and correct content-type."""
    assessment = await _seed_assessment(db)
    mock_pdf = b"%PDF-1.4 test content"

    with (
        patch("app.services.report_generator._generate_narrative", new_callable=AsyncMock, return_value="Narrative."),
        patch("app.services.report_generator._render_pdf", return_value=mock_pdf),
        patch("app.services.report_generator.upload_bytes", new_callable=AsyncMock) as mock_upload,
    ):
        from app.services.report_generator import generate_report

        await generate_report(assessment.id, db)

    mock_upload.assert_awaited_once()
    call_args = mock_upload.call_args
    assert call_args.args[1] == mock_pdf
    assert call_args.kwargs.get("content_type") == "application/pdf"


@pytest.mark.asyncio
async def test_generate_report_narrative_failure_uses_fallback(db: AsyncSession) -> None:
    """If Claude Opus call fails, a fallback narrative is used and PDF still generates."""
    assessment = await _seed_assessment(db)
    mock_pdf = b"%PDF-1.4 fallback"

    with (
        patch(
            "app.services.report_generator._generate_narrative",
            new_callable=AsyncMock,
            side_effect=Exception("Opus API timeout"),
        ),
        patch("app.services.report_generator._render_pdf", return_value=mock_pdf),
        patch("app.services.report_generator.upload_bytes", new_callable=AsyncMock),
    ):
        from app.services.report_generator import generate_report

        key = await generate_report(assessment.id, db)

    # Should still succeed with fallback narrative
    assert key.endswith(".pdf")


@pytest.mark.asyncio
async def test_generate_report_raises_on_missing_assessment(db: AsyncSession) -> None:
    """generate_report() should raise ValueError when assessment is not found."""
    from app.services.report_generator import generate_report

    with pytest.raises(ValueError, match="not found"):
        await generate_report(uuid4(), db)


@pytest.mark.asyncio
async def test_generate_report_handles_no_documents(db: AsyncSession) -> None:
    """Report should generate even if no documents are attached to the assessment."""
    org = Organization(name="EmptyOrg", slug=f"empty-{uuid4().hex[:6]}")
    db.add(org)
    await db.flush()

    assessment = Assessment(
        organization_id=org.id,
        status="complete",
        overall_score=10.0,
        risk_tier="critical",
        dimension_scores={},
        flags={"all_flags": []},
    )
    db.add(assessment)
    await db.commit()

    mock_pdf = b"%PDF-1.4 empty"

    with (
        patch("app.services.report_generator._generate_narrative", new_callable=AsyncMock, return_value="Critical."),
        patch("app.services.report_generator._render_pdf", return_value=mock_pdf),
        patch("app.services.report_generator.upload_bytes", new_callable=AsyncMock),
    ):
        from app.services.report_generator import generate_report

        key = await generate_report(assessment.id, db)

    assert str(assessment.id) in key


def test_score_color_bands() -> None:
    """_score_color returns distinct colors for each risk tier."""
    from app.services.report_generator import _score_color

    assert _score_color(80) == "#2e7d32"  # green — low
    assert _score_color(60) == "#f57c00"  # amber — medium
    assert _score_color(35) == "#c62828"  # red   — high
    assert _score_color(10) == "#7b1fa2"  # purple — critical


def test_tier_color() -> None:
    """_tier_color returns the right color for each named tier."""
    from app.services.report_generator import _tier_color

    assert _tier_color("low") == "#2e7d32"
    assert _tier_color("medium") == "#f57c00"
    assert _tier_color("high") == "#c62828"
    assert _tier_color("critical") == "#7b1fa2"
    assert _tier_color("unknown") == "#546e7a"  # fallback
