from typing import Annotated

import structlog
from fastapi import APIRouter, Query

from app.schemas.signal import SignalSearchResponse
from app.services.external_signals import search_signals

log = structlog.get_logger()

router = APIRouter(tags=["signals"])


@router.get("/signals/search", response_model=list[SignalSearchResponse])
async def search_external_signals(
    company: Annotated[str, Query(min_length=2, max_length=200, description="Company name to search signals for")],
    signal_types: list[str] | None = Query(
        None,
        description="Filter results to specific signal types (e.g. regulatory_action, news, incident, litigation).",
    ),
    severity: str | None = Query(
        None,
        description="Filter results to a specific severity level (critical, warning, info).",
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results to return."),
) -> list[SignalSearchResponse]:
    """
    Search for external signals (news, regulatory actions, incidents) about a company.

    Fetches recent news via NewsAPI and classifies each article using Claude.
    Results are not persisted; use the pipeline to store signals for an assessment.
    """
    log.info("signals.search", company=company, signal_types=signal_types, severity=severity, limit=limit)
    results = await search_signals(company)

    filtered = [
        SignalSearchResponse(
            signal_type=r.signal_type,
            source=r.source,
            title=r.title,
            summary=r.summary,
            severity=r.severity,
            url=r.url,
        )
        for r in results
        if (not signal_types or r.signal_type in signal_types) and (not severity or r.severity == severity)
    ]
    return filtered[:limit]
