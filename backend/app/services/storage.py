"""
S3 storage service.

Uses boto3 with run_in_executor for async compat — aiobotocore requires a
separate event-loop-aware session setup that adds complexity without meaningful
throughput gains at this scale. boto3 + executor keeps things simple and testable.

All methods raise StorageError on S3 failures so callers don't need to
import botocore exceptions directly.
"""
import asyncio
from functools import partial

import boto3
import structlog
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

log = structlog.get_logger()


class StorageError(Exception):
    """Raised when an S3 operation fails."""


def _get_client() -> "boto3.client":  # type: ignore[name-defined]
    kwargs: dict = {"region_name": settings.AWS_REGION}
    if settings.AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    if settings.S3_ENDPOINT_URL:
        # Point at local MinIO (or any S3-compatible endpoint)
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


async def generate_upload_url(key: str, content_type: str) -> str:
    """
    Return a presigned PUT URL for direct client-side upload.
    Expires in 15 minutes.
    """
    loop = asyncio.get_event_loop()
    try:
        url: str = await loop.run_in_executor(
            None,
            partial(
                _get_client().generate_presigned_url,
                "put_object",
                Params={
                    "Bucket": settings.S3_BUCKET_NAME,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=900,
            ),
        )
        log.info("storage.upload_url_generated", key=key)
        return url
    except (BotoCoreError, ClientError) as exc:
        log.error("storage.upload_url_failed", key=key, error=str(exc))
        raise StorageError(f"Failed to generate upload URL for {key}") from exc


async def generate_download_url(key: str) -> str:
    """
    Return a presigned GET URL for downloading a file.
    Expires in 1 hour.
    """
    loop = asyncio.get_event_loop()
    try:
        url: str = await loop.run_in_executor(
            None,
            partial(
                _get_client().generate_presigned_url,
                "get_object",
                Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
                ExpiresIn=3600,
            ),
        )
        log.info("storage.download_url_generated", key=key)
        return url
    except (BotoCoreError, ClientError) as exc:
        log.error("storage.download_url_failed", key=key, error=str(exc))
        raise StorageError(f"Failed to generate download URL for {key}") from exc


async def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    """
    Upload raw bytes directly to S3 (used for generated report PDFs).
    """
    loop = asyncio.get_event_loop()

    def _put() -> None:
        _get_client().put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    try:
        await loop.run_in_executor(None, _put)
        log.info("storage.upload_complete", key=key, bytes=len(data))
    except (BotoCoreError, ClientError) as exc:
        log.error("storage.upload_failed", key=key, error=str(exc))
        raise StorageError(f"Failed to upload {key}") from exc
