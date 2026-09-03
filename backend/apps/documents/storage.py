"""Object storage: put bytes, sign GET URLs. S3-compatible (MinIO locally). PROJECT_SPECS §12."""

from typing import Any

import boto3
from botocore.config import Config
from django.conf import settings

SIGNED_URL_TTL_SECONDS = 300


def _client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL or None,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or "unset",
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or "unset",
        region_name="ap-south-1",
        config=Config(signature_version="s3v4"),
    )


def put_object(key: str, data: bytes, content_type: str) -> None:
    _client().put_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key, Body=data, ContentType=content_type
    )


def get_object(key: str) -> bytes:
    body = _client().get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)["Body"]
    return bytes(body.read())


def signed_get_url(key: str, ttl: int = SIGNED_URL_TTL_SECONDS) -> str:
    """Presigned URL, computed locally — no network call."""
    url: str = _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key},
        ExpiresIn=ttl,
    )
    return url
