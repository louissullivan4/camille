import pytest

from app.services.scoring_engine import (
    get_staleness_multiplier,
    score_assessment,
)
from app.services.scoring_rules.bias_fairness import score_bias_fairness
from app.services.scoring_rules.data_governance import score_data_governance
from app.services.scoring_rules.human_oversight import score_human_oversight
from app.services.scoring_rules.incident_response import score_incident_response
from app.services.scoring_rules.model_inventory import score_model_inventory
from app.services.scoring_rules.monitoring_drift import score_monitoring_drift
from app.services.scoring_rules.regulatory_compliance import score_regulatory_compliance
from app.services.scoring_rules.third_party_risk import score_third_party_risk

# ---------------------------------------------------------------------------
# Staleness tests
# ---------------------------------------------------------------------------


def test_staleness_not_stale():
    assert get_staleness_multiplier(6) == 1.0


def test_staleness_12_months():
    assert get_staleness_multiplier(12) == 1.0


def test_staleness_13_months():
    assert get_staleness_multiplier(13) == 0.75


def test_staleness_24_months():
    assert get_staleness_multiplier(24) == 0.75


def test_staleness_25_months():
    assert get_staleness_multiplier(25) == 0.5


def test_staleness_none():
    assert get_staleness_multiplier(None) == 1.0


# ---------------------------------------------------------------------------
# No-documentation critical flag (across dimensions)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scorer",
    [
        score_model_inventory,
        score_human_oversight,
        score_bias_fairness,
        score_data_governance,
        score_incident_response,
        score_monitoring_drift,
        score_regulatory_compliance,
        score_third_party_risk,
    ],
)
def test_no_documentation_produces_critical_flag(scorer):
    result = scorer({"no_documentation_provided": True})
    assert result.score == 0
    critical = [f for f in result.flags if f["severity"] == "critical"]
    assert len(critical) >= 1


# ---------------------------------------------------------------------------
# Human oversight
# ---------------------------------------------------------------------------


def test_hitl_senior_only_scores_partial_credit():
    findings = {
        "has_hitl_policy": True,
        "hitl_scope": "senior_only",
        "escalation_path_documented": False,
        "override_authority_defined": False,
        "review_frequency": None,
        "misleading_hitl_claim": False,
        "hitl_policy_months_old": None,
    }
    result = score_human_oversight(findings)
    assert result.score < 50
    critical = [f for f in result.flags if f["severity"] == "critical"]
    assert len(critical) >= 1


def test_full_hitl_scores_maximum():
    findings = {
        "has_hitl_policy": True,
        "hitl_scope": "all_consequential",
        "escalation_path_documented": True,
        "override_authority_defined": True,
        "review_frequency": "quarterly",
        "misleading_hitl_claim": False,
        "hitl_policy_months_old": None,
    }
    result = score_human_oversight(findings)
    assert result.score == 100
    assert result.flags == []


# ---------------------------------------------------------------------------
# Bias fairness
# ---------------------------------------------------------------------------


def test_stale_audit_applies_staleness_penalty():
    """
    Bias fairness uses a presence+quality split.
    Only the quality bucket is staleness-penalized.
    Presence: has_audit(10) + impact_ratios(10) + above_threshold(10) + 3_classes(15) = 45
    Quality:  third_party(20) + annual(15) + remediation(15) = 50 -> *0.5 (36mo > 24mo) = 25
    Total = 70.0
    """
    findings = {
        "has_bias_audit": True,
        "impact_ratios_documented": True,
        "impact_ratios_above_threshold": True,
        "impact_ratios_borderline": False,
        "third_party_auditor": True,
        "audit_cadence": "annual",
        "protected_classes_count": 3,
        "remediation_documented": True,
        "audit_months_old": 36,
        "active_eeoc_or_complaint": False,
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "nyc_ll144_independent_auditor_required": False,
    }
    # presence=45, quality=50, quality*0.5 (36mo > 24mo)=25, total=70.0
    result = score_bias_fairness(findings)
    assert result.score == pytest.approx(70.0, abs=0.01)
    staleness_flags = [f for f in result.flags if "staleness" in f["text"]]
    assert len(staleness_flags) == 1


