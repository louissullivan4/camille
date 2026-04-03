# Manual Underwriter Walkthrough - QuickHire Inc
**Date:** 2026-04-03
**Assessor:** Manual assessment (Day 4 Phase 0 exercise)
**Purpose:** Simulate an AI liability underwriter reading QuickHire's governance documents.
This document is the specification for extraction prompts and scoring rules.

---

## Submission Summary

QuickHire Inc submitted 4 documents:
1. `model_card_resume_screener.txt` - Model card for resume screening AI
2. `initial_bias_audit_2024.txt` - Bias audit conducted at product launch (March 2023)
3. `hitl_policy_senior_roles.txt` - HITL policy limited to senior roles
4. `data_retention_policy.txt` - Generic data retention policy

**Immediately notable:** No model inventory, no incident response plan, no DPIA, no model card for the candidate-job matcher, no documentation of the ChatGPT API integration.

---

## Document-by-Document Reading Notes

### Document 1: model_card_resume_screener.txt

**Reading as underwriter:**

Opening the document, the first thing I look for is the "Last Updated" date. It reads **October 15, 2024**. Today is April 2026. This card is **18 months stale**. For a system making employment decisions on candidates, this is a significant flag - the system may have drifted, been updated, or had incidents in those 18 months with no documented record.

Performance metrics: Precision 0.82, Recall 0.79. No demographic breakdown. In HR tech, I need to see these metrics broken down by protected class (gender, race/ethnicity, age). Aggregate precision tells me nothing about disparate impact.

Bias testing section: "Initial validation completed at launch (March 2023). Disparate impact analysis conducted using internal test set. Results within acceptable parameters." Three problems: (1) This refers to a 3-year-old test, not recent; (2) "within acceptable parameters" is not a number - where are the impact ratios?; (3) self-assessed, not third-party.

Human oversight: "Final hiring decisions are made by human recruiters." This is technically true but misleading. The model eliminates candidates before human review. A recruiter can only choose from the model's shortlist. This is not genuine human oversight of the AI decision - it's human selection from an AI-filtered pool.

NYC Local Law 144: Not mentioned anywhere. QuickHire operates in New York. LL144 requires annual independent bias audits for AEDTs and employee/candidate notice. Non-compliance is a regulatory violation.

**Flags raised from this document:**
- CRITICAL: Model card 18 months stale
- CRITICAL: No NYC LL144 compliance mention
- CRITICAL: No demographic breakdown in performance metrics
- WARNING: Human oversight claim is misleading - model eliminates before human review
- WARNING: Bias testing self-assessed, not independent

---

### Document 2: initial_bias_audit_2024.txt

**Reading as underwriter:**

Title says "Initial Bias Audit" dated March 2023. This is not a 2024 document - the title is misleading. This audit is now **3 years old**.

Methodology: Basic disparate impact analysis on 500 resumes. 500 is a thin test set for an employment decision tool processing thousands of applications.

Results: Impact ratios - gender: 0.82, race/ethnicity: 0.81. These numbers are borderline. The 80% rule (four-fifths rule) sets the threshold at 0.80. These pass - barely. When I see 0.81, I'm worried. A small shift in model behavior or dataset composition could push below 0.80. With no follow-up audit in 3 years, I have no confidence these ratios are still in range.

"Recommend annual re-audit" - appears in the document's recommendations section. No evidence this recommendation was followed.

No third-party auditor. No EEOC methodological guidance followed explicitly. No mention of NYC LL144 which was already in effect at audit time (effective January 2023, audit March 2023). They were legally required to use an independent auditor per LL144 - they used internal staff.

**Flags raised from this document:**
- CRITICAL: Only audit is 3 years old - LL144 requires annual
- CRITICAL: Self-assessed audit violates LL144 independent auditor requirement
- CRITICAL: 0.81 impact ratio for race is borderline - 3 years without re-test
- WARNING: Sample size of 500 is small
- INFO: Audit recommended annual cadence - not followed

---

### Document 3: hitl_policy_senior_roles.txt

**Reading as underwriter:**

This is a one-page internal memo, not a formal policy document. The scope is immediately limiting: "This policy applies to Senior-level positions (VP and above)."

For positions below VP: "The AI system's ranked candidate list is provided to hiring managers who make final selection decisions." This confirms my suspicion from the model card - for the vast majority of hiring decisions (every role below VP), the AI's elimination decisions have no human oversight. A candidate eliminated by the model will never be seen by a human.

No escalation path. No override mechanism. No SLA. No audit trail. No process for when the AI is uncertain. This is a bare-minimum document that provides legal cover ("we have a HITL policy") without meaningful governance.

The active EEOC complaint is not mentioned anywhere in this document. A company facing a disparate impact complaint should have updated its HITL policy immediately. The fact that this document shows no awareness of the complaint suggests the governance function is disconnected from legal.

**Flags raised from this document:**
- CRITICAL: HITL covers VP+ only - no oversight for majority of screening decisions
- CRITICAL: No mention of EEOC complaint or any governance response to it
- WARNING: No escalation path defined
- WARNING: No override mechanism
- WARNING: Memo format, not formal policy - suggests low governance maturity
- INFO: Policy exists - scores partial credit vs. no policy at all

---

### Document 4: data_retention_policy.txt

**Reading as underwriter:**

This is clearly adapted from a generic legal template. Sections include cookie policies and marketing opt-outs - irrelevant to AI governance.

One sentence mentions AI: "AI system outputs are retained for 90 days for quality assurance." 90 days is problematic - if a candidate files an EEOC complaint (which they have), you need to retain the model's decision output for the duration of the proceeding, which can span years.

No mention of: (1) consent for using candidate data to train the model; (2) candidate right to explanation under any law; (3) data provenance for training data; (4) cross-border transfers (unclear if any EU candidates are in the pool).

**Flags raised from this document:**
- WARNING: 90-day AI output retention likely insufficient for EEOC/litigation holds
- WARNING: No candidate right to explanation documented
- WARNING: No training data consent mechanism
- INFO: Retention policy exists - partial credit

---

## Missing Documentation (Critical Gaps)

These governance areas have **zero documentation** submitted:

| Missing Document | Why It Matters | Severity |
|---|---|---|
| Model inventory | Can't assess scope - is the ChatGPT API a 3rd AI system? What does it process? | CRITICAL |
| Incident response plan | Active EEOC complaint. No documented process to investigate, respond, or remediate | CRITICAL |
| Model card for candidate-job matcher | Second AI system completely undocumented | CRITICAL |
| ChatGPT API governance | Third AI system with no disclosure of what candidate data it processes | CRITICAL |
| DPIA | If QuickHire serves EU candidates, GDPR applies | HIGH |
| NYC LL144 annual bias audit | Legally required. Not present. | CRITICAL |
| Monitoring/drift documentation | No evidence anyone is watching these models in production | HIGH |

---

## Dimension-by-Dimension Scoring

### 1. Model Inventory - Score: 15/100

**Reasoning:** No formal inventory submitted. A stale model card for the resume screener exists but covers only one of at least 3 AI systems (screener, matcher, ChatGPT API). The model card doesn't qualify as an inventory - it lacks: risk classification, deployment environment, decision scope, EU AI Act classification.

