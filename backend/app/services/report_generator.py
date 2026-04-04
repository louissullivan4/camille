"""
PDF Report Generator.

Generates a professional insurance-style risk assessment report:
  1. Load assessment + org + documents from DB
  2. Call Claude Opus for a 3-sentence executive summary narrative
  3. Render Jinja2 HTML → WeasyPrint PDF bytes
  4. Upload to S3 and return the S3 key

Returns the S3 key (stored as assessment.report_url by the pipeline).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.client import get_anthropic_client
from app.models.assessment import Assessment
from app.models.document import Document
from app.models.organization import Organization
from app.services.storage import upload_bytes

log = structlog.get_logger()

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_NARRATIVE_SYSTEM = """You are a senior insurance underwriter writing a concise risk assessment narrative.
Given a company's AI governance scores and critical flags, write exactly 3 sentences:
1. Overall risk characterization and score context.
2. The most significant governance gap(s) driving the risk rating.
3. A concrete recommendation for the underwriter (e.g. decline, accept with conditions, request remediation).
Be direct and professional. Do not use bullet points or headers.
Do not use em dashes (\u2014); use commas, semicolons, or colons instead."""

_NARRATIVE_TOOL: dict = {
    "name": "write_executive_summary",
    "description": "Write a 3-sentence executive summary narrative for the risk report",
    "input_schema": {
        "type": "object",
        "required": ["narrative"],
        "properties": {
            "narrative": {
                "type": "string",
                "description": "Exactly 3 sentences summarising the risk assessment",
            }
        },
    },
}

_DIMENSION_LABELS: dict[str, str] = {
    "model_inventory": "Model Inventory",
    "human_oversight": "Human Oversight",
    "bias_fairness": "Bias & Fairness",
    "data_governance": "Data Governance",
    "incident_response": "Incident Response",
    "monitoring_drift": "Monitoring & Drift",
    "regulatory_compliance": "Regulatory Compliance",
    "third_party_risk": "Third-Party Risk",
}

_DIMENSION_WEIGHTS: dict[str, float] = {
    "model_inventory": 0.15,
    "human_oversight": 0.20,
    "bias_fairness": 0.15,
    "data_governance": 0.10,
    "incident_response": 0.15,
    "monitoring_drift": 0.10,
    "regulatory_compliance": 0.10,
    "third_party_risk": 0.05,
}


async def _generate_narrative(
    org_name: str,
    overall_score: float,
    risk_tier: str,
    dimension_scores: dict,
    all_flags: list[dict],
) -> str:
    """Call Claude Opus to generate a 3-sentence executive summary."""
    client = get_anthropic_client()

    critical_flags = [f for f in all_flags if f.get("severity") == "critical"]
    flag_summary = "; ".join(f["text"] for f in critical_flags[:5]) if critical_flags else "none"

    dim_summary = "\n".join(
        f"  {_DIMENSION_LABELS.get(dim, dim)}: {data.get('score', 0):.0f}/100" for dim, data in dimension_scores.items()
    )

    user_message = (
        f"Company: {org_name}\n"
        f"Overall score: {overall_score:.1f}/100, Risk tier: {risk_tier.upper()}\n"
        f"Dimension scores:\n{dim_summary}\n"
        f"Critical flags: {flag_summary}"
    )

    response = await client.messages.create(
        model=settings.LLM_REPORT_MODEL,
        max_tokens=512,
        system=_NARRATIVE_SYSTEM,
        tools=[_NARRATIVE_TOOL],
        tool_choice={"type": "tool", "name": _NARRATIVE_TOOL["name"]},
        messages=[{"role": "user", "content": user_message}],
    )

    log.info(
        "report.narrative.complete",
        model=settings.LLM_REPORT_MODEL,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        return f"{org_name} presents a {risk_tier} risk profile with an overall score of {overall_score:.1f}/100."

    return _remove_em_dashes(tool_block.input["narrative"])


def _strip_weasyprint_css(html: str) -> str:
    """Remove WeasyPrint-only CSS that xhtml2pdf cannot parse.

    Specifically, strips nested ``@bottom-center`` / ``@bottom-right`` blocks
    inside ``@page`` rules.  The outer ``@page { size: A4; margin: ... }``
    declaration is preserved so basic page sizing still works.
    """
    import re

    return re.sub(r"@(?:bottom|top)-\w+\s*\{[^}]*\}", "", html)


def _render_pdf(html: str) -> bytes:
    """Convert HTML string to PDF bytes.

    Tries WeasyPrint first (best quality); falls back to xhtml2pdf when GTK
    native libraries are unavailable (e.g. Windows without GTK runtime).
    """
    try:
        from weasyprint import HTML

        return HTML(string=html, base_url=str(_TEMPLATE_DIR)).write_pdf()  # type: ignore[no-any-return]
    except Exception as wp_exc:
        _wp_msg = str(wp_exc).lower()
        _is_missing_lib = any(
            kw in _wp_msg
            for kw in (
                "libgobject",
                "cannot load library",
                "could not find",  # weasyprint 60+ on Windows
                "no such file",
                "dll load failed",  # Windows DLL error
                "winerror",
                "the specified module",  # Windows: "The specified module could not be found"
                "oserror",
            )
        )
        if not _is_missing_lib:
            raise
        log.warning("report_generator.weasyprint_unavailable", error=str(wp_exc), fallback="xhtml2pdf")

    import io

    from xhtml2pdf import pisa  # type: ignore[import-untyped]

    buf = io.BytesIO()
    result = pisa.CreatePDF(_strip_weasyprint_css(html), dest=buf)
    if result.err:
        raise RuntimeError(f"xhtml2pdf rendering failed with {result.err} error(s)")
    return buf.getvalue()


async def generate_report(assessment_id: uuid.UUID, db: AsyncSession) -> str:
    """
    Generate a PDF risk report and upload it to S3.

    Returns the S3 key for the uploaded PDF.
    """
    bound_log = log.bind(assessment_id=str(assessment_id))
    bound_log.info("report_generator.start")

    # ── Load data from DB ────────────────────────────────────────────────────
    a_result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = a_result.scalar_one_or_none()
    if assessment is None:
        raise ValueError(f"Assessment {assessment_id} not found")

    org_result = await db.execute(select(Organization).where(Organization.id == assessment.organization_id))
    org = org_result.scalar_one_or_none()
    org_name = org.name if org else "Unknown Organization"

    docs_result = await db.execute(select(Document).where(Document.assessment_id == assessment_id))
    documents = docs_result.scalars().all()

    overall_score: float = assessment.overall_score or 0.0
    risk_tier: str = assessment.risk_tier or "unknown"
    dimension_scores: dict = assessment.dimension_scores or {}
    all_flags: list[dict] = (assessment.flags or {}).get("all_flags", [])

    # ── Generate narrative via Claude Opus ───────────────────────────────────
    try:
        narrative = await _generate_narrative(
            org_name=org_name,
            overall_score=overall_score,
            risk_tier=risk_tier,
            dimension_scores=dimension_scores,
            all_flags=all_flags,
        )
    except Exception as exc:
        bound_log.warning("report_generator.narrative_failed", error=str(exc))
        narrative = (
            f"{org_name} has been assessed with an overall governance score of "
            f"{overall_score:.1f}/100, placing it in the {risk_tier} risk tier."
        )

    # ── Render HTML template ─────────────────────────────────────────────────
    jinja_env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = jinja_env.get_template("report.html")

    # Build per-dimension rows for the template
    dimension_rows = []
    for dim_key, data in dimension_scores.items():
        score = data.get("score", 0)
        flags = data.get("flags", [])
        critical_count = sum(1 for f in flags if f.get("severity") == "critical")
        warning_count = sum(1 for f in flags if f.get("severity") == "warning")
        dimension_rows.append(
            {
                "key": dim_key,
                "label": _DIMENSION_LABELS.get(dim_key, dim_key),
                "score": score,
                "weight_pct": int(_DIMENSION_WEIGHTS.get(dim_key, 0) * 100),
                "flags": flags,
                "critical_count": critical_count,
                "warning_count": warning_count,
                "score_color": _score_color(score),
            }
        )

    critical_flags = [f for f in all_flags if f.get("severity") == "critical"]
    warning_flags = [f for f in all_flags if f.get("severity") == "warning"]

    html = template.render(
        org_name=org_name,
        report_date=datetime.now(UTC).strftime("%B %d, %Y"),
        overall_score=overall_score,
        risk_tier=risk_tier,
        risk_tier_color=_tier_color(risk_tier),
        narrative=narrative,
        dimension_rows=dimension_rows,
        critical_flags=critical_flags,
        warning_flags=warning_flags,
        documents=[{"filename": d.filename, "doc_type": d.doc_type or "unknown"} for d in documents],
        generated_by="Camille AI Risk Assessment",
    )

    # ── Render PDF in executor (WeasyPrint is sync/CPU-bound) ────────────────
    # 90-second timeout guards against WeasyPrint hanging on Windows when GTK
    # DLLs are missing but don't raise a clean exception.
    loop = asyncio.get_event_loop()
    try:
        pdf_bytes = await asyncio.wait_for(
            loop.run_in_executor(None, _render_pdf, html),
            timeout=90.0,
        )
    except TimeoutError:
        bound_log.warning(
            "report_generator.pdf_render_timeout",
            hint="WeasyPrint likely requires GTK runtime on this platform",
        )
        raise RuntimeError("PDF rendering timed out (90s); install GTK3 runtime or set S3_ENDPOINT_URL to skip")
    bound_log.info("report_generator.pdf_rendered", size_bytes=len(pdf_bytes))

    # ── Upload to S3 ─────────────────────────────────────────────────────────
    s3_key = f"reports/{assessment_id}/risk_report.pdf"
    await upload_bytes(s3_key, pdf_bytes, content_type="application/pdf")
    bound_log.info("report_generator.uploaded", s3_key=s3_key)

    return s3_key


def _remove_em_dashes(text: str) -> str:
    """Replace em dashes in LLM-generated text with a semicolon + space."""
    return text.replace("\u2014", "; ")


def _score_color(score: float) -> str:
    if score >= 75:
        return "#2e7d32"  # green
    if score >= 50:
        return "#f57c00"  # amber
    if score >= 25:
        return "#c62828"  # red
    return "#7b1fa2"  # purple (critical)


def _tier_color(tier: str) -> str:
    return {
        "low": "#2e7d32",
        "medium": "#f57c00",
        "high": "#c62828",
        "critical": "#7b1fa2",
    }.get(tier, "#546e7a")