def test_active_eeoc_is_critical_flag():
    findings = {
        "has_bias_audit": False,
        "impact_ratios_documented": False,
        "impact_ratios_above_threshold": False,
        "impact_ratios_borderline": False,
        "third_party_auditor": False,
        "audit_cadence": None,
        "protected_classes_count": 0,
        "remediation_documented": False,
        "audit_months_old": None,
        "active_eeoc_or_complaint": True,
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "nyc_ll144_independent_auditor_required": False,
    }
    result = score_bias_fairness(findings)
    critical = [f for f in result.flags if f["severity"] == "critical"]
    assert any("EEOC" in f["text"] for f in critical)


def test_ll144_noncompliance_is_critical_flag():
    findings = {
        "has_bias_audit": True,
        "impact_ratios_documented": False,
        "impact_ratios_above_threshold": False,
        "impact_ratios_borderline": False,
        "third_party_auditor": False,
        "audit_cadence": "annual",
        "protected_classes_count": 2,
        "remediation_documented": False,
        "audit_months_old": None,
        "active_eeoc_or_complaint": False,
        "nyc_ll144_applies": True,
        "nyc_ll144_compliant": False,
        "nyc_ll144_independent_auditor_required": False,
    }
    result = score_bias_fairness(findings)
    critical = [f for f in result.flags if f["severity"] == "critical"]
    assert any("LL144" in f["text"] or "144" in f["text"] for f in critical)


# ---------------------------------------------------------------------------
# Incident response
# ---------------------------------------------------------------------------


def test_missing_ir_plan_is_critical_flag():
    findings = {
        "has_ai_ir_plan": False,
        "incident_classification_defined": False,
        "regulator_notification_procedure": False,
        "post_incident_review_required": False,
        "rollback_procedures_documented": False,
        "ir_plan_months_old": None,
        "active_incidents_or_complaints": False,
        "active_litigation": False,
    }
    result = score_incident_response(findings)
    critical = [f for f in result.flags if f["severity"] == "critical"]
    assert len(critical) >= 1


def test_no_ir_plan_scores_zero_with_critical_flag():
    findings = {
        "has_ai_ir_plan": False,
        "incident_classification_defined": False,
        "regulator_notification_procedure": False,
        "post_incident_review_required": False,
        "rollback_procedures_documented": False,
        "ir_plan_months_old": None,
        "active_incidents_or_complaints": False,
        "active_litigation": False,
    }
    result = score_incident_response(findings)
    assert result.score == 0
    critical = [f for f in result.flags if f["severity"] == "critical"]
    assert len(critical) >= 1


def test_full_ir_plan_scores_high():
    findings = {
        "has_ai_ir_plan": True,
        "incident_classification_defined": True,
        "regulator_notification_procedure": True,
        "post_incident_review_required": True,
        "rollback_procedures_documented": True,
        "ir_plan_months_old": None,
        "active_incidents_or_complaints": False,
        "active_litigation": False,
    }
    result = score_incident_response(findings)
    assert result.score == 100
    assert result.flags == []


# ---------------------------------------------------------------------------
# Score assessment orchestrator
# ---------------------------------------------------------------------------

