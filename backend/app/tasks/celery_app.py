from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "legalmetro",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 min hard limit for OCR/AI extraction
    worker_prefetch_multiplier=1,
    imports=["app.tasks.scan_pipeline"],
)


@celery_app.task(name="ping")
def ping_task() -> str:
    return "pong"
