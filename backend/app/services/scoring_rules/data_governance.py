from app.services.scoring_engine import DimensionScore, get_staleness_multiplier


def score_data_governance(findings: dict) -> DimensionScore:
    """Score the data_governance governance dimension."""
    flags: list[dict] = []

    if findings.get("no_documentation_provided"):
        flags.append(
            {
                "severity": "critical",
                "text": "No documentation provided for this dimension",
                "field": "no_documentation_provided",
            }
        )
        return DimensionScore(dimension="data_governance", score=0, max_score=100, flags=flags)

    score = 0.0

    has_policy = findings.get("has_data_governance_policy", False)
    if has_policy:
        score += 30  # 30 for having any data governance policy

    if findings.get("policy_is_ai_specific"):
        score += 10  # additional 10 for AI-specific policy
    elif has_policy:
        flags.append(
            {
                "severity": "warning",
                "text": "Data governance policy is generic, not AI-specific",
                "field": "policy_is_ai_specific",
            }
        )

    if findings.get("training_data_provenance_documented"):
        score += 15
    if findings.get("consent_mechanism_documented"):
        score += 15

    retention_exists = findings.get("retention_policy_exists", False)
    if retention_exists:
        score += 10

    if retention_exists and not findings.get("retention_adequate_for_litigation"):
        flags.append(
            {
                "severity": "warning",
                "text": "AI output retention may be insufficient for litigation/complaint holds",
                "field": "retention_adequate_for_litigation",
            }
        )

    if findings.get("cross_border_transfer_policy"):
        score += 10

    dpia_completed = findings.get("dpia_completed", False)
    if dpia_completed:
        score += 10

    if findings.get("processes_sensitive_data") and not dpia_completed:
        flags.append(
            {
                "severity": "critical",
                "text": "Processes sensitive data but no DPIA completed",
                "field": "dpia_completed",
            }
        )

    # candidate_right_to_explanation: no points, no deduction — absence noted per spec

    # Apply staleness multiplier
    months_old = findings.get("policy_months_old")
    multiplier = get_staleness_multiplier(months_old)
    if multiplier < 1.0:
        flags.append(
            {
                "severity": "warning",
                "text": f"Data governance policy is {months_old} months old — staleness penalty applied",
                "field": "policy_months_old",
            }
        )
    score *= multiplier

    return DimensionScore(dimension="data_governance", score=score, max_score=100, flags=flags)