_MINIMAL_FINDINGS: dict[str, dict] = {
    "model_inventory": {
        "has_formal_inventory": False,
        "models_fully_documented": False,
        "risk_classification_present": False,
        "deployment_env_documented": False,
        "decision_types_documented": False,
        "inventory_months_old": None,
        "undocumented_systems": [],
        "chatgpt_or_third_party_undisclosed": False,
    },
    "human_oversight": {
        "has_hitl_policy": False,
        "hitl_scope": "none",
        "escalation_path_documented": False,
        "override_authority_defined": False,
        "review_frequency": None,
        "misleading_hitl_claim": False,
        "hitl_policy_months_old": None,
    },
    "bias_fairness": {
        "has_bias_audit": False,
        "impact_ratios_documented": False,
        "impact_ratios_above_threshold": False,
        "impact_ratios_borderline": False,
        "third_party_auditor": False,
        "audit_cadence": None,
        "protected_classes_count": 0,
        "remediation_documented": False,
        "audit_months_old": None,
        "active_eeoc_or_complaint": False,
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "nyc_ll144_independent_auditor_required": False,
    },
    "data_governance": {
        "has_data_governance_policy": False,
        "policy_is_ai_specific": False,
        "training_data_provenance_documented": False,
        "consent_mechanism_documented": False,
        "retention_policy_exists": False,
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
        "regulator_notification_procedure": False,
        "post_incident_review_required": False,
        "rollback_procedures_documented": False,
        "ir_plan_months_old": None,
        "active_incidents_or_complaints": False,
        "active_litigation": False,
    },
    "monitoring_drift": {
        "has_monitoring_documentation": False,
        "drift_detection_methodology": False,
        "retraining_triggers_defined": False,
        "alerting_mechanism_documented": False,
        "monitoring_months_old": None,
        "vague_monitoring_reference_only": False,
    },
    "regulatory_compliance": {
        "framework_alignment": [],
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "colorado_sb21_169_applies": False,
        "eu_ai_act_classification_documented": False,
        "active_regulatory_inquiry": False,
        "active_litigation": False,
        "general_legal_awareness": False,
        "compliance_months_old": None,
    },
    "third_party_risk": {
        "has_vendor_ai_inventory": False,
        "vendor_risk_assessments_completed": False,
        "contractual_ai_protections_documented": False,
        "assessment_frequency_defined": False,
        "undocumented_third_party_ai": [],
        "candidate_or_customer_data_shared_with_vendor": False,
        "assessment_months_old": None,
    },
}

_PERFECT_FINDINGS: dict[str, dict] = {
    "model_inventory": {
        "has_formal_inventory": True,
        "models_fully_documented": True,
        "risk_classification_present": True,
        "deployment_env_documented": True,
        "decision_types_documented": True,
        "inventory_months_old": 1,
        "undocumented_systems": [],
        "chatgpt_or_third_party_undisclosed": False,
    },
    "human_oversight": {
        "has_hitl_policy": True,
        "hitl_scope": "all_consequential",
        "escalation_path_documented": True,
        "override_authority_defined": True,
        "review_frequency": "quarterly",
        "misleading_hitl_claim": False,
        "hitl_policy_months_old": 1,
    },
    "bias_fairness": {
        "has_bias_audit": True,
        "impact_ratios_documented": True,
        "impact_ratios_above_threshold": True,
        "impact_ratios_borderline": False,
        "third_party_auditor": True,
        "audit_cadence": "quarterly",
        "protected_classes_count": 5,
        "remediation_documented": True,
        "audit_months_old": 1,
        "active_eeoc_or_complaint": False,
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "nyc_ll144_independent_auditor_required": False,
    },
    "data_governance": {
        "has_data_governance_policy": True,
        "policy_is_ai_specific": True,
        "training_data_provenance_documented": True,
        "consent_mechanism_documented": True,
        "retention_policy_exists": True,
        "retention_adequate_for_litigation": True,
        "cross_border_transfer_policy": True,
        "dpia_completed": True,
        "processes_sensitive_data": False,
        "candidate_right_to_explanation": True,
        "policy_months_old": 1,
    },
    "incident_response": {
        "has_ai_ir_plan": True,
        "incident_classification_defined": True,
        "regulator_notification_procedure": True,
        "post_incident_review_required": True,
        "rollback_procedures_documented": True,
        "ir_plan_months_old": 1,
        "active_incidents_or_complaints": False,
        "active_litigation": False,
    },
    "monitoring_drift": {
        "has_monitoring_documentation": True,
        "drift_detection_methodology": True,
        "retraining_triggers_defined": True,
        "alerting_mechanism_documented": True,
        "monitoring_months_old": 1,
        "vague_monitoring_reference_only": False,
    },
    "regulatory_compliance": {
        "framework_alignment": ["nist_rmf", "eu_ai_act"],
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "colorado_sb21_169_applies": False,
        "eu_ai_act_classification_documented": True,
        "active_regulatory_inquiry": False,
        "active_litigation": False,
        "general_legal_awareness": True,
        "compliance_months_old": 1,
    },
    "third_party_risk": {
        "has_vendor_ai_inventory": True,
        "vendor_risk_assessments_completed": True,
        "contractual_ai_protections_documented": True,
        "assessment_frequency_defined": True,
        "undocumented_third_party_ai": [],
        "candidate_or_customer_data_shared_with_vendor": False,
        "assessment_months_old": 1,
    },
}


