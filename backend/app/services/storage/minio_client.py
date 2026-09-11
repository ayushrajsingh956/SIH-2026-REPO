import logging
from urllib.parse import urlsplit

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


def put_object_bytes(
    object_name: str,
    data: bytes,
    content_type: str,
    bucket_name: str | None = None,
) -> str:
    """Uploads bytes directly to MinIO with strict content-type enforcement.

    Returns the object name / key.
    """
    bucket = bucket_name or settings.MINIO_BUCKET
    ensure_bucket_exists(bucket)

    import io

    client = get_minio_client()
    data_stream = io.BytesIO(data)
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=data_stream,
        length=len(data),
        content_type=content_type,
    )
    logger.debug("Successfully uploaded %s to bucket %s (%d bytes)", object_name, bucket, len(data))
    return object_name


def get_object_bytes(object_name: str, bucket_name: str | None = None) -> bytes:
    """Retrieves object raw bytes from MinIO."""
    bucket = bucket_name or settings.MINIO_BUCKET
    client = get_minio_client()

    response = client.get_object(bucket_name=bucket, object_name=object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def presign_get_url(
    object_name: str,
    bucket_name: str | None = None,
    expires_seconds: int = 3600,
) -> str:
    """Generates a presigned GET URL for client-side download/viewing.

    SigV4 signatures include the Host header, so the URL must be signed with
    the endpoint the CLIENT will use (MINIO_PUBLIC_ENDPOINT, defaulting to
    MINIO_ENDPOINT) — not the docker-internal one. Presigning is local
    signature computation; no connection to the endpoint is made, so the
    public host only needs to resolve from the browser.
    """
    from datetime import timedelta

    bucket = bucket_name or settings.MINIO_BUCKET
    public = settings.minio_public_endpoint
    if public and not public.startswith(("http://", "https://")):
        public = f"{'https' if settings.MINIO_SECURE else 'http'}://{public}"

    internal = settings.MINIO_ENDPOINT
    if not internal.startswith(("http://", "https://")):
        internal = f"{'https' if settings.MINIO_SECURE else 'http'}://{internal}"

    if public and urlsplit(public).netloc != urlsplit(internal).netloc:
        # region pinned so presigning never needs a GetBucketLocation round-trip
        # to the (client-only, possibly unreachable) public endpoint.
        client = Minio(
            urlsplit(public).netloc,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=public.startswith("https://"),
            region="us-east-1",
        )
    else:
        client = get_minio_client()

    return client.presigned_get_object(
        bucket_name=bucket,
        object_name=object_name,
        expires=timedelta(seconds=expires_seconds),
    )
