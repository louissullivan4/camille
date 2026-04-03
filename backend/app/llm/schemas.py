"""
tool_use JSON schemas for document classification and all 8 governance dimensions.

CRITICAL: output field names in each schema MUST exactly match the findings dict
keys consumed by the corresponding scoring rule in app/services/scoring_rules/.
"""

CLASSIFY_DOCUMENT_TOOL: dict = {
    "name": "classify_document",
    "description": (
        "Classify an AI governance document by type and identify which "
        "scoring dimensions it contains evidence for."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "doc_type": {
                "type": "string",
                "enum": [
                    "model_card",
                    "bias_audit",
                    "hitl_policy",
                    "data_governance",
                    "ir_plan",
                    "monitoring",
                    "compliance",
                    "vendor_risk",
                    "unknown",
                ],
                "description": "The primary document type.",
            },
            "confidence": {
                "type": "number",
                "description": "Classification confidence between 0.0 and 1.0.",
            },
            "relevant_dimensions": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "model_inventory",
                        "human_oversight",
                        "bias_fairness",
                        "data_governance",
                        "incident_response",
                        "monitoring_drift",
                        "regulatory_compliance",
                        "third_party_risk",
                    ],
                },
                "description": "Which governance dimensions this document contains evidence for.",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the classification decision.",
            },
        },
        "required": ["doc_type", "confidence", "relevant_dimensions", "reasoning"],
    },
}

# ---------------------------------------------------------------------------
# Dimension extraction schemas
# Field names MUST match scoring_rules/*.py exactly.
# ---------------------------------------------------------------------------

MODEL_INVENTORY_TOOL: dict = {
    "name": "extract_model_inventory",
    "description": "Extract model inventory governance signals from AI governance documents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "no_documentation_provided": {
                "type": "boolean",
                "description": "True if no relevant documentation was found for this dimension.",
            },
            "has_formal_inventory": {
                "type": "boolean",
                "description": "A formal, written inventory of all AI/ML systems exists.",
            },
            "models_fully_documented": {
                "type": "boolean",
                "description": "All models in the inventory have complete documentation (purpose, inputs, outputs, version).",
            },
            "risk_classification_present": {
                "type": "boolean",
                "description": "Models are classified by risk tier (e.g. high/medium/low risk).",
            },
            "deployment_env_documented": {
                "type": "boolean",
                "description": "Deployment environments are documented for all AI systems.",
            },
            "decision_types_documented": {
                "type": "boolean",
                "description": "The types of decisions each model makes (consequential vs. non-consequential) are documented.",
            },
            "inventory_months_old": {
                "type": ["number", "null"],
                "description": "Age of the model inventory in months based on 'Last Updated' date. Null if not determinable.",
            },
            "undocumented_systems": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names/descriptions of AI systems mentioned but lacking formal documentation.",
            },
            "chatgpt_or_third_party_undisclosed": {
                "type": "boolean",
                "description": "Evidence of ChatGPT or other third-party AI used without disclosure or governance wrapper.",
            },
        },
        "required": [
            "no_documentation_provided",
            "has_formal_inventory",
            "models_fully_documented",
            "risk_classification_present",
            "deployment_env_documented",
            "decision_types_documented",
            "inventory_months_old",
            "undocumented_systems",
            "chatgpt_or_third_party_undisclosed",
        ],
    },
}

HUMAN_OVERSIGHT_TOOL: dict = {
    "name": "extract_human_oversight",
    "description": "Extract human-in-the-loop oversight governance signals from AI governance documents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "no_documentation_provided": {
                "type": "boolean",
                "description": "True if no relevant documentation was found for this dimension.",
            },
            "has_hitl_policy": {
                "type": "boolean",
                "description": "A formal human-in-the-loop (HITL) policy exists.",
            },
            "hitl_scope": {
                "type": "string",
                "enum": ["all_consequential", "partial", "senior_only", "none"],
                "description": (
                    "Scope of HITL coverage: 'all_consequential' = all consequential decisions reviewed, "
                    "'partial' = some but not all decision types, "
                    "'senior_only' = only senior/VP+ roles reviewed (majority unreviewed), "
                    "'none' = no human review of AI decisions."
                ),
            },
            "escalation_path_documented": {
                "type": "boolean",
                "description": "A documented escalation path exists for AI decisions.",
            },
            "override_authority_defined": {
                "type": "boolean",
                "description": "Authority to override AI decisions is explicitly defined.",
            },
            "review_frequency": {
                "type": ["string", "null"],
                "description": "How often AI decisions are reviewed: 'monthly', 'quarterly', 'annual', 'ad_hoc', or null.",
            },
            "misleading_hitl_claim": {
                "type": "boolean",
                "description": "HITL is claimed but the model pre-filters candidates before humans ever see them — human 'review' is effectively nominal.",
            },
            "hitl_policy_months_old": {
                "type": ["number", "null"],
                "description": "Age of the HITL policy in months. Null if not determinable.",
            },
        },
        "required": [
            "no_documentation_provided",
            "has_hitl_policy",
            "hitl_scope",
            "escalation_path_documented",
            "override_authority_defined",
            "review_frequency",
            "misleading_hitl_claim",
            "hitl_policy_months_old",
        ],
    },
}

BIAS_FAIRNESS_TOOL: dict = {
    "name": "extract_bias_fairness",
    "description": "Extract bias and fairness governance signals from AI governance documents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "no_documentation_provided": {
                "type": "boolean",
                "description": "True if no relevant documentation was found for this dimension.",
            },
            "has_bias_audit": {
                "type": "boolean",
                "description": "A bias audit or fairness evaluation has been conducted.",
            },
            "impact_ratios_documented": {
                "type": "boolean",
                "description": "Adverse impact ratios (e.g., selection rates by protected class) are documented.",
            },
            "impact_ratios_above_threshold": {
                "type": "boolean",
                "description": "All documented impact ratios meet the 80% rule threshold (≥0.80).",
            },
            "protected_classes_count": {
                "type": "integer",
                "description": "Number of protected classes tested (race, gender, age, etc.).",
            },
            "third_party_auditor": {
                "type": "boolean",
                "description": "Bias audit conducted by an independent third-party auditor.",
            },
            "audit_cadence": {
                "type": ["string", "null"],
                "description": "Frequency of bias audits: 'quarterly', 'annual', 'at_launch_only', or null.",
            },
            "remediation_documented": {
                "type": "boolean",
                "description": "Remediation steps taken in response to bias findings are documented.",
            },
            "audit_months_old": {
                "type": ["number", "null"],
                "description": "Age of the most recent bias audit in months. Null if not determinable.",
            },
            "impact_ratios_borderline": {
                "type": "boolean",
                "description": "Any impact ratio is borderline (0.75–0.85 range, near 80% rule threshold).",
            },
            "active_eeoc_or_complaint": {
                "type": "boolean",
                "description": "Active EEOC complaint or discrimination complaint related to AI decision-making.",
            },
            "nyc_ll144_applies": {
                "type": "boolean",
                "description": "NYC Local Law 144 applies — company uses AEDTs for employment decisions in NYC.",
            },
            "nyc_ll144_compliant": {
                "type": "boolean",
                "description": "Company has documented NYC LL144 compliance (independent audit, bias notice, etc.).",
            },
            "nyc_ll144_independent_auditor_required": {
                "type": "boolean",
                "description": "LL144 requires an independent auditor but the audit is self-assessed.",
            },
        },
        "required": [
            "no_documentation_provided",
            "has_bias_audit",
            "impact_ratios_documented",
            "impact_ratios_above_threshold",
            "protected_classes_count",
            "third_party_auditor",
            "audit_cadence",
            "remediation_documented",
            "audit_months_old",
            "impact_ratios_borderline",
            "active_eeoc_or_complaint",
            "nyc_ll144_applies",
            "nyc_ll144_compliant",
            "nyc_ll144_independent_auditor_required",
        ],
    },
}

