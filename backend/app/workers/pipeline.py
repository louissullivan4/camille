"""
Assessment pipeline orchestrator.

Runs as a background asyncio task (not a separate process) — keeps things
simple while the app is single-instance. Move to Celery/ARQ when horizontal
scaling is needed.

Status transitions:
  pending → processing → extracting → scoring → generating_report → complete
  Any step failure → failed
"""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import get_anthropic_client
from app.models.assessment import Assessment
from app.models.document import Document
from app.services.document_processor import chunk_text, extract_text_from_file
from app.services.governance_extractor import extract_all_dimensions
from app.services.scoring_engine import score_assessment
from app.services.storage import StorageError

log = structlog.get_logger()


async def run_assessment_pipeline(
    assessment_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """
    Full pipeline: extract → score → generate report → complete.

    On any unhandled exception, sets status = "failed" and logs the error.
    The caller is responsible for providing a session; this function commits
    status updates but does not manage session lifecycle.
    """
    bound_log = log.bind(assessment_id=str(assessment_id))

    async def _set_status(status: str) -> None:
        result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
        a = result.scalar_one_or_none()
        if a:
            a.status = status
            await db.commit()

    try:
        # ── Step 1: Load and chunk all documents ────────────────────────────
        await _set_status("extracting")
        bound_log.info("pipeline.step1.loading_documents")

        docs_result = await db.execute(select(Document).where(Document.assessment_id == assessment_id))
        documents = docs_result.scalars().all()

        all_chunks: list[str] = []
        for doc in documents:
            raw_text = doc.raw_text or ""

            # raw_text is populated by process_document_task which runs concurrently
            # with the pipeline trigger. If it hasn't finished yet, fall back to
            # downloading the original bytes from S3 and extracting text here.
            if not raw_text and doc.s3_key:
                bound_log.info(
                    "pipeline.doc_fallback_s3_download",
                    doc_id=str(doc.id),
                    filename=doc.filename,
                )
                try:
                    import asyncio  # noqa: PLC0415

                    import boto3  # noqa: PLC0415

                    from app.config import settings  # noqa: PLC0415

                    def _download() -> bytes:
                        kwargs: dict = {
                            "region_name": settings.AWS_REGION,
                            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
                            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
                        }
                        if settings.S3_ENDPOINT_URL:
                            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
                        s3 = boto3.client("s3", **kwargs)
                        obj = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=doc.s3_key)
                        return obj["Body"].read()

                    loop = asyncio.get_event_loop()
                    raw_bytes = await loop.run_in_executor(None, _download)
                    raw_text = extract_text_from_file(raw_bytes, doc.filename or "")
                    # Persist so subsequent pipeline runs skip the S3 download
                    doc.raw_text = raw_text
                    await db.commit()
                except (StorageError, Exception) as exc:
                    bound_log.warning(
                        "pipeline.doc_s3_download_failed",
                        doc_id=str(doc.id),
                        error=str(exc),
                    )
                    continue

            if not raw_text:
                bound_log.warning("pipeline.doc_no_text", doc_id=str(doc.id))
                continue

            chunks = chunk_text(raw_text, chunk_size=1000, overlap=200)
            tagged = [f"[Source: {doc.filename}]\n{chunk}" for chunk in chunks]
            all_chunks.extend(tagged)

        bound_log.info("pipeline.step1.complete", total_chunks=len(all_chunks))

        # ── Step 2: Extract all governance dimensions via LLM ───────────────
        client = get_anthropic_client()
        findings = await extract_all_dimensions(all_chunks, client)
        bound_log.info("pipeline.step2.extraction_complete")

        # ── Step 3: Gather external signals (stub — Group 5 implements this) ─
        await _set_status("scoring")
        signals: list[dict] = []
        try:
            from app.services.external_signals import gather_signals  # noqa: PLC0415

            result_a = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
            assessment = result_a.scalar_one_or_none()
            if assessment:
                from app.models.organization import Organization  # noqa: PLC0415

                org_result = await db.execute(select(Organization).where(Organization.id == assessment.organization_id))
                org = org_result.scalar_one_or_none()
                if org:
                    signals = await gather_signals(org.name, db)  # noqa: F841
        except ImportError:
            bound_log.info("pipeline.step3.signals_not_available")

        # ── Step 4: Score ────────────────────────────────────────────────────
        result_b = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
        assessment = result_b.scalar_one_or_none()
        if not assessment:
            bound_log.error("pipeline.assessment_missing")
            return

        scored = score_assessment(findings, assessment.assessment_config)

        assessment.dimension_scores = {
            dim: {
                "score": ds.score,
                "max_score": ds.max_score,
                "flags": ds.flags,
            }
            for dim, ds in scored.dimension_scores.items()
        }
        assessment.overall_score = scored.overall_score
        assessment.risk_tier = scored.risk_tier
        assessment.flags = {"all_flags": scored.all_flags}
        await db.commit()
        bound_log.info(
            "pipeline.step4.scoring_complete",
            overall_score=scored.overall_score,
            risk_tier=scored.risk_tier,
        )

        # ── Step 5: Generate report ──────────────────────────────────────────
        await _set_status("generating_report")
        try:
            from app.services.report_generator import generate_report  # noqa: PLC0415

            report_key = await generate_report(assessment_id, db)
            assessment.report_url = report_key
            await db.commit()
            bound_log.info("pipeline.step5.report_complete", report_key=report_key)
        except ImportError:
            bound_log.info("pipeline.step5.report_generator_not_available")
        except Exception as exc:
            bound_log.warning("pipeline.step5.report_failed", error=str(exc))
            # Report failure is non-fatal — still mark complete

        # ── Done ─────────────────────────────────────────────────────────────
        await _set_status("complete")
        bound_log.info("pipeline.complete")

    except Exception as exc:
        bound_log.error("pipeline.failed", error=str(exc), exc_info=True)
        await _set_status("failed")
        raise
