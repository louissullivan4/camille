from app.services.scoring_engine import DimensionScore, get_staleness_multiplier

FRAMEWORK_POINTS: dict[str, int] = {
    "nist_rmf": 25,
    "iso_42001": 20,
    "eu_ai_act": 20,
    "nist_ai_100_1": 15,
}
FRAMEWORK_POINTS_CAP = 40


def score_regulatory_compliance(findings: dict) -> DimensionScore:
    """Score the regulatory_compliance governance dimension."""
    flags: list[dict] = []

    if findings.get("no_documentation_provided"):
        flags.append(
            {
                "severity": "critical",
                "text": "No documentation provided for this dimension",
                "field": "no_documentation_provided",
            }
        )
        return DimensionScore(dimension="regulatory_compliance", score=0, max_score=100, flags=flags)

    score = 0.0

    # Framework alignment — capped at 40
    framework_score = 0
    for fw in findings.get("framework_alignment", []):
        framework_score += FRAMEWORK_POINTS.get(fw, 0)
    framework_score = min(framework_score, FRAMEWORK_POINTS_CAP)
    score += framework_score

    # NYC LL144
    nyc_applies = findings.get("nyc_ll144_applies", False)
    nyc_compliant = findings.get("nyc_ll144_compliant", False)
    if nyc_applies and nyc_compliant:
        score += 20
    elif nyc_applies and not nyc_compliant:
        flags.append(
            {
                "severity": "critical",
                "text": "NYC LL144 applies — no compliance documentation",
                "field": "nyc_ll144_compliant",
            }
        )

    # Colorado SB21-169
    if findings.get("colorado_sb21_169_applies") and not findings.get("colorado_sb21_169_compliant", False):
        flags.append(
            {
                "severity": "critical",
                "text": "Colorado SB21-169 likely applies — no compliance documentation",
                "field": "colorado_sb21_169_applies",
            }
        )

    if findings.get("eu_ai_act_classification_documented"):
        score += 10

    if findings.get("active_regulatory_inquiry"):
        flags.append(
            {
                "severity": "critical",
                "text": "Active regulatory inquiry",
                "field": "active_regulatory_inquiry",
            }
        )

    if findings.get("active_litigation"):
        flags.append(
            {
                "severity": "critical",
                "text": "Active litigation creates regulatory exposure",
                "field": "active_litigation",
            }
        )

    if findings.get("general_legal_awareness"):
        score += 20  # Company shows awareness of applicable law

    # Apply staleness multiplier
    months_old = findings.get("compliance_months_old")
    multiplier = get_staleness_multiplier(months_old)
    if multiplier < 1.0:
        flags.append(
            {
                "severity": "warning",
                "text": f"Compliance documentation is {months_old} months old — staleness penalty applied",
                "field": "compliance_months_old",
            }
        )
    score *= multiplier

    return DimensionScore(dimension="regulatory_compliance", score=score, max_score=100, flags=flags)
