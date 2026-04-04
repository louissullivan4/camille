from collections.abc import Callable
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger()

DEFAULT_WEIGHTS: dict[str, float] = {
    "model_inventory": 0.15,
    "human_oversight": 0.20,
    "bias_fairness": 0.15,
    "data_governance": 0.10,
    "incident_response": 0.15,
    "monitoring_drift": 0.10,
    "regulatory_compliance": 0.10,
    "third_party_risk": 0.05,
}


@dataclass
class DimensionScore:
    dimension: str
    score: float
    max_score: float
    flags: list[dict] = field(default_factory=list)


@dataclass
class AssessmentScore:
    overall_score: float
    risk_tier: str
    dimension_scores: dict[str, DimensionScore]
    all_flags: list[dict]


def get_staleness_multiplier(months_old: int | None) -> float:
    """
    Return a staleness multiplier based on document age in months.

    Tiers:
      ≤12 months  → 1.0  (current)
      13–24 months → 0.75 (recent — minor penalty)
      >24 months   → 0.50 (stale — significant penalty)
    """
    if months_old is None or months_old == 0:
        return 1.0
    if months_old <= 12:
        return 1.0
    if months_old <= 24:
        return 0.75
    return 0.5


def _assign_risk_tier(score: float) -> str:
    if score >= 75:
        return "low"
    if score >= 50:
        return "medium"
    if score >= 25:
        return "high"
    return "critical"


def score_assessment(
    findings: dict[str, dict],
    assessment_config: dict | None = None,
) -> AssessmentScore:
    """
    Orchestrate scoring across all 8 governance dimensions.

    findings: maps dimension name -> extraction findings dict
    assessment_config: optional dict with {"weight_overrides": {...}}
    """
    # Import here to avoid circular imports at module load time
    from app.services.scoring_rules.bias_fairness import score_bias_fairness
    from app.services.scoring_rules.data_governance import score_data_governance
    from app.services.scoring_rules.human_oversight import score_human_oversight
    from app.services.scoring_rules.incident_response import score_incident_response
    from app.services.scoring_rules.model_inventory import score_model_inventory
    from app.services.scoring_rules.monitoring_drift import score_monitoring_drift
    from app.services.scoring_rules.regulatory_compliance import score_regulatory_compliance
    from app.services.scoring_rules.third_party_risk import score_third_party_risk

    scorers: dict[str, Callable[[dict], DimensionScore]] = {
        "model_inventory": score_model_inventory,
        "human_oversight": score_human_oversight,
        "bias_fairness": score_bias_fairness,
        "data_governance": score_data_governance,
        "incident_response": score_incident_response,
        "monitoring_drift": score_monitoring_drift,
        "regulatory_compliance": score_regulatory_compliance,
        "third_party_risk": score_third_party_risk,
    }

    # Merge weight overrides
    weights = dict(DEFAULT_WEIGHTS)
    if assessment_config and "weight_overrides" in assessment_config:
        for dim, w in assessment_config["weight_overrides"].items():
            if dim in weights:
                weights[dim] = w

    dimension_scores: dict[str, DimensionScore] = {}
    all_flags: list[dict] = []

    for dimension, scorer in scorers.items():
        dim_findings = findings.get(dimension, {"no_documentation_provided": True})
        dim_score = scorer(dim_findings)
        dimension_scores[dimension] = dim_score
        for flag in dim_score.flags:
            enriched = dict(flag)
            enriched["dimension"] = dimension
            all_flags.append(enriched)

        log.info(
            "scoring.dimension.complete",
            dimension=dimension,
            score=dim_score.score,
            flags=len(dim_score.flags),
        )

    overall_score = sum(
        dimension_scores[dim].score * weights[dim]
        for dim in scorers
    )
    risk_tier = _assign_risk_tier(overall_score)

    log.info(
        "scoring.assessment.complete",
        overall_score=overall_score,
        risk_tier=risk_tier,
    )

    return AssessmentScore(
        overall_score=overall_score,
        risk_tier=risk_tier,
        dimension_scores=dimension_scores,
        all_flags=all_flags,
    )
