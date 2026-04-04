from app.services.scoring_engine import DimensionScore, get_staleness_multiplier


def score_incident_response(findings: dict) -> DimensionScore:
    """Score the incident_response governance dimension."""
    flags: list[dict] = []

    if findings.get("no_documentation_provided"):
        flags.append(
            {
                "severity": "critical",
                "text": "No AI incident response plan — critical gap",
                "field": "no_documentation_provided",
            }
        )
        return DimensionScore(dimension="incident_response", score=0, max_score=100, flags=flags)

    score = 0.0

    has_ir_plan = findings.get("has_ai_ir_plan", False)
    if has_ir_plan:
        score += 40
    else:
        flags.append(
            {
                "severity": "critical",
                "text": "No AI incident response plan documented",
                "field": "has_ai_ir_plan",
            }
        )

    if findings.get("incident_classification_defined"):
        score += 20
    if findings.get("regulator_notification_procedure"):
        score += 20
    if findings.get("post_incident_review_required"):
        score += 10
    if findings.get("rollback_procedures_documented"):
        score += 10

    # Apply staleness multiplier
    months_old = findings.get("ir_plan_months_old")
    multiplier = get_staleness_multiplier(months_old)
    if multiplier < 1.0:
        flags.append(
            {
                "severity": "warning",
                "text": f"Incident response plan is {months_old} months old — staleness penalty applied",
                "field": "ir_plan_months_old",
            }
        )
    score *= multiplier

    if findings.get("active_incidents_or_complaints") and not has_ir_plan:
        flags.append(
            {
                "severity": "critical",
                "text": "Active incident/complaint with no documented IR process",
                "field": "active_incidents_or_complaints",
            }
        )

    if findings.get("active_litigation"):
        flags.append(
            {
                "severity": "critical",
                "text": "Active litigation — IR plan absence is critical",
                "field": "active_litigation",
            }
        )

    return DimensionScore(dimension="incident_response", score=score, max_score=100, flags=flags)
