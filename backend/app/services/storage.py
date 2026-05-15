"""MinIO/S3-compatible object storage service."""

from __future__ import annotations

import io
import logging
from datetime import timedelta
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class StorageService:
    """Thin wrapper around MinIO client for image storage."""

    _instance: Optional["StorageService"] = None

    def __init__(self):
        settings = get_settings()
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=settings.minio_use_ssl,
        )
        self._bucket = settings.minio_bucket
        self._ensure_bucket()

    @classmethod
    def get_instance(cls) -> "StorageService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
                logger.info("Created bucket: %s", self._bucket)
        except S3Error as e:
            logger.warning("Could not ensure bucket: %s", e)

    def upload_bytes(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "image/png",
    ) -> str:
        """Upload raw bytes and return the object path."""
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return f"{self._bucket}/{object_name}"

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        """Generate a presigned GET URL."""
        try:
            return self._client.presigned_get_object(
                self._bucket, object_name, expires=timedelta(seconds=expires)
            )
        except S3Error:
            return ""

    def download_bytes(self, object_name: str) -> bytes:
        """Download object as bytes."""
        response = self._client.get_object(self._bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
