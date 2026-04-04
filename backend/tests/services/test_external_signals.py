"""
Tests for app/services/external_signals.py.

All tests use mocked httpx and Anthropic clients - no real HTTP or LLM calls.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from app.models.assessment import Assessment
from app.models.external_signal import ExternalSignal
from app.models.organization import Organization
from app.services.external_signals import (
    SignalResult,
    _classify_article,
    _fetch_news_articles,
    gather_signals,
    search_signals,
)

# ── _fetch_news_articles ────────────────────────────────────────────────────


async def test_fetch_news_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns empty list when NEWS_API_KEY is not set."""
    monkeypatch.setattr("app.services.external_signals.settings.NEWS_API_KEY", "")
    result = await _fetch_news_articles("QuickHire")
    assert result == []


async def test_fetch_news_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns empty list on any HTTP error."""
    monkeypatch.setattr("app.services.external_signals.settings.NEWS_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock())

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_response)

    with patch("app.services.external_signals.httpx.AsyncClient", return_value=mock_http):
        result = await _fetch_news_articles("QuickHire")

    assert result == []


async def test_fetch_news_returns_articles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns article list on success."""
    monkeypatch.setattr("app.services.external_signals.settings.NEWS_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={
            "articles": [
                {
                    "title": "QuickHire AI sued",
                    "description": "Lawsuit over biased hiring",
                    "content": "...",
                    "source": {"name": "Reuters"},
                    "url": "https://example.com/1",
                }
            ]
        }
    )

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_response)

    with patch("app.services.external_signals.httpx.AsyncClient", return_value=mock_http):
        result = await _fetch_news_articles("QuickHire")

    assert len(result) == 1
    assert result[0]["title"] == "QuickHire AI sued"


# ── _classify_article ───────────────────────────────────────────────────────


async def test_classify_article_irrelevant() -> None:
    """Returns None when Claude marks article as not relevant."""
    mock_client = AsyncMock()
    article = {
        "title": "General AI industry trends",
        "description": "Overview of AI adoption",
        "content": "Long article about AI in general",
        "source": {"name": "TechCrunch"},
        "url": "https://example.com/2",
    }

    with patch(
        "app.services.external_signals.call_tool_use",
        return_value={
            "relevant": False,
            "signal_type": "media_sentiment",
            "severity": "low",
            "summary": "Not about this company",
        },
    ):
        result = await _classify_article(article, mock_client)

    assert result is None


async def test_classify_article_relevant_litigation() -> None:
    """Returns classified dict when article is relevant."""
    mock_client = AsyncMock()
    article = {
        "title": "QuickHire AI sued over biased resume screening",
        "description": "Lawsuit filed in NYC federal court",
        "content": "Plaintiffs allege...",
        "source": {"name": "Reuters"},
        "url": "https://example.com/3",
    }

    with patch(
        "app.services.external_signals.call_tool_use",
        return_value={
            "relevant": True,
            "signal_type": "litigation",
            "severity": "critical",
            "summary": "Active federal lawsuit over discriminatory AI hiring tool.",
        },
    ):
        result = await _classify_article(article, mock_client)

    assert result is not None
    assert result["signal_type"] == "litigation"
    assert result["severity"] == "critical"
    assert result["source"] == "Reuters"
    assert result["url"] == "https://example.com/3"
    assert "lawsuit" in result["summary"].lower()


async def test_classify_article_api_error_returns_none() -> None:
    """Returns None on Claude API error - does not raise."""
    mock_client = AsyncMock()
    article = {
        "title": "Some news",
        "description": "",
        "content": "",
        "source": {"name": "BBC"},
        "url": None,
    }

    with patch(
        "app.services.external_signals.call_tool_use",
        side_effect=Exception("API unavailable"),
    ):
        result = await _classify_article(article, mock_client)

    assert result is None


async def test_classify_article_missing_source() -> None:
    """Handles article with None source gracefully."""
    mock_client = AsyncMock()
    article = {
        "title": "AI incident report",
        "description": "System failure",
        "content": "Details...",
        "source": None,
        "url": "https://example.com/4",
    }

    with patch(
        "app.services.external_signals.call_tool_use",
        return_value={
            "relevant": True,
            "signal_type": "incident",
            "severity": "high",
            "summary": "Reported AI system failure.",
        },
    ):
        result = await _classify_article(article, mock_client)

    assert result is not None
    assert result["source"] == "Unknown"