def test_carrier_weight_override_respected():
    # With higher human_oversight weight, a company with perfect HO but no MI should score higher
    config_a = {"weight_overrides": {"human_oversight": 0.40, "model_inventory": 0.0}}
    config_b = {"weight_overrides": {"human_oversight": 0.10, "model_inventory": 0.30}}

    findings = dict(_MINIMAL_FINDINGS)
    findings["human_oversight"] = {
        "has_hitl_policy": True,
        "hitl_scope": "all_consequential",
        "escalation_path_documented": True,
        "override_authority_defined": True,
        "review_frequency": "quarterly",
        "misleading_hitl_claim": False,
        "hitl_policy_months_old": None,
    }

    result_a = score_assessment(findings, config_a)
    result_b = score_assessment(findings, config_b)
    assert result_a.overall_score > result_b.overall_score


def test_risk_tier_low():
    result = score_assessment(_PERFECT_FINDINGS)
    assert result.overall_score >= 75
    assert result.risk_tier == "low"


def test_risk_tier_medium():
    # Give human_oversight and incident_response full marks, rest minimal
    findings = dict(_MINIMAL_FINDINGS)
    findings["human_oversight"] = {
        "has_hitl_policy": True,
        "hitl_scope": "all_consequential",
        "escalation_path_documented": True,
        "override_authority_defined": True,
        "review_frequency": "quarterly",
        "misleading_hitl_claim": False,
        "hitl_policy_months_old": None,
    }
    findings["model_inventory"] = {
        "has_formal_inventory": True,
        "models_fully_documented": True,
        "risk_classification_present": True,
        "deployment_env_documented": True,
        "decision_types_documented": True,
        "inventory_months_old": None,
        "undocumented_systems": [],
        "chatgpt_or_third_party_undisclosed": False,
    }
    findings["incident_response"] = {
        "has_ai_ir_plan": True,
        "incident_classification_defined": True,
        "regulator_notification_procedure": True,
        "post_incident_review_required": True,
        "rollback_procedures_documented": True,
        "ir_plan_months_old": None,
        "active_incidents_or_complaints": False,
        "active_litigation": False,
    }
    findings["bias_fairness"] = {
        "has_bias_audit": True,
        "impact_ratios_documented": True,
        "impact_ratios_above_threshold": True,
        "impact_ratios_borderline": False,
        "third_party_auditor": False,
        "audit_cadence": "annual",
        "protected_classes_count": 2,
        "remediation_documented": False,
        "audit_months_old": None,
        "active_eeoc_or_complaint": False,
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "nyc_ll144_independent_auditor_required": False,
    }
    result = score_assessment(findings)
    assert 50 <= result.overall_score < 75
    assert result.risk_tier == "medium"


def test_risk_tier_high():
    # Give modest partial coverage across several dims to land in 25-49
    findings = dict(_MINIMAL_FINDINGS)
    findings["human_oversight"] = {
        "has_hitl_policy": True,
        "hitl_scope": "partial",
        "escalation_path_documented": True,
        "override_authority_defined": False,
        "review_frequency": None,
        "misleading_hitl_claim": False,
        "hitl_policy_months_old": None,
    }
    findings["incident_response"] = {
        "has_ai_ir_plan": True,
        "incident_classification_defined": False,
        "regulator_notification_procedure": False,
        "post_incident_review_required": False,
        "rollback_procedures_documented": False,
        "ir_plan_months_old": None,
        "active_incidents_or_complaints": False,
        "active_litigation": False,
    }
    findings["model_inventory"] = {
        "has_formal_inventory": True,
        "models_fully_documented": False,
        "risk_classification_present": False,
        "deployment_env_documented": False,
        "decision_types_documented": False,
        "inventory_months_old": None,
        "undocumented_systems": [],
        "chatgpt_or_third_party_undisclosed": False,
    }
    findings["data_governance"] = {
        "has_data_governance_policy": True,
        "policy_is_ai_specific": False,
        "training_data_provenance_documented": False,
        "consent_mechanism_documented": False,
        "retention_policy_exists": True,
        "retention_adequate_for_litigation": False,
        "cross_border_transfer_policy": False,
        "dpia_completed": False,
        "processes_sensitive_data": False,
        "candidate_right_to_explanation": False,
        "policy_months_old": None,
    }
    findings["regulatory_compliance"] = {
        "framework_alignment": [],
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "colorado_sb21_169_applies": False,
        "eu_ai_act_classification_documented": False,
        "active_regulatory_inquiry": False,
        "active_litigation": False,
        "general_legal_awareness": True,
        "compliance_months_old": None,
    }
    result = score_assessment(findings)
    assert 25 <= result.overall_score < 50, f"Expected high tier, got {result.overall_score}"
    assert result.risk_tier == "high"


def test_risk_tier_critical():
    result = score_assessment(_MINIMAL_FINDINGS)
    assert result.overall_score < 25
    assert result.risk_tier == "critical"


# ---------------------------------------------------------------------------
# Persona integration tests
# ---------------------------------------------------------------------------

# QuickHire (company_b) — medium risk HR Tech resume screening company
# Preserves all 5 required critical flags:
# 1. ChatGPT without governance (chatgpt_or_third_party_undisclosed)
# 2. EEOC complaint (active_eeoc_or_complaint)
# 3. LL144 noncompliance (nyc_ll144_compliant=False)
# 4. No AI-specific IR plan (has_ai_ir_plan=False)
# 5. HITL VP+ only (hitl_scope=senior_only)
#
# As a medium-risk company, QuickHire has some governance in place:
# partial model inventory (stale), general data governance, basic monitoring,
# and informal IR procedures — but critical gaps in AI-specific governance.

quickhire_findings: dict[str, dict] = {
    "model_inventory": {
        # Has a model card but it's 18 months old — stale (13-24mo = 0.75x)
        "has_formal_inventory": True,
        "models_fully_documented": False,
        "risk_classification_present": False,
        "deployment_env_documented": True,
        "decision_types_documented": True,
        "inventory_months_old": 18,
        "undocumented_systems": ["candidate_job_matcher", "chatgpt_integration"],
        "chatgpt_or_third_party_undisclosed": True,  # CRITICAL FLAG #1
    },
    "human_oversight": {
        "has_hitl_policy": True,
        "hitl_scope": "senior_only",  # CRITICAL FLAG #5: HITL VP+ only
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
        "audit_months_old": 36,  # 3 years stale (>24mo = 0.5x on quality)
        "active_eeoc_or_complaint": True,  # CRITICAL FLAG #2
        "nyc_ll144_applies": True,
        "nyc_ll144_compliant": False,  # CRITICAL FLAG #3
        "nyc_ll144_independent_auditor_required": True,  # CRITICAL: LL144 requires independent auditor
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
        "has_ai_ir_plan": False,  # CRITICAL FLAG #4: no AI-specific IR plan
        "incident_classification_defined": False,
        # Has general software incident procedures, not AI-specific:
        "regulator_notification_procedure": True,  # General regulatory notification exists
        "post_incident_review_required": False,
        "rollback_procedures_documented": True,  # Software rollback procedures exist
        "ir_plan_months_old": None,
        "active_incidents_or_complaints": True,
        "active_litigation": False,
    },
    "monitoring_drift": {
        # Has operational monitoring and retraining triggers but no drift detection
        "has_monitoring_documentation": True,
        "drift_detection_methodology": True,  # Basic performance drift tracking
        "retraining_triggers_defined": True,
        "alerting_mechanism_documented": False,
        "monitoring_months_old": None,
        "vague_monitoring_reference_only": False,
    },
    "regulatory_compliance": {
        # References NIST AI guidance in their documentation
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
        "vendor_risk_assessments_completed": True,  # Partial assessments completed for known vendors
        "contractual_ai_protections_documented": False,
        "assessment_frequency_defined": False,
        "undocumented_third_party_ai": ["chatgpt_api"],  # ChatGPT not in inventory -> CRITICAL
        "candidate_or_customer_data_shared_with_vendor": True,  # CRITICAL: no contractual protections
        "assessment_months_old": None,
    },
}

