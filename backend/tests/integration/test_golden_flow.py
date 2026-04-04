"""
Golden flow integration test — QuickHire (company_b) end-to-end pipeline.

Uses pre-computed extraction findings (matching the calibrated QuickHire persona
from test_scoring_engine.py) to bypass the LLM extraction step and test
everything from scoring through to report generation.

Success criteria (from CLAUDE.md):
  - overall_score in [48, 58]
  - risk_tier == "medium"
  - 5 critical flags: ChatGPT ungoverned, EEOC complaint, LL144 non-compliance,
    no AI-specific IR plan, HITL senior-only

The report_generator is mocked to avoid requiring WeasyPrint + real S3 in CI.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.document import Document
from app.models.organization import Organization
from app.workers.pipeline import run_assessment_pipeline

# ── QuickHire extraction findings (calibrated persona) ───────────────────────
# Copied from tests/services/test_scoring_engine.py — these are the ground-truth
# findings that must produce a score in [48, 58] with all 5 critical flags.

QUICKHIRE_FINDINGS: dict[str, dict] = {
    "model_inventory": {
        "has_formal_inventory": True,
        "models_fully_documented": False,
        "risk_classification_present": False,
        "deployment_env_documented": True,
        "decision_types_documented": True,
        "inventory_months_old": 18,
        "undocumented_systems": ["candidate_job_matcher", "chatgpt_integration"],
        "chatgpt_or_third_party_undisclosed": True,
    },
    "human_oversight": {
        "has_hitl_policy": True,
        "hitl_scope": "senior_only",
        "escalation_path_documented": True,
        "override_authority_defined": True,
        "review_frequency": None,
        "misleading_hitl_claim": True,
        "hitl_policy_months_old": None,
    },
    "bias_fairness": {
        "has_bias_audit": True,
        "impact_ratios_documented": True,
        "impact_ratios_above_threshold": True,
        "impact_ratios_borderline": True,
        "third_party_auditor": False,
        "audit_cadence": "at_launch_only",
        "protected_classes_count": 2,
        "remediation_documented": False,
        "audit_months_old": 36,
        "active_eeoc_or_complaint": True,
        "nyc_ll144_applies": True,
        "nyc_ll144_compliant": False,
        "nyc_ll144_independent_auditor_required": True,
    },
    "data_governance": {
        "has_data_governance_policy": True,
        "policy_is_ai_specific": False,
        "training_data_provenance_documented": True,
        "consent_mechanism_documented": True,
        "retention_policy_exists": True,
        "retention_adequate_for_litigation": False,
        "cross_border_transfer_policy": False,
        "dpia_completed": False,
        "processes_sensitive_data": False,
        "candidate_right_to_explanation": False,
        "policy_months_old": None,
    },
    "incident_response": {
        "has_ai_ir_plan": False,
        "incident_classification_defined": False,
        "regulator_notification_procedure": True,
        "post_incident_review_required": False,
        "rollback_procedures_documented": True,
        "ir_plan_months_old": None,
        "active_incidents_or_complaints": True,
        "active_litigation": False,
    },
    "monitoring_drift": {
        "has_monitoring_documentation": True,
        "drift_detection_methodology": True,
        "retraining_triggers_defined": True,
        "alerting_mechanism_documented": False,
        "monitoring_months_old": None,
        "vague_monitoring_reference_only": False,
    },
    "regulatory_compliance": {
        "framework_alignment": ["nist_ai_100_1"],
        "nyc_ll144_applies": True,
        "nyc_ll144_compliant": False,
        "colorado_sb21_169_applies": False,
        "eu_ai_act_classification_documented": False,
        "active_regulatory_inquiry": False,
        "active_litigation": False,
        "general_legal_awareness": True,
        "compliance_months_old": None,
    },
    "third_party_risk": {
        "has_vendor_ai_inventory": True,
        "vendor_risk_assessments_completed": True,
        "contractual_ai_protections_documented": False,
        "assessment_frequency_defined": False,
        "undocumented_third_party_ai": ["chatgpt_api"],
        "candidate_or_customer_data_shared_with_vendor": True,
        "assessment_months_old": None,
    },
}


# ── Full pipeline golden flow (DB required) ──────────────────────────────────


async def _seed_quickhire(db: AsyncSession) -> Assessment:
    """Create QuickHire org + assessment + 3 sample documents in the test DB."""
    org = Organization(name="QuickHire Inc.", slug="quickhire-golden")
    db.add(org)
    await db.flush()

    assessment = Assessment(organization_id=org.id, status="pending")
    db.add(assessment)
    await db.flush()

    # Sample documents — text content is irrelevant (LLM extraction is mocked)
    for filename, doc_type, text in [
        ("model_card_resume_screener.txt", "model_card", "QuickHire resume screening model card."),
        ("hitl_policy_v2_jan2026.txt", "hitl_policy", "HITL policy: VP and above review AI decisions."),
        ("it_incident_response_policy.txt", "incident_response", "IT incident response procedures."),
    ]:
        doc = Document(
            assessment_id=assessment.id,
            filename=filename,
            doc_type=doc_type,
            status="processed",
            raw_text=text,
        )
        db.add(doc)

    await db.commit()
    return assessment


@pytest.mark.asyncio
async def test_golden_flow_pipeline_complete_status(db: AsyncSession) -> None:
    """Full pipeline must set status='complete' for QuickHire."""
    assessment = await _seed_quickhire(db)

    with (
        patch(
            "app.workers.pipeline.extract_all_dimensions",
            new_callable=AsyncMock,
            return_value=QUICKHIRE_FINDINGS,
        ),
        patch("app.workers.pipeline.get_anthropic_client", return_value=None),
        # Mock report generator — avoid WeasyPrint + real S3 in integration tests
        patch.dict(
            "sys.modules",
            {
                "app.services.report_generator": type(
                    "mod",
                    (),
                    {"generate_report": AsyncMock(return_value=f"reports/{assessment.id}/risk_report.pdf")},
                )()
            },
        ),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    assert updated.status == "complete"


@pytest.mark.asyncio
async def test_golden_flow_score_in_target_range(db: AsyncSession) -> None:
    """Pipeline must produce overall_score in [48, 58] for QuickHire."""
    assessment = await _seed_quickhire(db)

    with (
        patch(
            "app.workers.pipeline.extract_all_dimensions",
            new_callable=AsyncMock,
            return_value=QUICKHIRE_FINDINGS,
        ),
        patch("app.workers.pipeline.get_anthropic_client", return_value=None),
        patch.dict(
            "sys.modules",
            {
                "app.services.report_generator": type(
                    "mod",
                    (),
                    {"generate_report": AsyncMock(return_value=f"reports/{assessment.id}/risk_report.pdf")},
                )()
            },
        ),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()

    assert updated.overall_score is not None
    assert 48 <= updated.overall_score <= 58, f"QuickHire overall_score {updated.overall_score:.2f} not in [48, 58]"
    assert updated.risk_tier == "medium"


@pytest.mark.asyncio
async def test_golden_flow_five_critical_flags_in_db(db: AsyncSession) -> None:
    """Pipeline must persist all 5 required critical flags in assessment.flags."""
    assessment = await _seed_quickhire(db)

    with (
        patch(
            "app.workers.pipeline.extract_all_dimensions",
            new_callable=AsyncMock,
            return_value=QUICKHIRE_FINDINGS,
        ),
        patch("app.workers.pipeline.get_anthropic_client", return_value=None),
        patch.dict(
            "sys.modules",
            {
                "app.services.report_generator": type(
                    "mod",
                    (),
                    {"generate_report": AsyncMock(return_value=f"reports/{assessment.id}/risk_report.pdf")},
                )()
            },
        ),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()

    all_flags: list[dict] = (updated.flags or {}).get("all_flags", [])
    critical_flags = [f for f in all_flags if f.get("severity") == "critical"]
    flag_texts = " ".join(f.get("text", "") for f in critical_flags)

    assert any(
        "ChatGPT" in t or "Third-party AI" in t or "undisclosed" in t.lower()
        for t in (f.get("text", "") for f in critical_flags)
    ), f"Missing ChatGPT flag. Critical flags: {flag_texts}"

    assert any("EEOC" in f.get("text", "") for f in critical_flags), f"Missing EEOC flag. Critical flags: {flag_texts}"

    assert any("144" in f.get("text", "") or "LL144" in f.get("text", "") for f in critical_flags), (
        f"Missing LL144 flag. Critical flags: {flag_texts}"
    )

    assert any(
        "incident response" in f.get("text", "").lower() or "IR plan" in f.get("text", "") for f in critical_flags
    ), f"Missing IR plan flag. Critical flags: {flag_texts}"

    assert any(
        "senior" in f.get("text", "").lower()
        or "HITL" in f.get("text", "")
        or "misleading" in f.get("text", "").lower()
        for f in critical_flags
    ), f"Missing HITL flag. Critical flags: {flag_texts}"


@pytest.mark.asyncio
async def test_golden_flow_report_url_set(db: AsyncSession) -> None:
    """Pipeline must set assessment.report_url after report generation."""
    assessment = await _seed_quickhire(db)
    expected_key = f"reports/{assessment.id}/risk_report.pdf"

    with (
        patch(
            "app.workers.pipeline.extract_all_dimensions",
            new_callable=AsyncMock,
            return_value=QUICKHIRE_FINDINGS,
        ),
        patch("app.workers.pipeline.get_anthropic_client", return_value=None),
        patch.dict(
            "sys.modules",
            {
                "app.services.report_generator": type(
                    "mod",
                    (),
                    {"generate_report": AsyncMock(return_value=expected_key)},
                )()
            },
        ),
    ):
        await run_assessment_pipeline(assessment.id, db)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment.id))
    updated = result.scalar_one()
    assert updated.report_url == expected_key
