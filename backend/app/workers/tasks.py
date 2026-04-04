"""
Thin task wrappers for background execution.

Each task creates its own DB session so it can run outside the request lifecycle.
These are called via asyncio.create_task() from routers.
"""
import uuid

import structlog
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.llm.client import get_anthropic_client
from app.models.document import Document
from app.services.document_classifier import classify_document
from app.services.document_processor import chunk_text, extract_text_from_file
from app.workers.pipeline import run_assessment_pipeline

log = structlog.get_logger()


async def process_document_task(
    doc_id: uuid.UUID,
    raw_bytes: bytes,
    filename: str,
) -> None:
    """
    Extract text, classify document type, store results in DB.
    Called as a background task after document upload.
    """
    async with AsyncSessionLocal() as db:
        try:
            text = extract_text_from_file(raw_bytes, filename)
            chunks = chunk_text(text, chunk_size=1000, overlap=200)

            client = get_anthropic_client()
            classification = await classify_document(text[:4000], client)

            result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.raw_text = text
                doc.doc_type = classification.doc_type
                doc.word_count = len(text.split())
                doc.doc_metadata = {
                    "confidence": classification.confidence,
                    "reasoning": classification.reasoning,
                    "chunk_count": len(chunks),
                }
                doc.status = "processed"
                await db.commit()
                log.info(
                    "task.document_processed",
                    doc_id=str(doc_id),
                    doc_type=classification.doc_type,
                )
        except Exception as exc:
            log.error("task.document_failed", doc_id=str(doc_id), error=str(exc))
            try:
                result = await db.execute(select(Document).where(Document.id == doc_id))
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = "failed"
                    await db.commit()
            except Exception:
                pass


async def run_pipeline_task(assessment_id: uuid.UUID) -> None:
    """
    Run the full assessment pipeline in a background task with its own DB session.
    """
    async with AsyncSessionLocal() as db:
        await run_assessment_pipeline(assessment_id, db)