DATA_GOVERNANCE_TOOL: dict = {
    "name": "extract_data_governance",
    "description": "Extract data governance signals from AI governance documents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "no_documentation_provided": {
                "type": "boolean",
                "description": "True if no relevant documentation was found for this dimension.",
            },
            "has_data_governance_policy": {
                "type": "boolean",
                "description": "A data governance policy exists.",
            },
            "policy_is_ai_specific": {
                "type": "boolean",
                "description": "The data governance policy specifically addresses AI/ML data requirements (not just generic IT policy).",
            },
            "training_data_provenance_documented": {
                "type": "boolean",
                "description": "Origin and lineage of training data is documented.",
            },
            "consent_mechanism_documented": {
                "type": "boolean",
                "description": "Consent mechanism for data use in AI training/inference is documented.",
            },
            "retention_policy_exists": {
                "type": "boolean",
                "description": "A data retention policy exists covering AI inputs/outputs.",
            },
            "retention_adequate_for_litigation": {
                "type": "boolean",
                "description": "Retention period is adequate for litigation and complaint holds (typically ≥3 years for employment decisions).",
            },
            "cross_border_transfer_policy": {
                "type": "boolean",
                "description": "Cross-border data transfer policy exists (relevant for GDPR, SCCs, etc.).",
            },
            "dpia_completed": {
                "type": "boolean",
                "description": "A Data Protection Impact Assessment (DPIA) has been completed.",
            },
            "processes_sensitive_data": {
                "type": "boolean",
                "description": "The AI system processes sensitive personal data (biometrics, health, financial, etc.).",
            },
            "policy_months_old": {
                "type": ["number", "null"],
                "description": "Age of the data governance policy in months. Null if not determinable.",
            },
        },
        "required": [
            "no_documentation_provided",
            "has_data_governance_policy",
            "policy_is_ai_specific",
            "training_data_provenance_documented",
            "consent_mechanism_documented",
            "retention_policy_exists",
            "retention_adequate_for_litigation",
            "cross_border_transfer_policy",
            "dpia_completed",
            "processes_sensitive_data",
            "policy_months_old",
        ],
    },
}

INCIDENT_RESPONSE_TOOL: dict = {
    "name": "extract_incident_response",
    "description": "Extract AI incident response governance signals from AI governance documents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "no_documentation_provided": {
                "type": "boolean",
                "description": "True if no relevant documentation was found for this dimension.",
            },
            "has_ai_ir_plan": {
                "type": "boolean",
                "description": "An AI-specific incident response plan exists (not just a generic IT IR plan).",
            },
            "incident_classification_defined": {
                "type": "boolean",
                "description": "AI incident severity levels / classification criteria are defined.",
            },
            "regulator_notification_procedure": {
                "type": "boolean",
                "description": "Procedure for notifying regulators of AI incidents is documented.",
            },
            "post_incident_review_required": {
                "type": "boolean",
                "description": "Post-incident review / root cause analysis is required by policy.",
            },
            "rollback_procedures_documented": {
                "type": "boolean",
                "description": "Model rollback or suspension procedures are documented.",
            },
            "ir_plan_months_old": {
                "type": ["number", "null"],
                "description": "Age of the IR plan in months. Null if not determinable.",
            },
            "active_incidents_or_complaints": {
                "type": "boolean",
                "description": "Active AI-related incidents or complaints are documented.",
            },
            "active_litigation": {
                "type": "boolean",
                "description": "Active litigation related to AI decisions.",
            },
        },
        "required": [
            "no_documentation_provided",
            "has_ai_ir_plan",
            "incident_classification_defined",
            "regulator_notification_procedure",
            "post_incident_review_required",
            "rollback_procedures_documented",
            "ir_plan_months_old",
            "active_incidents_or_complaints",
            "active_litigation",
        ],
    },
}

MONITORING_DRIFT_TOOL: dict = {
    "name": "extract_monitoring_drift",
    "description": "Extract model monitoring and drift detection governance signals.",
    "input_schema": {
        "type": "object",
        "properties": {
            "no_documentation_provided": {
                "type": "boolean",
                "description": "True if no relevant documentation was found for this dimension.",
            },
            "has_monitoring_documentation": {
                "type": "boolean",
                "description": "Operational model monitoring documentation exists (specific metrics, thresholds, tooling).",
            },
            "vague_monitoring_reference_only": {
                "type": "boolean",
                "description": "Monitoring is mentioned but not operationally documented (e.g. 'we monitor our models' with no specifics).",
            },
            "drift_detection_methodology": {
                "type": "boolean",
                "description": "A specific drift detection methodology or tooling is documented.",
            },
            "retraining_triggers_defined": {
                "type": "boolean",
                "description": "Specific conditions that trigger model retraining are defined.",
            },
            "alerting_mechanism_documented": {
                "type": "boolean",
                "description": "An alerting mechanism for performance degradation is documented.",
            },
            "monitoring_months_old": {
                "type": ["number", "null"],
                "description": "Age of monitoring documentation in months. Null if not determinable.",
            },
        },
        "required": [
            "no_documentation_provided",
            "has_monitoring_documentation",
            "vague_monitoring_reference_only",
            "drift_detection_methodology",
            "retraining_triggers_defined",
            "alerting_mechanism_documented",
            "monitoring_months_old",
        ],
    },
}

