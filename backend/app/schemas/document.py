from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentCreate(BaseModel):
    assessment_id: UUID
    filename: str
    s3_key: str | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assessment_id: UUID
    filename: str
    s3_key: str | None = None
    doc_type: str | None = None
    status: str
    page_count: int | None = None
    word_count: int | None = None
    doc_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime
