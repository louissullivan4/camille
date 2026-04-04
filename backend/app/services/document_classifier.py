"""
Document classifier: determines the type of an AI governance document
and which scoring dimensions it contains evidence for.
"""

from dataclasses import dataclass

import structlog
from anthropic import AsyncAnthropic

from app.config import settings
from app.llm.client import call_tool_use
from app.llm.schemas import CLASSIFY_DOCUMENT_TOOL

log = structlog.get_logger()

_CLASSIFICATION_SYSTEM_PROMPT = """\
You are an AI governance document analyst.

Classify the provided document excerpt by its primary type and identify which of the \
8 AI governance scoring dimensions it contains relevant evidence for.

Document types:
- model_card: describes a specific AI/ML model (purpose, architecture, training data, performance)
- bias_audit: bias testing, fairness evaluation, impact ratio analysis
- hitl_policy: human-in-the-loop policy, human review procedures, override authority
- data_governance: data handling, retention, consent, provenance, DPIA
- ir_plan: incident response, breach notification, rollback procedures
- monitoring: model performance monitoring, drift detection, retraining triggers
- compliance: regulatory compliance, framework alignment (NIST, ISO, EU AI Act, NYC LL144)
- vendor_risk: third-party AI vendor inventory, vendor risk assessments
- unknown: document does not fit any governance category

Be conservative: only mark a dimension as relevant if the document contains substantive \
evidence for that dimension, not just a passing mention.
"""


@dataclass
class DocumentClassification:
    doc_type: str
    confidence: float
    relevant_dimensions: list[str]
    reasoning: str


async def classify_document(
    text: str,
    client: AsyncAnthropic,
) -> DocumentClassification:
    """
    Classify an AI governance document by type and relevant dimensions.

    Args:
        text: Document text (or first chunk if document is large).
        client: AsyncAnthropic client instance.

    Returns:
        DocumentClassification with doc_type, confidence, relevant_dimensions, reasoning.
    """
    # Truncate to ~3000 chars for classification - we only need enough to identify type
    excerpt = text[:3000] if len(text) > 3000 else text

    result = await call_tool_use(
        client=client,
        model=settings.LLM_CLASSIFICATION_MODEL,
        system_prompt=_CLASSIFICATION_SYSTEM_PROMPT,
        user_message=f"Classify this document:\n\n{excerpt}",
        tool_schema=CLASSIFY_DOCUMENT_TOOL,
    )

    log.info(
        "document.classified",
        doc_type=result["doc_type"],
        confidence=result["confidence"],
        relevant_dimensions=result["relevant_dimensions"],
    )

    return DocumentClassification(
        doc_type=result["doc_type"],
        confidence=result["confidence"],
        relevant_dimensions=result["relevant_dimensions"],
        reasoning=result["reasoning"],
    )