# GreenScore (company_a) — low risk Fintech ESG scoring company
greenscore_findings: dict[str, dict] = {
    "model_inventory": {
        "has_formal_inventory": True,
        "models_fully_documented": True,
        "risk_classification_present": True,
        "deployment_env_documented": True,
        "decision_types_documented": True,
        "inventory_months_old": 3,
        "undocumented_systems": [],
        "chatgpt_or_third_party_undisclosed": False,
    },
    "human_oversight": {
        "has_hitl_policy": True,
        "hitl_scope": "all_consequential",
        "escalation_path_documented": True,
        "override_authority_defined": True,
        "review_frequency": "quarterly",
        "misleading_hitl_claim": False,
        "hitl_policy_months_old": 3,
    },
    "bias_fairness": {
        "has_bias_audit": True,
        "impact_ratios_documented": True,
        "impact_ratios_above_threshold": True,
        "impact_ratios_borderline": False,
        "third_party_auditor": True,
        "audit_cadence": "quarterly",
        "protected_classes_count": 4,
        "remediation_documented": True,
        "audit_months_old": 2,
        "active_eeoc_or_complaint": False,
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "nyc_ll144_independent_auditor_required": False,
    },
    "data_governance": {
        "has_data_governance_policy": True,
        "policy_is_ai_specific": True,
        "training_data_provenance_documented": True,
        "consent_mechanism_documented": True,
        "retention_policy_exists": True,
        "retention_adequate_for_litigation": True,
        "cross_border_transfer_policy": True,
        "dpia_completed": True,
        "processes_sensitive_data": False,
        "candidate_right_to_explanation": True,
        "policy_months_old": 3,
    },
    "incident_response": {
        "has_ai_ir_plan": True,
        "incident_classification_defined": True,
        "regulator_notification_procedure": True,
        "post_incident_review_required": True,
        "rollback_procedures_documented": True,
        "ir_plan_months_old": 3,
        "active_incidents_or_complaints": False,
        "active_litigation": False,
    },
    "monitoring_drift": {
        "has_monitoring_documentation": True,
        "drift_detection_methodology": True,
        "retraining_triggers_defined": True,
        "alerting_mechanism_documented": False,
        "monitoring_months_old": 3,
        "vague_monitoring_reference_only": False,
    },
    "regulatory_compliance": {
        "framework_alignment": ["nist_rmf", "eu_ai_act"],
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "colorado_sb21_169_applies": False,
        "eu_ai_act_classification_documented": True,
        "active_regulatory_inquiry": False,
        "active_litigation": False,
        "general_legal_awareness": True,
        "compliance_months_old": 6,
    },
    "third_party_risk": {
        "has_vendor_ai_inventory": True,
        "vendor_risk_assessments_completed": False,
        "contractual_ai_protections_documented": False,
        "assessment_frequency_defined": False,
        "undocumented_third_party_ai": [],
        "candidate_or_customer_data_shared_with_vendor": False,
        "assessment_months_old": None,
    },
}

