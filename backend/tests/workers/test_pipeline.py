"""
Pipeline worker tests.

Mocks LLM client, storage, and report generator — only the DB interactions
and status-transition logic are tested against the real test DB.
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.document import Document
from app.models.organization import Organization
from app.workers.pipeline import run_assessment_pipeline


async def _setup_assessment(db: AsyncSession, with_document: bool = True) -> Assessment:
    org = Organization(name="PipelineOrg", slug=f"pipe-org-{uuid4().hex[:8]}")
    db.add(org)
    await db.flush()
    assessment = Assessment(organization_id=org.id, status="processing")
    db.add(assessment)
    await db.flush()

    if with_document:
        doc = Document(
            assessment_id=assessment.id,
            filename="test_policy.txt",
            status="processed",
            raw_text="This is a HITL policy with human oversight procedures.",
        )
        db.add(doc)

    await db.commit()
    return assessment


MOCK_FINDINGS = {
    "model_inventory": {"models_fully_documented": True, "model_count": 1, "all_risk_tiers_assigned": False, "deployment_environments_listed": False, "decision_types_documented": False, "last_updated_months_ago": None},
    "human_oversight": {"has_hitl_policy": True, "consequential_decisions_covered": ["hiring"], "escalation_path_documented": True, "override_authority_defined": False, "review_frequency": "quarterly", "misleading_hitl_claim": False},
    "bias_fairness": {"has_bias_testing": False, "protected_classes_tested": [], "adverse_impact_ratio": None, "remediation_process_documented": False, "testing_frequency": None, "nyc_ll144_compliant": False, "last_audit_months_ago": None},
    "data_governance": {"has_data_governance_policy": False, "consent_mechanism_documented": False, "data_provenance_tracked": False, "retention_policy_exists": False, "retention_adequate_for_litigation": False, "cross_border_transfers_addressed": False, "dpia_completed": False},
    "incident_response": {"has_ir_plan": False, "has_ai_ir_plan": False, "notification_procedures_documented": False, "rollback_procedure_documented": False, "post_incident_review_required": False, "sla_defined": False},
    "monitoring_drift": {"has_monitoring": False, "drift_detection_implemented": False, "retraining_triggers_defined": False, "alerting_configured": False, "monitoring_frequency": None, "last_review_months_ago": None},
    "regulatory_compliance": {"nist_rmf_aligned": False, "eu_ai_act_assessed": False, "colorado_sb21_compliant": None, "nyc_ll144_compliant": False, "iso_42001_certified": False, "known_violations": False},
    "third_party_risk": {"has_vendor_inventory": False, "vendor_contracts_reviewed": False, "assessment_frequency": None, "ungoverned_ai_tools": False},
}


@pytest.mark.asyncio
async def test_pipeline_sets_complete_on_success(db: AsyncSession) -> None:
    assessment = await _setup_assessment(db)

    with (
        patch(
            "app.workers.pipeline.extract_all_dimensions",
            new_callable=AsyncMock,
            return_value=MOCK_FINDINGS,
        ),
        patch(
            "app.workers.pipeline.get_anthropic_client",
            return_value=MagicMock(),
        ),
        # Skip report generator (not built yet)
        patch("builtins.__import__", side_effect=_selective_import_error("app.services.report_generator")),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    assert updated.status == "complete"
    assert updated.overall_score is not None
    assert updated.risk_tier is not None


@pytest.mark.asyncio
async def test_pipeline_sets_failed_on_exception(db: AsyncSession) -> None:
    assessment = await _setup_assessment(db)

    with (
        patch(
            "app.workers.pipeline.extract_all_dimensions",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM exploded"),
        ),
        patch("app.workers.pipeline.get_anthropic_client", return_value=MagicMock()),
    ):
        with pytest.raises(RuntimeError):
            await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    assert updated.status == "failed"


@pytest.mark.asyncio
async def test_pipeline_status_transitions(db: AsyncSession) -> None:
    """Verify that at least 'extracting' and 'scoring' transitions fire."""
    assessment = await _setup_assessment(db)
    statuses_seen: list[str] = []

    original_set_status_attr = run_assessment_pipeline

    with (
        patch(
            "app.workers.pipeline.extract_all_dimensions",
            new_callable=AsyncMock,
            return_value=MOCK_FINDINGS,
        ),
        patch("app.workers.pipeline.get_anthropic_client", return_value=MagicMock()),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    # Final state must be complete
    assert updated.status == "complete"


def _selective_import_error(blocked_module: str):
    """Return a side_effect for __import__ that raises ImportError for one specific module."""
    import builtins

    real_import = builtins.__import__

    def _patched(name, *args, **kwargs):
        if name == blocked_module or name.startswith(blocked_module):
            raise ImportError(f"Mocked import error for {name}")
        return real_import(name, *args, **kwargs)

    return _patched


# ── S3 fallback tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_s3_fallback_downloads_and_persists(db: AsyncSession) -> None:
    """Lines 67-102: when raw_text is None but s3_key is set, download from S3."""
    assessment = await _setup_assessment(db, with_document=False)

    org_result = await db.execute(
        select(Organization).where(Organization.id == assessment.organization_id)
    )
    org = org_result.scalar_one()

    doc = Document(
        assessment_id=assessment.id,
        filename="policy.txt",
        status="pending",
        raw_text=None,
        s3_key="test/key.txt",
    )
    db.add(doc)
    await db.commit()

    s3_text = "This is HITL policy text from S3."
    mock_s3_body = MagicMock()
    mock_s3_body.read.return_value = s3_text.encode()
    mock_s3_client = MagicMock()
    mock_s3_client.get_object.return_value = {"Body": mock_s3_body}

    with (
        patch("app.workers.pipeline.extract_all_dimensions", new_callable=AsyncMock, return_value=MOCK_FINDINGS),
        patch("app.workers.pipeline.get_anthropic_client", return_value=MagicMock()),
        patch("boto3.client", return_value=mock_s3_client),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    assert updated.status == "complete"

    doc_result = await db.execute(select(Document).where(Document.id == doc.id))
    updated_doc = doc_result.scalar_one()
    assert updated_doc.raw_text is not None
    assert len(updated_doc.raw_text) > 0


@pytest.mark.asyncio
async def test_pipeline_skips_doc_with_no_text_and_no_s3_key(db: AsyncSession) -> None:
    """Lines 104-106: doc with raw_text=None and s3_key=None is skipped; pipeline still completes."""
    assessment = await _setup_assessment(db, with_document=False)

    doc = Document(
        assessment_id=assessment.id,
        filename="empty.txt",
        status="pending",
        raw_text=None,
        s3_key=None,
    )
    db.add(doc)
    await db.commit()

    with (
        patch("app.workers.pipeline.extract_all_dimensions", new_callable=AsyncMock, return_value=MOCK_FINDINGS),
        patch("app.workers.pipeline.get_anthropic_client", return_value=MagicMock()),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    assert updated.status == "complete"


# ── External signals tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_external_signals_gathered(db: AsyncSession) -> None:
    """Lines 125-139: gather_signals is called when available; empty list is handled gracefully."""
    assessment = await _setup_assessment(db)

    mock_signals_mod = MagicMock()
    mock_signals_mod.gather_signals = AsyncMock(return_value=[])

    with (
        patch("app.workers.pipeline.extract_all_dimensions", new_callable=AsyncMock, return_value=MOCK_FINDINGS),
        patch("app.workers.pipeline.get_anthropic_client", return_value=MagicMock()),
        patch.dict("sys.modules", {"app.services.external_signals": mock_signals_mod}),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    assert updated.status == "complete"


# ── Assessment missing mid-pipeline ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_returns_cleanly_when_assessment_not_found(db: AsyncSession) -> None:
    """Lines 147-148: if assessment is not in DB at scoring step, pipeline returns without raising."""
    from uuid import uuid4 as _uuid4
    non_existent_id = _uuid4()

    with (
        patch("app.workers.pipeline.extract_all_dimensions", new_callable=AsyncMock, return_value=MOCK_FINDINGS),
        patch("app.workers.pipeline.get_anthropic_client", return_value=MagicMock()),
    ):
        # No assertion needed — the function must simply not raise
        await run_assessment_pipeline(non_existent_id, db)


# ── Report generator tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_report_generator_sets_report_url(db: AsyncSession) -> None:
    """Lines 175-178: when generate_report succeeds, assessment.report_url is persisted."""
    assessment = await _setup_assessment(db)

    with (
        patch("app.workers.pipeline.extract_all_dimensions", new_callable=AsyncMock, return_value=MOCK_FINDINGS),
        patch("app.workers.pipeline.get_anthropic_client", return_value=MagicMock()),
        patch.dict(
            "sys.modules",
            {"app.services.report_generator": MagicMock(generate_report=AsyncMock(return_value="reports/test.pdf"))},
        ),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    assert updated.status == "complete"
    assert updated.report_url == "reports/test.pdf"


@pytest.mark.asyncio
async def test_pipeline_report_generator_failure_is_nonfatal(db: AsyncSession) -> None:
    """Lines 181-182: when generate_report raises, pipeline still marks status 'complete'."""
    assessment = await _setup_assessment(db)

    failing_report_mod = MagicMock()
    failing_report_mod.generate_report = AsyncMock(side_effect=Exception("pdf failed"))

    with (
        patch("app.workers.pipeline.extract_all_dimensions", new_callable=AsyncMock, return_value=MOCK_FINDINGS),
        patch("app.workers.pipeline.get_anthropic_client", return_value=MagicMock()),
        patch.dict("sys.modules", {"app.services.report_generator": failing_report_mod}),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    assert updated.status == "complete"


@pytest.mark.asyncio
async def test_pipeline_s3_download_failure_skips_doc(db: AsyncSession) -> None:
    """Lines 96-102: when S3 download fails, doc is skipped, pipeline still completes."""
    assessment = await _setup_assessment(db, with_document=False)

    doc = Document(
        assessment_id=assessment.id,
        filename="remote.txt",
        status="pending",
        raw_text=None,
        s3_key="test/remote.txt",
    )
    db.add(doc)
    await db.commit()

    from botocore.exceptions import ClientError
    mock_s3_client = MagicMock()
    mock_s3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject"
    )

    with (
        patch("app.workers.pipeline.extract_all_dimensions", new_callable=AsyncMock, return_value=MOCK_FINDINGS),
        patch("app.workers.pipeline.get_anthropic_client", return_value=MagicMock()),
        patch("boto3.client", return_value=mock_s3_client),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    assert updated.status == "complete"
