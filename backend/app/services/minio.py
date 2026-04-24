"""MinIO (S3-compatible) client wrapper."""
from __future__ import annotations

import asyncio
from functools import lru_cache
from io import BytesIO
from typing import BinaryIO

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _client():
    from minio import Minio

    s = get_settings()
    return Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=s.minio_secure,
    )


async def ensure_bucket() -> None:
    s = get_settings()

    def _sync():
        c = _client()
        if not c.bucket_exists(s.minio_bucket):
            c.make_bucket(s.minio_bucket)

    await asyncio.to_thread(_sync)


async def put_object(
    key: str, data: bytes | BinaryIO, size: int | None = None, content_type: str = "application/octet-stream"
) -> str:
    s = get_settings()
    payload = data if not isinstance(data, bytes) else BytesIO(data)
    length = size if size is not None else (len(data) if isinstance(data, bytes) else -1)

    def _sync():
        c = _client()
        c.put_object(s.minio_bucket, key, payload, length=length, content_type=content_type)
        return f"s3://{s.minio_bucket}/{key}"

    return await asyncio.to_thread(_sync)


async def get_object(key: str) -> bytes:
    s = get_settings()

    def _sync() -> bytes:
        c = _client()
        resp = c.get_object(s.minio_bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    return await asyncio.to_thread(_sync)


async def presigned_url(key: str, expires_seconds: int = 3600) -> str:
    from datetime import timedelta

    s = get_settings()

    def _sync() -> str:
        return _client().presigned_get_object(
            s.minio_bucket, key, expires=timedelta(seconds=expires_seconds)
        )

    return await asyncio.to_thread(_sync)


async def healthcheck() -> bool:
    try:
        await ensure_bucket()
        return True
    except Exception:
        return False


__all__ = ["ensure_bucket", "get_object", "healthcheck", "presigned_url", "put_object"]