# ── gather_signals ──────────────────────────────────────────────────────────


async def test_gather_signals_no_articles(db) -> None:
    """Returns empty list when no articles are fetched."""
    assessment_id = uuid.uuid4()

    with patch("app.services.external_signals._fetch_news_articles", return_value=[]):
        result = await gather_signals("QuickHire", assessment_id, db)

    assert result == []


async def test_gather_signals_persists_to_db(db) -> None:
    """Stores relevant signals in the DB linked to the assessment."""
    # Create org + assessment so the FK is satisfied
    org = Organization(name="QuickHire", slug="quickhire")
    db.add(org)
    await db.commit()
    await db.refresh(org)

    assessment = Assessment(
        organization_id=org.id,
        status="scoring",
        assessment_config={},
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    fake_articles = [
        {
            "title": "QuickHire AI bias lawsuit",
            "description": "Details",
            "content": "Full content",
            "source": {"name": "Reuters"},
            "url": "https://example.com/5",
        }
    ]
    fake_classified = {
        "signal_type": "litigation",
        "severity": "critical",
        "summary": "Active lawsuit over biased AI.",
        "title": "QuickHire AI bias lawsuit",
        "source": "Reuters",
        "url": "https://example.com/5",
    }

    with (
        patch("app.services.external_signals._fetch_news_articles", return_value=fake_articles),
        patch("app.services.external_signals._classify_article", return_value=fake_classified),
        patch("app.services.external_signals.get_anthropic_client", return_value=AsyncMock()),
    ):
        result = await gather_signals("QuickHire", assessment.id, db)

    assert len(result) == 1
    assert result[0]["signal_type"] == "litigation"

    # Verify DB row was created
    rows = (
        (await db.execute(select(ExternalSignal).where(ExternalSignal.assessment_id == assessment.id))).scalars().all()
    )
    assert len(rows) == 1
    assert rows[0].severity == "critical"
    assert rows[0].source == "Reuters"


async def test_gather_signals_skips_irrelevant(db) -> None:
    """Does not persist articles classified as irrelevant (None return)."""
    org = Organization(name="Acme Corp", slug="acme-corp")
    db.add(org)
    await db.commit()
    await db.refresh(org)

    assessment = Assessment(organization_id=org.id, status="scoring", assessment_config={})
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    fake_articles = [
        {"title": "Generic AI news", "description": "", "content": "", "source": {"name": "Tech"}, "url": None}
    ]

    with (
        patch("app.services.external_signals._fetch_news_articles", return_value=fake_articles),
        patch("app.services.external_signals._classify_article", return_value=None),
        patch("app.services.external_signals.get_anthropic_client", return_value=AsyncMock()),
    ):
        result = await gather_signals("Acme Corp", assessment.id, db)

    assert result == []
    rows = (await db.execute(select(ExternalSignal))).scalars().all()
    assert len(rows) == 0


# ── search_signals ──────────────────────────────────────────────────────────


async def test_search_signals_returns_results() -> None:
    """Returns SignalResult list without persisting."""
    fake_articles = [
        {
            "title": "QuickHire under EEOC investigation",
            "description": "Probe into hiring AI",
            "content": "...",
            "source": {"name": "WSJ"},
            "url": "https://example.com/6",
        }
    ]
    fake_classified = {
        "signal_type": "regulatory_action",
        "severity": "high",
        "summary": "EEOC opened investigation into AI hiring tool.",
        "title": "QuickHire under EEOC investigation",
        "source": "WSJ",
        "url": "https://example.com/6",
    }

    with (
        patch("app.services.external_signals._fetch_news_articles", return_value=fake_articles),
        patch("app.services.external_signals._classify_article", return_value=fake_classified),
        patch("app.services.external_signals.get_anthropic_client", return_value=AsyncMock()),
    ):
        result = await search_signals("QuickHire")

    assert len(result) == 1
    assert isinstance(result[0], SignalResult)
    assert result[0].signal_type == "regulatory_action"
    assert result[0].source == "WSJ"


async def test_search_signals_no_key() -> None:
    """Returns empty list when no API key is configured."""
    with patch("app.services.external_signals._fetch_news_articles", return_value=[]):
        result = await search_signals("QuickHire")

    assert result == []
