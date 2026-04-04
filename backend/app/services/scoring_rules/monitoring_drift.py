from app.services.scoring_engine import DimensionScore, get_staleness_multiplier


def score_monitoring_drift(findings: dict) -> DimensionScore:
    """Score the monitoring_drift governance dimension."""
    flags: list[dict] = []

    if findings.get("no_documentation_provided"):
        flags.append(
            {
                "severity": "critical",
                "text": "No documentation provided for this dimension",
                "field": "no_documentation_provided",
            }
        )
        return DimensionScore(dimension="monitoring_drift", score=0, max_score=100, flags=flags)

    score = 0.0

    vague_only = findings.get("vague_monitoring_reference_only", False)

    if vague_only:
        # Vague reference only: overrides has_monitoring_documentation full credit
        score += 10
        flags.append(
            {
                "severity": "warning",
                "text": "Monitoring referenced but not operationally documented",
                "field": "vague_monitoring_reference_only",
            }
        )
    elif findings.get("has_monitoring_documentation"):
        score += 25

    if findings.get("drift_detection_methodology"):
        score += 25
    if findings.get("retraining_triggers_defined"):
        score += 25
    if findings.get("alerting_mechanism_documented"):
        score += 25

    # Apply staleness multiplier
    months_old = findings.get("monitoring_months_old")
    multiplier = get_staleness_multiplier(months_old)
    if multiplier < 1.0:
        flags.append(
            {
                "severity": "warning",
                "text": f"Monitoring documentation is {months_old} months old - staleness penalty applied",
                "field": "monitoring_months_old",
            }
        )
    score *= multiplier

    return DimensionScore(dimension="monitoring_drift", score=score, max_score=100, flags=flags)
