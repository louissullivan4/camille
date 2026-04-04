from app.services.scoring_engine import DimensionScore, get_staleness_multiplier


def score_model_inventory(findings: dict) -> DimensionScore:
    """Score the model_inventory governance dimension."""
    flags: list[dict] = []

    if findings.get("no_documentation_provided"):
        flags.append(
            {
                "severity": "critical",
                "text": "No documentation provided for this dimension",
                "field": "no_documentation_provided",
            }
        )
        return DimensionScore(dimension="model_inventory", score=0, max_score=100, flags=flags)

    score = 0.0

    if findings.get("has_formal_inventory"):
        score += 40
    if findings.get("models_fully_documented"):
        score += 20
    if findings.get("risk_classification_present"):
        score += 20
    if findings.get("deployment_env_documented"):
        score += 10
    if findings.get("decision_types_documented"):
        score += 10

    # Apply staleness multiplier to total
    months_old = findings.get("inventory_months_old")
    multiplier = get_staleness_multiplier(months_old)
    if multiplier < 1.0:
        flags.append(
            {
                "severity": "warning",
                "text": f"Model inventory is {months_old} months old - staleness penalty applied",
                "field": "inventory_months_old",
            }
        )
    score *= multiplier

    for system in findings.get("undocumented_systems", []):
        flags.append(
            {
                "severity": "warning",
                "text": f"Undocumented AI system: {system}",
                "field": "undocumented_systems",
            }
        )

    if findings.get("chatgpt_or_third_party_undisclosed"):
        flags.append(
            {
                "severity": "critical",
                "text": "Third-party AI (e.g., ChatGPT) used without disclosure or governance wrapper",
                "field": "chatgpt_or_third_party_undisclosed",
            }
        )

    return DimensionScore(dimension="model_inventory", score=score, max_score=100, flags=flags)
