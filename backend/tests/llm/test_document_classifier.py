"""Tests for document_classifier.py — classify_document."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.document_classifier import DocumentClassification, classify_document


def _make_tool_use_response(input_dict: dict) -> MagicMock:
    """Build a mock Anthropic messages.create response with a tool_use block."""
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = input_dict

    usage = MagicMock()
    usage.input_tokens = 500
    usage.output_tokens = 100

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


@pytest.mark.asyncio
async def test_classifies_model_card_correctly(mock_client):
    mock_client.messages.create = AsyncMock(
        return_value=_make_tool_use_response(
            {
                "doc_type": "model_card",
                "confidence": 0.95,
                "relevant_dimensions": ["model_inventory", "bias_fairness"],
                "reasoning": "Document describes model architecture and training data.",
            }
        )
    )

    result = await classify_document("Model card text...", mock_client)

    assert isinstance(result, DocumentClassification)
    assert result.doc_type == "model_card"
    assert result.confidence == 0.95
    assert "model_inventory" in result.relevant_dimensions
    assert result.reasoning != ""


@pytest.mark.asyncio
async def test_classifies_bias_audit_correctly(mock_client):
    mock_client.messages.create = AsyncMock(
        return_value=_make_tool_use_response(
            {
                "doc_type": "bias_audit",
                "confidence": 0.90,
                "relevant_dimensions": ["bias_fairness"],
                "reasoning": "Document contains impact ratio analysis.",
            }
        )
    )

    result = await classify_document("Bias audit report...", mock_client)

    assert result.doc_type == "bias_audit"
    assert "bias_fairness" in result.relevant_dimensions


@pytest.mark.asyncio
async def test_unknown_doc_type_returned_for_irrelevant_text(mock_client):
    mock_client.messages.create = AsyncMock(
        return_value=_make_tool_use_response(
            {
                "doc_type": "unknown",
                "confidence": 0.30,
                "relevant_dimensions": [],
                "reasoning": "Document is a catering menu.",
            }
        )
    )

    result = await classify_document("Today's lunch menu: pizza, salad...", mock_client)

    assert result.doc_type == "unknown"
    assert result.relevant_dimensions == []


@pytest.mark.asyncio
async def test_classifies_hitl_policy_correctly(mock_client):
    mock_client.messages.create = AsyncMock(
        return_value=_make_tool_use_response(
            {
                "doc_type": "hitl_policy",
                "confidence": 0.88,
                "relevant_dimensions": ["human_oversight"],
                "reasoning": "Document describes human review process for AI decisions.",
            }
        )
    )

    result = await classify_document("Human review policy text...", mock_client)

    assert result.doc_type == "hitl_policy"
    assert "human_oversight" in result.relevant_dimensions


@pytest.mark.asyncio
async def test_long_text_is_truncated_before_classification(mock_client):
    """Classifier should truncate to ~3000 chars to keep costs down."""
    mock_client.messages.create = AsyncMock(
        return_value=_make_tool_use_response(
            {
                "doc_type": "model_card",
                "confidence": 0.80,
                "relevant_dimensions": ["model_inventory"],
                "reasoning": "Model card.",
            }
        )
    )

    long_text = "model card content " * 1000  # ~19000 chars
    await classify_document(long_text, mock_client)

    call_args = mock_client.messages.create.call_args
    user_message = call_args.kwargs["messages"][0]["content"]
    # The excerpt in the user message should be ≤3000 chars (plus the prompt prefix)
    assert len(user_message) < 4000