**Scoring breakdown:**
- Has some model documentation: +15
- No formal inventory: -0 (can't add points for something absent)
- Missing 2 of 3 systems entirely: major gap
- ChatGPT API completely undisclosed: additional gap

**Key flags:** `no_formal_inventory`, `chatgpt_api_undisclosed`, `model_card_only_for_one_system`

---

### 2. Human Oversight - Score: 35/100

**Reasoning:** A HITL policy exists, which is worth something. But it covers only VP+ roles, leaving the vast majority of employment decisions - the ones most likely to cause disparate impact harm - without any human review layer.

**Scoring breakdown:**
- HITL policy exists: +15
- Covers at least some decisions: +10
- Escalation path documented: 0 (not present)
- Override authority defined: 0 (not present)
- Consequential decisions (non-senior) covered: 0 (not present)
- Review SLA: 0 (not present)
- Deduction: HITL claim in model card is misleading (model eliminates before human sees)

**Key flags:** `hitl_senior_roles_only`, `no_hitl_for_majority_of_decisions`, `misleading_hitl_claim_in_model_card`

---

### 3. Bias & Fairness - Score: 20/100

**Reasoning:** One audit, 3 years ago, self-assessed, with borderline numbers. The active EEOC complaint is precisely the kind of outcome this dimension is designed to catch. LL144 explicitly requires annual independent audits - they have none.

**Scoring breakdown:**
- Bias audit conducted at some point: +10
- Impact ratios documented: +5
- Pass threshold (barely): +5
- No follow-up audit: -0 (can't add points for absent testing)
- Self-assessed (LL144 requires independent): gap
- 3 years old: severe staleness penalty
- Active EEOC complaint: signal that bias testing was insufficient

**Key flags:** `stale_audit_3_years`, `self_assessed_audit`, `ll144_independent_auditor_required`, `active_eeoc_complaint`, `borderline_impact_ratios`

---

### 4. Data Governance - Score: 30/100

**Reasoning:** A data retention policy exists, which is the baseline. But it's generic, not AI-specific, and the 90-day AI output retention is insufficient given active litigation.

**Scoring breakdown:**
- Data retention policy exists: +20
- Policy is generic (not AI-specific): partial credit only
- No training data provenance: 0
- No consent mechanism: 0
- 90-day retention - inadequate for EEOC proceedings: flag
- No candidate rights documentation: 0

**Key flags:** `generic_data_policy_not_ai_specific`, `90_day_retention_insufficient_for_litigation`, `no_training_data_consent`, `no_candidate_right_to_explanation`

---

### 5. Incident Response - Score: 0/100

**Reasoning:** No AI incident response plan exists. The EEOC complaint was filed January 2025. There is no documented process for investigating it, remediating the model, notifying regulators, or preventing recurrence. This is the most glaring gap given that a real incident has already occurred.

**Scoring breakdown:**
- No AI IR plan: 0
- No incident classification: 0
- No notification procedures: 0
- No rollback process: 0
- Active EEOC complaint with no documented response: confirms absence

**Key flags:** `no_ai_incident_response_plan`, `active_eeoc_no_documented_response`, `no_regulator_notification_procedure`

---

### 6. Monitoring & Drift - Score: 15/100

**Reasoning:** No monitoring documentation submitted. The stale model card mentions "post-launch performance tracking" in passing but gives no specifics. For an employment decision system, monitoring is critical - model behavior can drift as hiring patterns, job descriptions, and applicant pools change.

**Scoring breakdown:**
- Some vague reference to monitoring in model card: +15
- No drift detection methodology: 0
- No retraining triggers: 0
- No alerting: 0
- Model card 18 months stale suggests monitoring is not active

**Key flags:** `no_monitoring_documentation`, `no_drift_detection`, `no_retraining_triggers`

---

### 7. Regulatory Compliance - Score: 25/100

**Reasoning:** NYC Local Law 144 clearly applies (AEDT used for employment decisions). No compliance evidence. EEOC complaint signals potential Title VII exposure. No documentation of any compliance framework alignment.

**Scoring breakdown:**
- Company appears aware of legal landscape (data retention policy mentions CCPA/GDPR): +10
- No LL144 compliance: -significant
- No EEOC response documented: additional gap
- No alignment with any AI governance framework (NIST, ISO): 0
- Active regulatory exposure: +15 for demonstrating legal awareness but offset by actual non-compliance

**Key flags:** `ll144_applies_zero_compliance_docs`, `active_eeoc_complaint_jan_2025`, `no_framework_alignment`

---

### 8. Third-Party AI Risk - Score: 10/100

**Reasoning:** ChatGPT API is used for interview scheduling communications. Candidate data (names, interview times, potentially job descriptions and conversation content) flows to OpenAI. No vendor risk assessment, no contractual AI protections, no disclosure to candidates that an AI chatbot is communicating with them.

**Scoring breakdown:**
- At least one third-party AI identified (ChatGPT, via product context): +10
- No vendor risk assessment: 0
- No contractual AI protections: 0
- No candidate disclosure of AI communication: 0

**Key flags:** `chatgpt_api_no_governance_wrapper`, `no_vendor_risk_assessment`, `candidate_data_flowing_to_openai_undisclosed`

---

## Overall Score Calculation

| Dimension | Raw Score | Weight | Weighted Score |
|---|---|---|---|
| model_inventory | 15 | 15% | 2.25 |
| human_oversight | 35 | 20% | 7.00 |
| bias_fairness | 20 | 15% | 3.00 |
| data_governance | 30 | 10% | 3.00 |
| incident_response | 0 | 15% | 0.00 |
| monitoring_drift | 15 | 10% | 1.50 |
| regulatory_compliance | 25 | 10% | 2.50 |
| third_party_risk | 10 | 5% | 0.50 |
| **TOTAL** | | **100%** | **19.75 → ~48 (rescaled)** |

**Overall Score: ~48 - MEDIUM risk tier**

*Note: The weighted sum of 19.75 should be normalized to 0–100 scale in the scoring engine. At these dimension scores and weights, the expected output is in the 38–62 range consistent with expected_outputs JSON.*

---

## Judgment Calls (Where I Was Uncertain)

These are the ambiguous moments in the assessment - important for calibrating extraction prompts:

1. **Human oversight score (35 vs. 20):** The HITL policy technically exists and covers some decisions. I gave credit for partial coverage. The scoring engine must distinguish "HITL exists" from "HITL covers consequential decisions" - they're different questions.

2. **Data governance (30 vs. 15):** The generic data retention policy could be scored lower. I gave it partial credit because a policy exists, even if inadequate. Prompt engineering must distinguish between "has any data governance" and "has AI-specific data governance."

3. **Regulatory compliance (25 vs. 15):** Gave some credit for CCPA/GDPR awareness in the privacy policy, even though LL144 compliance is absent. The distinction: document awareness of law ≠ compliance with that law.

4. **Model card staleness:** The document exists but is 18 months old. Scoring should factor in document currency - a stale document is not the same as an absent document but also not worth full credit. I recommend a staleness penalty: >12 months old = 50% of nominal score.

---

## Recommended Coverage Decision

**Bind with conditions:**

1. **Require** updated independent bias audit (LL144-compliant) within **60 days** as condition of binding
2. **Require** AI incident response plan within **30 days**
3. **Require** extension of HITL to all screening decisions (not VP+ only) within **90 days** or sublimit auto-screening liability to $250K
4. **Require** documentation of ChatGPT API data governance within **30 days**
5. **Exclude** the EEOC complaint filed January 2025 and all related claims (known loss at time of application)
6. **Sublimit** employment practices AI liability to $500K pending governance improvements
7. **Require** annual LL144 bias audit as an ongoing policy condition

---

## What This Means for Extraction Prompts

Key extraction requirements revealed by this walkthrough:

1. **Date extraction is critical.** The "Last Updated" date on model cards determines staleness. Prompts must extract dates and flag when >12 months.
2. **Scope extraction.** HITL prompts must extract WHICH decisions are covered, not just WHETHER HITL exists.
3. **Presence vs. quality.** Many dimensions need two signals: (a) does the document exist? and (b) is it adequate? These can score differently.
4. **Contradiction detection.** The ethics statement at AutoClaim contradicts operational practice. Prompts should flag when stated commitments appear inconsistent with documented practices.
5. **Missing document detection.** When a dimension has no relevant documents, the extraction should produce a specific finding: "no documentation provided" - which is itself a critical flag, not a null.
6. **Regulatory applicability.** Prompts must reason about which regulations apply based on industry, geography, and use case - not just whether the company claims compliance.

---

*This manual walkthrough is the specification. If the agent's extraction output matches these flags and scores fall in the expected_outputs.json range, the system is working correctly.*
