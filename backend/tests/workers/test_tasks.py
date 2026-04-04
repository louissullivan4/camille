"""
Tests for app/workers/tasks.py.

process_document_task and run_pipeline_task each open their own
AsyncSessionLocal session. In tests we patch AsyncSessionLocal with a
context manager that yields the test fixture's db session so changes
are visible to the test without a cross-DB lookup.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.document import Document
from app.models.organization import Organization
from app.workers.tasks import process_document_task, run_pipeline_task


async def _make_document(db: AsyncSession) -> tuple[Organization, Assessment, Document]:
    """Persist a minimal org + assessment + document and commit."""
    org = Organization(name="TasksOrg", slug=f"tasks-org-{uuid4().hex[:8]}")
    db.add(org)
    await db.flush()

    assessment = Assessment(organization_id=org.id, status="processing")
    db.add(assessment)
    await db.flush()

    doc = Document(
        assessment_id=assessment.id,
        filename="policy.txt",
        status="pending",
    )
    db.add(doc)
    await db.commit()
    return org, assessment, doc


def _make_session_factory(db: AsyncSession):
    """Return a callable that acts like AsyncSessionLocal but yields the test db."""
    @asynccontextmanager
    async def _factory():
        yield db
    return _factory


# ── process_document_task ────────────────────────────────────────────────────

async def test_process_document_task_success(db: AsyncSession) -> None:
    """Happy path: task extracts text, classifies, persists status='processed'."""
    _, _, doc = await _make_document(db)
    doc_id = doc.id

    mock_classification = MagicMock(
        doc_type="hitl_policy",
        confidence=0.9,
        reasoning="looks like HITL",
    )

    with (
        patch("app.workers.tasks.AsyncSessionLocal", _make_session_factory(db)),
        patch("app.workers.tasks.classify_document", new_callable=AsyncMock, return_value=mock_classification),
        patch("app.workers.tasks.get_anthropic_client", return_value=MagicMock()),
    ):
        await process_document_task(doc_id, b"HITL policy text about review processes.", "policy.txt")

    result = await db.execute(select(Document).where(Document.id == doc_id))
    updated = result.scalar_one()
    assert updated.status == "processed"
    assert updated.doc_type == "hitl_policy"
    assert updated.raw_text is not None and len(updated.raw_text) > 0


async def test_process_document_task_handles_exception(db: AsyncSession) -> None:
    """When classify_document raises, task catches error, sets status='failed', does not propagate."""
    _, _, doc = await _make_document(db)
    doc_id = doc.id

    with (
        patch("app.workers.tasks.AsyncSessionLocal", _make_session_factory(db)),
        patch("app.workers.tasks.classify_document", new_callable=AsyncMock, side_effect=RuntimeError("LLM exploded")),
        patch("app.workers.tasks.get_anthropic_client", return_value=MagicMock()),
    ):
        await process_document_task(doc_id, b"some bytes", "policy.txt")

    result = await db.execute(select(Document).where(Document.id == doc_id))
    updated = result.scalar_one()
    assert updated.status == "failed"


# ── run_pipeline_task ────────────────────────────────────────────────────────

async def test_run_pipeline_task_delegates_to_pipeline(db: AsyncSession) -> None:
    """run_pipeline_task must call run_assessment_pipeline with the assessment_id."""
    assessment_id = uuid4()

    with (
        patch("app.workers.tasks.AsyncSessionLocal", _make_session_factory(db)),
        patch("app.workers.tasks.run_assessment_pipeline", new_callable=AsyncMock) as mock_pipeline,
    ):
        await run_pipeline_task(assessment_id)

    mock_pipeline.assert_called_once()
    assert mock_pipeline.call_args.args[0] == assessment_id
