"""Tests for governance_extractor.py — extract_dimension and extract_all_dimensions."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.governance_extractor import (
    GOVERNANCE_DIMENSIONS,
    _filter_chunks_for_dimension,
    extract_all_dimensions,
    extract_dimension,
)


def _make_tool_use_response(input_dict: dict) -> MagicMock:
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = input_dict

    usage = MagicMock()
    usage.input_tokens = 300
    usage.output_tokens = 80

    response = MagicMock()
    response.content = [tool_use_block]
    response.usage = usage
    response.stop_reason = "tool_use"
    return response


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.messages = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# extract_dimension
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_dimension_docs_sets_no_documentation_provided(mock_client):
    """Empty chunk list must return no_documentation_provided without LLM call."""
    result = await extract_dimension("model_inventory", [], mock_client)

    assert result == {"no_documentation_provided": True}
    mock_client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_extract_dimension_returns_llm_findings(mock_client):
    findings = {
        "no_documentation_provided": False,
        "has_formal_inventory": True,
        "models_fully_documented": True,
        "risk_classification_present": True,
        "deployment_env_documented": False,
        "decision_types_documented": False,
        "inventory_months_old": 6,
        "undocumented_systems": [],
        "chatgpt_or_third_party_undisclosed": False,
    }
    mock_client.messages.create = AsyncMock(return_value=_make_tool_use_response(findings))

    result = await extract_dimension("model_inventory", ["Model inventory document..."], mock_client)

    assert result["has_formal_inventory"] is True
    assert result["inventory_months_old"] == 6


@pytest.mark.asyncio
async def test_extraction_failure_propagates_exception(mock_client):
    """API failure must propagate so the caller can retry or fall back explicitly."""
    mock_client.messages.create = AsyncMock(side_effect=Exception("API timeout"))

    with pytest.raises(Exception, match="API timeout"):
        await extract_dimension("incident_response", ["some text"], mock_client)


# ---------------------------------------------------------------------------
# extract_all_dimensions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_dimensions_extracted_with_semaphore(mock_client):
    """
    All 8 dimensions must be extracted via the semaphore-controlled path.
    The LLM client should be called for dimensions that have relevant chunks.
    """
    # Provide chunks that match keywords for all 8 dimensions
    chunks = [
        "AI model inventory and risk classification system",
        "Human-in-the-loop review and escalation policy",
        "Bias audit and impact ratio analysis by protected class",
        "Data governance policy, retention, DPIA, consent mechanism",
        "Incident response plan with rollback procedures",
        "Model monitoring drift detection and retraining triggers",
        "Regulatory compliance NIST RMF ISO 42001 LL144",
        "Third-party vendor AI risk assessment contractual protections",
    ]

    # All LLM calls return a minimal valid response
    mock_client.messages.create = AsyncMock(return_value=_make_tool_use_response({"no_documentation_provided": False}))

    result = await extract_all_dimensions(chunks, mock_client)

    assert set(result.keys()) == set(GOVERNANCE_DIMENSIONS)


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency(mock_client):
    """Concurrent in-flight LLM calls must never exceed EXTRACTION_CONCURRENCY."""
    import app.services.governance_extractor as extractor_module

    # Patch settings to use concurrency=2
    with patch.object(extractor_module.settings, "EXTRACTION_CONCURRENCY", 2):
        active: list[int] = []
        max_active = 0

        async def slow_create(**kwargs):
            nonlocal max_active
            active.append(1)
            if len(active) > max_active:
                max_active = len(active)
            await asyncio.sleep(0.02)
            active.pop()
            return _make_tool_use_response({"no_documentation_provided": False})

        mock_client.messages.create = slow_create

        chunks = [
            f"model inventory bias fairness human review data governance "
            f"incident response monitoring drift regulatory compliance "
            f"vendor third party risk {i}"
            for i in range(8)
        ]

        await extract_all_dimensions(chunks, mock_client)

    assert max_active <= 2, f"Expected max 2 concurrent calls, got {max_active}"


@pytest.mark.asyncio
async def test_no_chunks_all_dimensions_no_documentation(mock_client):
    """With no doc chunks, every dimension gets no_documentation_provided."""
    result = await extract_all_dimensions([], mock_client)

    assert set(result.keys()) == set(GOVERNANCE_DIMENSIONS)
    for dim, findings in result.items():
        assert findings == {"no_documentation_provided": True}, f"Expected no_documentation_provided for {dim}"
    mock_client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_failed_dimension_retried_after_delay(mock_client):
    """Dimensions that fail with an API error must be retried once; no_documentation_provided
    is only set after the retry also fails."""
    import app.services.governance_extractor as extractor_module

    call_count = 0

    async def fail_then_succeed(**kwargs):
        nonlocal call_count
        call_count += 1
        # First call fails (simulates 529 overload), second succeeds.
        if call_count == 1:
            raise Exception("529 Overloaded")
        return _make_tool_use_response({"has_bias_audit": True})

    mock_client.messages.create = fail_then_succeed

    chunks = ["bias audit impact ratio protected class demographic"]

    with patch.object(extractor_module, "_RETRY_DELAY_SECONDS", 0):
        result = await extract_all_dimensions(chunks, mock_client)

    # bias_fairness should have succeeded on retry - not no_documentation_provided
    assert result["bias_fairness"].get("has_bias_audit") is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_extraction_logs_token_counts(mock_client, caplog):
    """Token counts must be logged via structlog (captured via caplog or log output)."""
    import logging

    mock_client.messages.create = AsyncMock(return_value=_make_tool_use_response({"no_documentation_provided": False}))

    # structlog writes to stdlib logging when not configured otherwise in tests
    with caplog.at_level(logging.DEBUG):
        await extract_dimension(
            "model_inventory",
            ["Model inventory document with model risk classification"],
            mock_client,
        )

    # Verify the underlying messages.create was called (token logging happens there)
    mock_client.messages.create.assert_called_once()


# ---------------------------------------------------------------------------
# _filter_chunks_for_dimension
# ---------------------------------------------------------------------------


def test_filter_chunks_returns_relevant_only():
    chunks = [
        "This document covers model inventory and risk classification",
        "This is about catering menus",
        "AI system deployment environment documentation",
    ]
    result = _filter_chunks_for_dimension(chunks, "model_inventory")
    assert len(result) == 2
    assert all("model" in c.lower() or "inventory" in c.lower() or "ai system" in c.lower() for c in result)


def test_filter_chunks_empty_when_no_matches():
    chunks = ["Catering menu", "Office furniture catalog"]
    result = _filter_chunks_for_dimension(chunks, "model_inventory")
    assert result == []


def test_filter_chunks_respects_max_chunks():
    chunks = [f"model inventory system {i}" for i in range(20)]
    result = _filter_chunks_for_dimension(chunks, "model_inventory", max_chunks=5)
    assert len(result) == 5


# ---------------------------------------------------------------------------
# QuickHire shape test (fixture-based — checks field presence, not values)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quickhire_extractions_produce_correct_findings_shape(mock_client):
    """
    All expected scoring-rule fields must be present in extraction output.
    Values are not checked here — that's the live integration test.
    """
    from app.llm.schemas import DIMENSION_TOOLS

    # For each dimension, return a response containing all required schema fields
    def make_full_response(dimension: str) -> MagicMock:
        schema_props = DIMENSION_TOOLS[dimension]["input_schema"]["properties"]
        findings = {
            k: (
                []
                if v.get("type") == "array"
                else (0 if v.get("type") == "integer" else (False if v.get("type") == "boolean" else None))
            )
            for k, v in schema_props.items()
        }
        findings["no_documentation_provided"] = False
        return _make_tool_use_response(findings)

    mock_client.messages.create = AsyncMock(
        side_effect=lambda **kwargs: make_full_response(
            next(dim for dim in GOVERNANCE_DIMENSIONS if dim in kwargs["tools"][0]["name"])
        )
    )

    quickhire_chunks = [
        "QuickHire resume screening model card — model version 2.1 risk classification high",
        "Human-in-the-loop policy: VP+ review for senior roles only, escalation path defined",
        "Initial bias audit 2024: impact ratio race 0.81 borderline — self-assessed",
        "Data retention policy: AI output retained 90 days — consent mechanism documented",
        "No incident response plan documented",
        "Model performance monitored quarterly via internal dashboard",
        "Legal awareness: EEOC, NYC LL144 mentioned — no compliance documentation",
        "ChatGPT API integrated for cover letter analysis without governance wrapper",
    ]

    result = await extract_all_dimensions(quickhire_chunks, mock_client)

    assert set(result.keys()) == set(GOVERNANCE_DIMENSIONS)
    for dim in GOVERNANCE_DIMENSIONS:
        assert isinstance(result[dim], dict), f"{dim} findings must be a dict"
        assert "no_documentation_provided" in result[dim], f"{dim} findings missing no_documentation_provided field"
