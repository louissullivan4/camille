from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExternalSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assessment_id: UUID
    signal_type: str
    source: str
    title: str
    summary: str | None = None
    severity: str
    url: str | None = None
    discovered_at: datetime


class SignalSearchRequest(BaseModel):
    company: str


class SignalSearchResponse(BaseModel):
    signal_type: str
    source: str
    title: str
    summary: str
    severity: str
    url: str | None = None
