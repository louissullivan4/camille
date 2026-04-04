"""
External signals service: fetches news about a company, classifies each article
using Claude, and persists relevant signals to the database.

Handles missing NEWS_API_KEY gracefully by returning an empty list.
"""

import uuid
from dataclasses import dataclass

import httpx
import structlog
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.client import call_tool_use, get_anthropic_client
from app.models.external_signal import ExternalSignal

log = structlog.get_logger()

_CLASSIFY_SIGNAL_TOOL: dict = {
    "name": "classify_signal",
    "description": "Classify a news article's relevance and severity for AI liability underwriting.",
    "input_schema": {
        "type": "object",
        "properties": {
            "relevant": {
                "type": "boolean",
                "description": (
                    "True if this article is specifically about this company's AI systems, practices, or incidents."
                ),
            },
            "signal_type": {
                "type": "string",
                "enum": ["litigation", "regulatory_action", "media_sentiment", "incident"],
                "description": (
                    "Type of signal: litigation (lawsuits), regulatory_action (enforcement),"
                    " media_sentiment (press coverage), incident (AI failure/harm)."
                ),
            },
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": (
                    "critical: active lawsuit or enforcement underway, confirmed harm. "
                    "high: formal complaint or government inquiry opened. "
                    "medium: negative press, disclosed vulnerability. "
                    "low: minor commentary or unverified claim."
                ),
            },
            "summary": {
                "type": "string",
                "description": "1-2 sentence summary of the signal's relevance to AI liability risk.",
            },
        },
        "required": ["relevant", "signal_type", "severity", "summary"],
    },
}

_CLASSIFY_SYSTEM_PROMPT = """\
You are an AI liability underwriting analyst reviewing news articles about a company.

Determine whether an article is relevant to AI liability risk for this specific company.
Only mark relevant=true if the article discusses this company's AI systems, practices,
or AI-related incidents - not general industry news.

Signal types:
- litigation: lawsuits, legal claims, court proceedings related to AI
- regulatory_action: government enforcement, fines, investigations, compliance orders
- media_sentiment: press coverage of AI practices (bias, safety, ethics concerns)
- incident: reported AI failures, harms, outages, or unintended consequences

Severity:
- critical: active lawsuit filed, enforcement action underway, confirmed AI-caused harm
- high: formal complaint, government inquiry opened, credible allegation of harm
- medium: negative press coverage, disclosed vulnerability, watchdog concern
- low: minor commentary, general criticism, unverified claim
"""


@dataclass
class SignalResult:
    signal_type: str
    source: str
    title: str
    summary: str
    severity: str
    url: str | None


async def _fetch_news_articles(company_name: str) -> list[dict]:
    """Fetch recent news articles about a company from NewsAPI.

    Returns empty list if NEWS_API_KEY is not configured or on any HTTP error.
    """
    if not settings.NEWS_API_KEY:
        log.info("external_signals.news_api_key_not_configured")
        return []

    params = {
        "q": f'"{company_name}" AI',
        "sortBy": "publishedAt",
        "pageSize": 10,
        "language": "en",
        "apiKey": settings.NEWS_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.get("https://newsapi.org/v2/everything", params=params)
            resp.raise_for_status()
            articles: list[dict] = resp.json().get("articles", [])
            log.info("external_signals.news_fetched", company=company_name, count=len(articles))
            return articles
    except httpx.HTTPError as exc:
        log.warning("external_signals.news_fetch_failed", company=company_name, error=str(exc))
        return []


async def _classify_article(article: dict, client: AsyncAnthropic) -> dict | None:
    """Use Claude to classify a news article for AI liability relevance and severity.

    Returns None if the article is not relevant, or if classification fails.
    """
    title = article.get("title") or ""
    description = article.get("description") or ""
    content = article.get("content") or ""
    text = f"Title: {title}\n\nDescription: {description}\n\n{content}"

    try:
        result = await call_tool_use(
            client=client,
            model=settings.LLM_CLASSIFICATION_MODEL,
            system_prompt=_CLASSIFY_SYSTEM_PROMPT,
            user_message=text[:3000],
            tool_schema=_CLASSIFY_SIGNAL_TOOL,
            max_tokens=512,
        )
    except Exception as exc:
        log.warning("external_signals.classify_failed", title=title, error=str(exc))
        return None

    if not result.get("relevant"):
        return None

    return {
        "signal_type": result["signal_type"],
        "severity": result["severity"],
        "summary": result["summary"],
        "title": title,
        "source": (article.get("source") or {}).get("name") or "Unknown",
        "url": article.get("url"),
    }


async def gather_signals(
    company_name: str,
    assessment_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict]:
    """Fetch, classify, and persist external signals for a company.

    Called by the pipeline. Stores ExternalSignal rows linked to the assessment.
    Returns the list of persisted signal dicts.
    """
    bound_log = log.bind(company=company_name, assessment_id=str(assessment_id))
    bound_log.info("external_signals.gather.start")

    articles = await _fetch_news_articles(company_name)
    if not articles:
        bound_log.info("external_signals.gather.no_articles")
        return []

    client = get_anthropic_client()
    results: list[dict] = []

    for article in articles:
        classified = await _classify_article(article, client)
        if classified is None:
            continue

        signal = ExternalSignal(
            assessment_id=assessment_id,
            signal_type=classified["signal_type"],
            source=classified["source"],
            title=classified["title"],
            summary=classified["summary"],
            severity=classified["severity"],
            url=classified["url"],
        )
        db.add(signal)
        results.append(classified)

    await db.commit()
    bound_log.info("external_signals.gather.complete", signals_stored=len(results))
    return results


async def search_signals(company_name: str) -> list[SignalResult]:
    """Fetch and classify external signals without persisting to the database.

    Used by the search endpoint for ad-hoc underwriter queries.
    """
    log.info("external_signals.search.start", company=company_name)
    articles = await _fetch_news_articles(company_name)
    if not articles:
        return []

    client = get_anthropic_client()
    results: list[SignalResult] = []

    for article in articles:
        classified = await _classify_article(article, client)
        if classified is None:
            continue
        results.append(
            SignalResult(
                signal_type=classified["signal_type"],
                source=classified["source"],
                title=classified["title"],
                summary=classified["summary"],
                severity=classified["severity"],
                url=classified["url"],
            )
        )

    log.info("external_signals.search.complete", company=company_name, count=len(results))
    return results
