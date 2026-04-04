"""
Governance extractor: orchestrates parallel extraction of all 8 governance dimensions
from document chunks using Claude tool_use.
"""

import asyncio
import importlib
from collections import defaultdict

import structlog
from anthropic import AsyncAnthropic

from app.config import settings
from app.llm.client import call_tool_use

log = structlog.get_logger()

GOVERNANCE_DIMENSIONS = [
    "model_inventory",
    "human_oversight",
    "bias_fairness",
    "data_governance",
    "incident_response",
    "monitoring_drift",
    "regulatory_compliance",
    "third_party_risk",
]

# Relevance keywords per dimension - used to filter chunks before sending to LLM.
# Rules:
#  - Prefer specific phrases over single common words to avoid false matches from
#    unrelated documents (e.g. "model" appears everywhere; "model inventory" does not).
#  - Keywords also match the [Source: filename] header prepended by verify_extraction.py,
#    so e.g. "inventory" will include all chunks from "model_inventory.txt" even if the
#    chunk body doesn't mention it - this is intentional and desirable.
_DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "model_inventory": [
        "model inventory",  # matches inventory doc title + header tag
        "model card",  # matches model card documents
        "model register",  # alternative inventory naming
        "risk tier",  # classification field in inventories / cards
        "model id",  # registry field
        "inventory",  # part of inventory doc filename/title
        "ai system",  # reasonably specific
        "machine learning",
        "deployed",
        "production",
        "algorithm",
        # "model"  ← removed: appears in virtually every governance document
        # "system" ← removed: too generic
    ],
    "human_oversight": [
        "hitl",  # specific acronym
        "human-in-the-loop",  # explicit phrase
        "human oversight",  # policy-level phrase
        "oversight policy",
        "mandatory review",  # more specific than bare "review"
        "review queue",
        "override authority",
        "review policy",
        "review cadence",
        "escalat",  # escalation-related content
        "operator",
        "decision maker",
        "supervisor",
        # "review"  ← removed: appears in bias audits, data governance, incident plans
        # "human"   ← removed: appears broadly
        # "manual"  ← removed: too generic
        # "approval" ← removed: too generic
    ],
    "bias_fairness": [
        "bias",
        "fairness",
        "impact ratio",
        "disparate",
        "protected class",
        "eeoc",
        "audit",
        "discrimination",
        "equity",
        "demographic",
        "ll144",
        "adverse impact",
    ],
    "data_governance": [
        "data governance",
        "retention",
        "consent",
        "provenance",
        "dpia",
        "training data",
        "data source",
        "cross-border",
        "gdpr",
        "personal data",
        "sensitive data",
    ],
    "incident_response": [
        "incident",
        "response",
        "breach",
        "notification",
        "rollback",
        "escalat",
        "sla",
        "post-incident",
        "root cause",
        "investigation",
        "disaster recovery",
    ],
    "monitoring_drift": [
        "monitor",
        "drift",
        "retrain",
        "alert",
        "threshold",
        "degradation",
        "kpi",
        "monitoring runbook",  # matches runbook filename header tag
        "retraining trigger",  # specific phrase
        "score distribution",  # drift methodology phrase
        "cloudwatch",  # specific tooling
        "datadog",  # specific tooling
        # "performance" ← removed: appears heavily in model cards and bias audits
        # "precision"   ← removed: appears in bias audits
        # "recall"      ← removed: appears in bias audits
        # "f1"          ← kept below only as substring - too noisy when removed
        "f1",
        "accuracy",
    ],
    "regulatory_compliance": [
        "compliance",
        "regulation",
        "nist",
        "iso",
        "eu ai act",
        "ll144",
        "colorado",
        "sb21",
        "gdpr",
        "legal",
        "framework",
        "certif",
    ],
    "third_party_risk": [
        "vendor",
        "third party",
        "third-party",
        "supplier",
        "openai",
        "chatgpt",
        "anthropic",
        "contract",
        "sow",
        "api",
        "external",
        "procurement",
    ],
}


def _filter_chunks_for_dimension(
    chunks: list[str],
    dimension: str,
    max_chunks: int = 10,
) -> list[str]:
    """
    Return relevant chunks for the given dimension using document-balanced selection.

    When chunks carry ``[Source: filename]`` headers (added by verify_extraction.py),
    each source document contributes at most *max_chunks* matching chunks.  This
    prevents a single large document whose content happens to match many keywords
    (e.g. a bias audit that mentions "model" 50 times) from filling the entire
    context window and crowding out the document that actually governs the dimension.

    For untagged chunks (legacy test fixtures or direct API usage), the function
    falls back to the original global top-N behaviour so existing tests are
    unaffected.
    """
    keywords = _DIMENSION_KEYWORDS.get(dimension, [])

    # Group by source document (tagged chunks) or treat all as one group (untagged).
    doc_groups: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        if chunk.startswith("[Source: ") and "\n" in chunk:
            newline_pos = chunk.index("\n")
            source = chunk[9:newline_pos].rstrip("]")
            doc_groups[source].append(chunk)
        else:
            doc_groups["__untagged__"].append(chunk)

    result: list[str] = []
    for doc_chunk_list in doc_groups.values():
        matching = [c for c in doc_chunk_list if any(kw.lower() in c.lower() for kw in keywords)]
        result.extend(matching[:max_chunks])

    return result


