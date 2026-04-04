from app.services.scoring_engine import DimensionScore, get_staleness_multiplier


def score_third_party_risk(findings: dict) -> DimensionScore:
    """Score the third_party_risk governance dimension."""
    flags: list[dict] = []

    if findings.get("no_documentation_provided"):
        flags.append(
            {
                "severity": "critical",
                "text": "No documentation provided for this dimension",
                "field": "no_documentation_provided",
            }
        )
        return DimensionScore(dimension="third_party_risk", score=0, max_score=100, flags=flags)

    score = 0.0

    if findings.get("has_vendor_ai_inventory"):
        score += 20
    if findings.get("vendor_risk_assessments_completed"):
        score += 25

    contractual_protections = findings.get("contractual_ai_protections_documented", False)
    if contractual_protections:
        score += 30

    if findings.get("assessment_frequency_defined"):
        score += 25

    for system in findings.get("undocumented_third_party_ai", []):
        flags.append(
            {
                "severity": "critical",
                "text": f"Third-party AI system used without governance documentation: {system}",
                "field": "undocumented_third_party_ai",
            }
        )

    if findings.get("candidate_or_customer_data_shared_with_vendor") and not contractual_protections:
        flags.append(
            {
                "severity": "critical",
                "text": "Customer/candidate data shared with third-party AI — no contractual protections documented",
                "field": "contractual_ai_protections_documented",
            }
        )

    # Apply staleness multiplier
    months_old = findings.get("assessment_months_old")
    multiplier = get_staleness_multiplier(months_old)
    if multiplier < 1.0:
        flags.append(
            {
                "severity": "warning",
                "text": f"Third-party risk assessment is {months_old} months old — staleness penalty applied",
                "field": "assessment_months_old",
            }
        )
    score *= multiplier

    return DimensionScore(dimension="third_party_risk", score=score, max_score=100, flags=flags)
