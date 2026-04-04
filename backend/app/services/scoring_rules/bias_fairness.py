from app.services.scoring_engine import DimensionScore, get_staleness_multiplier


def score_bias_fairness(findings: dict) -> DimensionScore:
    """
    Score the bias_fairness governance dimension.

    Points are split into two buckets:
    - Presence points: evidence of bias measurement exists (not staleness-penalized)
    - Quality points: how good/rigorous the audit is (staleness-penalized)

    This distinction matters: a 3-year-old audit still proves the company ran
    impact ratios - but the rigor and cadence signals are stale.
    """
    flags: list[dict] = []

    if findings.get("no_documentation_provided"):
        flags.append(
            {
                "severity": "critical",
                "text": "No documentation provided for this dimension",
                "field": "no_documentation_provided",
            }
        )
        return DimensionScore(dimension="bias_fairness", score=0, max_score=100, flags=flags)

    # Presence signals - not staleness-penalized
    presence = 0.0

    if findings.get("has_bias_audit"):
        presence += 10
    if findings.get("impact_ratios_documented"):
        presence += 10
    if findings.get("impact_ratios_above_threshold"):
        presence += 10

    protected_count = findings.get("protected_classes_count", 0)
    if protected_count >= 3:
        presence += 15
    elif protected_count >= 1:
        presence += 8

    # Quality signals - staleness-penalized
    quality = 0.0

    if findings.get("third_party_auditor"):
        quality += 20
    elif findings.get("has_bias_audit"):
        flags.append(
            {
                "severity": "warning",
                "text": "Bias audit self-assessed, not independent",
                "field": "third_party_auditor",
            }
        )

    audit_cadence = findings.get("audit_cadence")
    if audit_cadence == "quarterly":
        quality += 15
    elif audit_cadence == "annual":
        quality += 15
    elif audit_cadence == "at_launch_only":
        quality += 5

    if findings.get("remediation_documented"):
        quality += 15

    # Apply staleness multiplier to quality only
    months_old = findings.get("audit_months_old")
    multiplier = get_staleness_multiplier(months_old)
    if multiplier < 1.0:
        flags.append(
            {
                "severity": "warning",
                "text": f"Bias audit is {months_old} months old - staleness penalty applied to quality signals",
                "field": "audit_months_old",
            }
        )

    score = presence + quality * multiplier

    if findings.get("impact_ratios_borderline"):
        flags.append(
            {
                "severity": "warning",
                "text": "Impact ratios borderline: near 80% rule threshold",
                "field": "impact_ratios_borderline",
            }
        )

    if findings.get("active_eeoc_or_complaint"):
        flags.append(
            {
                "severity": "critical",
                "text": "Active EEOC/discrimination complaint",
                "field": "active_eeoc_or_complaint",
            }
        )

    nyc_applies = findings.get("nyc_ll144_applies", False)
    nyc_compliant = findings.get("nyc_ll144_compliant", False)
    if nyc_applies and not nyc_compliant:
        flags.append(
            {
                "severity": "critical",
                "text": "NYC Local Law 144 applies but no compliance documentation",
                "field": "nyc_ll144_compliant",
            }
        )

    if findings.get("nyc_ll144_independent_auditor_required") and not findings.get("third_party_auditor"):
        flags.append(
            {
                "severity": "critical",
                "text": "LL144 requires independent auditor: self-assessment does not comply",
                "field": "nyc_ll144_independent_auditor_required",
            }
        )

    return DimensionScore(dimension="bias_fairness", score=score, max_score=100, flags=flags)
