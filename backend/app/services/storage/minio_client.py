import logging

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


def check_minio_health() -> tuple[bool, str | None]:
    """Checks if MinIO server is reachable and accessible."""
    try:
        client = get_minio_client()
        # bucket_exists or list_buckets serves as health check
        client.bucket_exists(settings.MINIO_BUCKET)
        return True, None
    except Exception as exc:
        logger.warning("MinIO health check failed: %s", exc)
        return False, str(exc)


def ensure_bucket_exists(bucket_name: str | None = None) -> bool:
    bucket = bucket_name or settings.MINIO_BUCKET
    try:
        client = get_minio_client()
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("Created MinIO bucket: %s", bucket)
        return True
    except S3Error as err:
        logger.error("Failed to ensure MinIO bucket '%s': %s", bucket, err)
        return False
