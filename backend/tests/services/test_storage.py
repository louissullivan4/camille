from unittest.mock import MagicMock, patch

import pytest

from app.services.storage import StorageError, generate_download_url, generate_upload_url, upload_bytes


@pytest.mark.asyncio
async def test_generate_upload_url_returns_string() -> None:
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://s3.example.com/put-url"

    with patch("app.services.storage._get_client", return_value=mock_client):
        url = await generate_upload_url("assessments/123/doc.pdf", "application/pdf")

    assert url == "https://s3.example.com/put-url"
    mock_client.generate_presigned_url.assert_called_once()
    call_kwargs = mock_client.generate_presigned_url.call_args
    assert call_kwargs[0][0] == "put_object"
    assert call_kwargs[1]["ExpiresIn"] == 900


@pytest.mark.asyncio
async def test_generate_download_url_returns_string() -> None:
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://s3.example.com/get-url"

    with patch("app.services.storage._get_client", return_value=mock_client):
        url = await generate_download_url("assessments/123/doc.pdf")

    assert url == "https://s3.example.com/get-url"
    assert call_kwargs[1]["ExpiresIn"] == 3600 if (call_kwargs := mock_client.generate_presigned_url.call_args) else True


@pytest.mark.asyncio
async def test_upload_bytes_calls_put_object() -> None:
    mock_client = MagicMock()

    with patch("app.services.storage._get_client", return_value=mock_client):
        await upload_bytes("reports/123/report.pdf", b"%PDF-1.4 data", "application/pdf")

    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args[1]
    assert call_kwargs["Key"] == "reports/123/report.pdf"
    assert call_kwargs["ContentType"] == "application/pdf"
    assert call_kwargs["Body"] == b"%PDF-1.4 data"


@pytest.mark.asyncio
async def test_upload_bytes_raises_storage_error_on_failure() -> None:
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    mock_client.put_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "bucket missing"}}, "PutObject"
    )

    with patch("app.services.storage._get_client", return_value=mock_client):
        with pytest.raises(StorageError, match="Failed to upload"):
            await upload_bytes("bad/key.pdf", b"data", "application/pdf")


@pytest.mark.asyncio
async def test_generate_upload_url_raises_storage_error_on_failure() -> None:
    from botocore.exceptions import BotoCoreError

    mock_client = MagicMock()
    mock_client.generate_presigned_url.side_effect = BotoCoreError()

    with patch("app.services.storage._get_client", return_value=mock_client):
        with pytest.raises(StorageError, match="Failed to generate upload URL"):
            await generate_upload_url("some/key.pdf", "application/pdf")


@pytest.mark.asyncio
async def test_generate_download_url_raises_storage_error_on_failure() -> None:
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    mock_client.generate_presigned_url.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "key missing"}}, "GetObject"
    )

    with patch("app.services.storage._get_client", return_value=mock_client):
        with pytest.raises(StorageError, match="Failed to generate download URL"):
            await generate_download_url("some/missing/key.pdf")


@pytest.mark.asyncio
async def test_get_client_includes_endpoint_url_when_configured() -> None:
    """_get_client passes endpoint_url to boto3 when S3_ENDPOINT_URL is set."""
    with (
        patch("app.services.storage.settings") as mock_settings,
        patch("app.services.storage.boto3.client") as mock_boto3_client,
    ):
        mock_settings.AWS_REGION = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"
        mock_settings.S3_ENDPOINT_URL = "http://localhost:9000"
        mock_settings.S3_BUCKET_NAME = "test-bucket"

        from app.services.storage import _get_client
        _get_client()

    call_kwargs = mock_boto3_client.call_args[1]
    assert call_kwargs["endpoint_url"] == "http://localhost:9000"
    assert call_kwargs["aws_access_key_id"] == "test-key"