REGULATORY_COMPLIANCE_TOOL: dict = {
    "name": "extract_regulatory_compliance",
    "description": "Extract regulatory compliance signals from AI governance documents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "no_documentation_provided": {
                "type": "boolean",
                "description": "True if no relevant documentation was found for this dimension.",
            },
            "framework_alignment": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["nist_rmf", "iso_42001", "eu_ai_act", "nist_ai_100_1"],
                },
                "description": "Regulatory frameworks the company is aligned with or claims compliance to.",
            },
            "nyc_ll144_applies": {
                "type": "boolean",
                "description": "NYC Local Law 144 applies — company uses AEDTs for employment decisions in NYC.",
            },
            "nyc_ll144_compliant": {
                "type": "boolean",
                "description": "Company has documented NYC LL144 compliance.",
            },
            "colorado_sb21_169_applies": {
                "type": "boolean",
                "description": "Colorado SB21-169 applies — company uses AI in insurance decisions in Colorado.",
            },
            "colorado_sb21_169_compliant": {
                "type": "boolean",
                "description": "Company has documented Colorado SB21-169 compliance.",
            },
            "eu_ai_act_classification_documented": {
                "type": "boolean",
                "description": "EU AI Act risk classification for the AI system is documented.",
            },
            "active_regulatory_inquiry": {
                "type": "boolean",
                "description": "Active regulatory inquiry or investigation.",
            },
            "active_litigation": {
                "type": "boolean",
                "description": "Active litigation with regulatory exposure.",
            },
            "general_legal_awareness": {
                "type": "boolean",
                "description": "Company demonstrates general awareness of applicable AI laws and regulations even without full compliance documentation.",
            },
            "compliance_months_old": {
                "type": ["number", "null"],
                "description": "Age of compliance documentation in months. Null if not determinable.",
            },
        },
        "required": [
            "no_documentation_provided",
            "framework_alignment",
            "nyc_ll144_applies",
            "nyc_ll144_compliant",
            "colorado_sb21_169_applies",
            "colorado_sb21_169_compliant",
            "eu_ai_act_classification_documented",
            "active_regulatory_inquiry",
            "active_litigation",
            "general_legal_awareness",
            "compliance_months_old",
        ],
    },
}

THIRD_PARTY_RISK_TOOL: dict = {
    "name": "extract_third_party_risk",
    "description": "Extract third-party AI vendor risk governance signals.",
    "input_schema": {
        "type": "object",
        "properties": {
            "no_documentation_provided": {
                "type": "boolean",
                "description": "True if no relevant documentation was found for this dimension.",
            },
            "has_vendor_ai_inventory": {
                "type": "boolean",
                "description": "A formal inventory of third-party AI vendors/services exists.",
            },
            "vendor_risk_assessments_completed": {
                "type": "boolean",
                "description": "Risk assessments have been completed for third-party AI vendors.",
            },
            "contractual_ai_protections_documented": {
                "type": "boolean",
                "description": "Contractual protections specific to AI use (liability, data handling, audit rights) are documented.",
            },
            "assessment_frequency_defined": {
                "type": "boolean",
                "description": "The frequency of vendor AI risk assessments is defined.",
            },
            "undocumented_third_party_ai": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Third-party AI systems used without governance documentation.",
            },
            "candidate_or_customer_data_shared_with_vendor": {
                "type": "boolean",
                "description": "Candidate or customer personal data is shared with third-party AI vendors.",
            },
            "assessment_months_old": {
                "type": ["number", "null"],
                "description": "Age of the most recent vendor risk assessment in months. Null if not determinable.",
            },
        },
        "required": [
            "no_documentation_provided",
            "has_vendor_ai_inventory",
            "vendor_risk_assessments_completed",
            "contractual_ai_protections_documented",
            "assessment_frequency_defined",
            "undocumented_third_party_ai",
            "candidate_or_customer_data_shared_with_vendor",
            "assessment_months_old",
        ],
    },
}

# Lookup map for orchestrator use
DIMENSION_TOOLS: dict[str, dict] = {
    "model_inventory": MODEL_INVENTORY_TOOL,
    "human_oversight": HUMAN_OVERSIGHT_TOOL,
    "bias_fairness": BIAS_FAIRNESS_TOOL,
    "data_governance": DATA_GOVERNANCE_TOOL,
    "incident_response": INCIDENT_RESPONSE_TOOL,
    "monitoring_drift": MONITORING_DRIFT_TOOL,
    "regulatory_compliance": REGULATORY_COMPLIANCE_TOOL,
    "third_party_risk": THIRD_PARTY_RISK_TOOL,
}