def _load_prompt(dimension: str) -> tuple[str, dict]:
    """Dynamically load SYSTEM_PROMPT and TOOL_SCHEMA for a dimension."""
    module = importlib.import_module(f"app.llm.prompts.{dimension}")
    return module.SYSTEM_PROMPT, module.TOOL_SCHEMA


async def _extract_dimension_with_semaphore(
    dimension: str,
    relevant_chunks: list[str],
    client: AsyncAnthropic,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Wraps extract_dimension with a semaphore to cap concurrent LLM calls."""
    async with semaphore:
        return await extract_dimension(dimension, relevant_chunks, client)


async def extract_dimension(
    dimension: str,
    relevant_chunks: list[str],
    client: AsyncAnthropic,
) -> dict:
    """
    Extract governance findings for a single dimension.

    If relevant_chunks is empty, returns {"no_documentation_provided": True}
    immediately without an LLM call.

    Args:
        dimension: One of the 8 GOVERNANCE_DIMENSIONS.
        relevant_chunks: Document chunks relevant to this dimension.
        client: AsyncAnthropic client.

    Returns:
        Findings dict matching the scoring rule's expected keys.
    """
    bound_log = log.bind(dimension=dimension)

    if not relevant_chunks:
        bound_log.info("extraction.no_docs")
        return {"no_documentation_provided": True}

    system_prompt, tool_schema = _load_prompt(dimension)

    combined = "\n---\n".join(relevant_chunks)
    user_message = f"Analyze the following governance document excerpts for the '{dimension}' dimension:\n\n{combined}"

    result = await call_tool_use(
        client=client,
        model=settings.LLM_EXTRACTION_MODEL,
        system_prompt=system_prompt,
        user_message=user_message,
        tool_schema=tool_schema,
    )
    bound_log.info("extraction.complete", fields=list(result.keys()))
    return result


_RETRY_DELAY_SECONDS = 45
_MAX_DIMENSION_RETRIES = 1


async def extract_all_dimensions(
    doc_chunks: list[str],
    client: AsyncAnthropic,
) -> dict[str, dict]:
    """
    Run extraction for all 8 governance dimensions in parallel.

    Failed dimensions (due to API overload or transient errors) are retried once
    after a delay.  Only genuinely absent documents produce no_documentation_provided.

    Args:
        doc_chunks: All document chunks from the assessment's uploaded documents.
        client: AsyncAnthropic client.

    Returns:
        Dict mapping dimension name → findings dict.
    """
    log.info(
        "extraction.pipeline.start",
        total_chunks=len(doc_chunks),
        concurrency=settings.EXTRACTION_CONCURRENCY,
    )

    # Pre-filter chunks per dimension before the gather
    dimension_chunks = {dim: _filter_chunks_for_dimension(doc_chunks, dim) for dim in GOVERNANCE_DIMENSIONS}

    # Semaphore caps concurrent LLM calls to avoid hitting per-minute token rate limits.
    semaphore = asyncio.Semaphore(settings.EXTRACTION_CONCURRENCY)

    raw_results = await asyncio.gather(
        *[
            _extract_dimension_with_semaphore(dim, dimension_chunks[dim], client, semaphore)
            for dim in GOVERNANCE_DIMENSIONS
        ],
        return_exceptions=True,
    )

    findings: dict[str, dict] = {}
    failed_dims: list[str] = []

    for dim, result in zip(GOVERNANCE_DIMENSIONS, raw_results, strict=True):
        if isinstance(result, Exception):
            log.warning(
                "extraction.dimension_failed",
                dimension=dim,
                error=str(result),
                retry_in=_RETRY_DELAY_SECONDS,
            )
            failed_dims.append(dim)
        else:
            findings[dim] = result

    # Retry failed dimensions sequentially after a delay so the API can recover.
    if failed_dims:
        log.info("extraction.retrying_failed", dimensions=failed_dims, delay=_RETRY_DELAY_SECONDS)
        await asyncio.sleep(_RETRY_DELAY_SECONDS)
        for dim in failed_dims:
            try:
                findings[dim] = await extract_dimension(dim, dimension_chunks[dim], client)
            except Exception as exc:
                log.error("extraction.dimension_failed_final", dimension=dim, error=str(exc))
                # Only after exhausting retries do we fall back to no_documentation_provided.
                findings[dim] = {"no_documentation_provided": True}

    log.info("extraction.pipeline.complete", dimensions=list(findings.keys()))
    return findings
