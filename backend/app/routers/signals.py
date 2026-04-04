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
) -> list[SignalSearchResponse]:
    """
    Search for external signals (news, regulatory actions, incidents) about a company.

    Fetches recent news via NewsAPI and classifies each article using Claude.
    Results are not persisted; use the pipeline to store signals for an assessment.
    """
    log.info("signals.search", company=company)
    results = await search_signals(company)
    return [
        SignalSearchResponse(
            signal_type=r.signal_type,
            source=r.source,
            title=r.title,
            summary=r.summary,
            severity=r.severity,
            url=r.url,
        )
        for r in results
    ]