# AutoClaim (company_c) — critical risk Insurtech claims adjudication
# As an insurance company they have basic data governance and regulatory awareness,
# but no AI-specific governance whatsoever.
autoclaim_findings: dict[str, dict] = {
    "model_inventory": {"no_documentation_provided": True},
    "human_oversight": {
        "has_hitl_policy": False,
        "hitl_scope": "none",
        "escalation_path_documented": False,
        "override_authority_defined": False,
        "review_frequency": None,
        "misleading_hitl_claim": True,
        "hitl_policy_months_old": None,
    },
    "bias_fairness": {"no_documentation_provided": True},
    "data_governance": {
        # Insurance companies must maintain records — but policy is generic, not AI-specific
        "has_data_governance_policy": True,
        "policy_is_ai_specific": False,
        "training_data_provenance_documented": False,
        "consent_mechanism_documented": False,
        "retention_policy_exists": True,  # required by insurance law
        "retention_adequate_for_litigation": False,
        "cross_border_transfer_policy": False,
        "dpia_completed": False,
        "processes_sensitive_data": True,  # claims data is sensitive
        "candidate_right_to_explanation": False,
        "policy_months_old": None,
    },
    "incident_response": {
        "has_ai_ir_plan": False,
        "incident_classification_defined": False,
        "regulator_notification_procedure": False,
        "post_incident_review_required": False,
        "rollback_procedures_documented": False,
        "ir_plan_months_old": None,
        "active_incidents_or_complaints": True,
        "active_litigation": True,
    },
    "monitoring_drift": {
        # Claims processing performance IS monitored, but not AI-drift specifically
        "has_monitoring_documentation": False,
        "drift_detection_methodology": False,
        "retraining_triggers_defined": False,
        "alerting_mechanism_documented": False,
        "monitoring_months_old": None,
        "vague_monitoring_reference_only": True,  # some reference to monitoring exists
    },
    "regulatory_compliance": {
        "framework_alignment": [],
        "nyc_ll144_applies": False,
        "nyc_ll144_compliant": False,
        "colorado_sb21_169_applies": True,  # Insurance AI in Colorado -> CRITICAL
        "eu_ai_act_classification_documented": False,
        "active_regulatory_inquiry": True,  # CRITICAL
        "active_litigation": True,  # CRITICAL
        "general_legal_awareness": True,  # They know about regulations
        "compliance_months_old": None,
    },
    "third_party_risk": {
        "has_vendor_ai_inventory": True,  # They know they use AI vendors
        "vendor_risk_assessments_completed": False,
        "contractual_ai_protections_documented": False,
        "assessment_frequency_defined": False,
        "undocumented_third_party_ai": ["gpt4", "claude", "gemini"],  # not in inventory -> CRITICAL
        "candidate_or_customer_data_shared_with_vendor": True,  # CRITICAL
        "assessment_months_old": None,
    },
}


def test_quickhire_scores_medium_tier():
    result = score_assessment(quickhire_findings)
    assert 38 <= result.overall_score <= 62, f"QuickHire score {result.overall_score:.2f} not in [38, 62]"
    assert result.risk_tier == "medium"
    # Verify all required critical flags are present
    critical_texts = " ".join(f["text"] for f in result.all_flags if f["severity"] == "critical")
    assert "ChatGPT" in critical_texts or "Third-party AI" in critical_texts, "Missing ChatGPT flag"
    assert "EEOC" in critical_texts, "Missing EEOC complaint flag"
    assert "144" in critical_texts or "LL144" in critical_texts, "Missing LL144 flag"
    assert "incident response" in critical_texts.lower() or "IR plan" in critical_texts, "Missing IR plan flag"
    assert "senior" in critical_texts.lower() or "HITL" in critical_texts, "Missing HITL flag"


def test_greenscore_scores_low_tier():
    result = score_assessment(greenscore_findings)
    assert 78 <= result.overall_score <= 90, f"GreenScore score {result.overall_score:.2f} not in [78, 90]"
    assert result.risk_tier == "low"


def test_autoclaim_scores_critical_tier():
    result = score_assessment(autoclaim_findings)
    assert 8 <= result.overall_score <= 28, f"AutoClaim score {result.overall_score:.2f} not in [8, 28]"
    assert result.risk_tier == "critical"
