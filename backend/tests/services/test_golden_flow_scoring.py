"""
Golden flow scoring tests - pure unit tests, no DB or network required.

Validates that the QuickHire (company_b) extraction findings produce:
  - overall_score in [48, 58]
  - risk_tier == "medium"
  - All required critical flags

Fixture values are calibrated against live LLM extraction evidence from two
pipeline runs. Key staleness values reflect actual document dates:
  - hitl_policy_v2_jan2026.txt: Jan 15 2026 -> 3 months old (April 2026)
  - initial_bias_audit_2024.txt: March 2023 -> 37 months old
  - data_retention_policy.txt: Jan 2024 -> ~28 months old
  - ai_tools_and_vendor_policy.txt: ~Nov 2024 -> ~17 months old
"""

from app.services.scoring_engine import score_assessment

QUICKHIRE_FINDINGS: dict[str, dict] = {
    "model_inventory": {
        "has_formal_inventory": True,
        "models_fully_documented": True,
        "risk_classification_present": False,
        "deployment_env_documented": True,
        "decision_types_documented": True,
        "inventory_months_old": 17,
        "undocumented_systems": [
            "OpenAI API (GPT-4) - cover letter quality scoring (beta); explicitly flagged as NOT GOVERNED with no security review, DPA, or formal vendor agreement completed"
        ],
        "chatgpt_or_third_party_undisclosed": True,
    },
    "human_oversight": {
        "has_hitl_policy": True,
        "hitl_scope": "partial",
        "escalation_path_documented": True,
        "override_authority_defined": True,
        "review_frequency": None,
        "misleading_hitl_claim": True,
        "hitl_policy_months_old": 3,
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
        "audit_months_old": 37,
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
        "policy_months_old": 28,
    },
    "incident_response": {
        "has_ai_ir_plan": False,
        "incident_classification_defined": False,
        "regulator_notification_procedure": True,
        "post_incident_review_required": False,
        "rollback_procedures_documented": True,
        "ir_plan_months_old": None,
        "active_incidents_or_complaints": True,
        "active_litigation": True,
    },
    "monitoring_drift": {
        "has_monitoring_documentation": True,
        "drift_detection_methodology": True,
        "retraining_triggers_defined": True,
        "alerting_mechanism_documented": True,
        "monitoring_months_old": None,
        "vague_monitoring_reference_only": False,
    },
    "regulatory_compliance": {
        "framework_alignment": [],
        "nyc_ll144_applies": True,
        "nyc_ll144_compliant": False,
        "colorado_sb21_169_applies": False,
        "eu_ai_act_classification_documented": False,
        "active_regulatory_inquiry": True,
        "active_litigation": True,
        "general_legal_awareness": True,
        "compliance_months_old": 17,
    },
    "third_party_risk": {
        "has_vendor_ai_inventory": True,
        "vendor_risk_assessments_completed": True,
        "contractual_ai_protections_documented": False,
        "assessment_frequency_defined": False,
        "undocumented_third_party_ai": [
            "OpenAI API (GPT-4) - used for candidate cover letter scoring during beta evaluation with candidate personal data shared; no DPA, no security review, no formal AI-specific vendor agreement completed"
        ],
        "candidate_or_customer_data_shared_with_vendor": True,
        "assessment_months_old": None,
    },
}


def test_quickhire_score_in_target_range() -> None:
    """Scoring engine must produce [48, 58] for the calibrated QuickHire findings."""
    result = score_assessment(QUICKHIRE_FINDINGS)
    assert 48 <= result.overall_score <= 58, f"QuickHire overall_score {result.overall_score:.2f} not in [48, 58]"
    assert result.risk_tier == "medium"


def test_quickhire_all_critical_flags_present() -> None:
    """All required critical flags must be present in the scoring output."""
    result = score_assessment(QUICKHIRE_FINDINGS)
    critical_flags = [f for f in result.all_flags if f["severity"] == "critical"]
    flag_texts = " | ".join(f["text"] for f in critical_flags)

    # 1. ChatGPT / ungoverned third-party AI
    assert any(
        "ChatGPT" in f["text"] or "Third-party AI" in f["text"] or "undisclosed" in f["text"].lower()
        for f in critical_flags
    ), f"Missing ChatGPT/ungoverned flag. All critical: {flag_texts}"

    # 2. Active EEOC complaint
    assert any("EEOC" in f["text"] for f in critical_flags), f"Missing EEOC complaint flag. All critical: {flag_texts}"

    # 3. NYC LL144 non-compliance
    assert any("144" in f["text"] or "LL144" in f["text"] for f in critical_flags), (
        f"Missing LL144 flag. All critical: {flag_texts}"
    )

    # 4. No AI-specific incident response plan
    assert any(
        "incident response" in f["text"].lower() or "IR plan" in f["text"] or "no ai" in f["text"].lower()
        for f in critical_flags
    ), f"Missing IR plan flag. All critical: {flag_texts}"

    # 5. Active litigation exposure
    assert any("litigation" in f["text"].lower() for f in critical_flags), (
        f"Missing active litigation flag. All critical: {flag_texts}"
    )
