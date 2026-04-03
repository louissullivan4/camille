from app.services.scoring_engine import DimensionScore, get_staleness_multiplier


def score_human_oversight(findings: dict) -> DimensionScore:
    """Score the human_oversight governance dimension."""
    flags: list[dict] = []

    if findings.get("no_documentation_provided"):
        flags.append({
            "severity": "critical",
            "text": "No documentation provided for this dimension",
            "field": "no_documentation_provided",
        })
        return DimensionScore(dimension="human_oversight", score=0, max_score=100, flags=flags)

    base_score = 0.0
    scope_points = 0.0

    if findings.get("has_hitl_policy"):
        base_score += 20

    hitl_scope = findings.get("hitl_scope", "none")
    if hitl_scope == "all_consequential":
        scope_points += 30
    elif hitl_scope == "partial":
        scope_points += 15
        flags.append({
            "severity": "warning",
            "text": "HITL covers partial decisions only",
            "field": "hitl_scope",
        })
    elif hitl_scope == "senior_only":
        scope_points += 10
        flags.append({
            "severity": "critical",
            "text": "HITL covers senior roles only — majority of decisions unreviewed",
            "field": "hitl_scope",
        })
    else:
        # "none"
        flags.append({
            "severity": "critical",
            "text": "No HITL coverage",
            "field": "hitl_scope",
        })

    if findings.get("escalation_path_documented"):
        base_score += 20
    if findings.get("override_authority_defined"):
        base_score += 15

    review_frequency = findings.get("review_frequency")
    if review_frequency in ("monthly", "quarterly"):
        base_score += 15

    if findings.get("misleading_hitl_claim"):
        flags.append({
            "severity": "warning",
            "text": "HITL claim may be misleading — model filters before human review",
            "field": "misleading_hitl_claim",
        })

    # Apply staleness multiplier to base_score only (not scope points)
    months_old = findings.get("hitl_policy_months_old")
    multiplier = get_staleness_multiplier(months_old)
    if multiplier < 1.0:
        flags.append({
            "severity": "warning",
            "text": f"HITL policy is {months_old} months old — staleness penalty applied",
            "field": "hitl_policy_months_old",
        })
    base_score *= multiplier

    score = base_score + scope_points

    return DimensionScore(dimension="human_oversight", score=score, max_score=100, flags=flags)
