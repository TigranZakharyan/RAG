from celery import Celery

from core.settings import settings
import workers

redis_url = (
    f"redis://"
    f"{settings.redis_host}:"
    f"{settings.redis_port}/0"
)


celery_app = Celery(
    "fastapi_ingestion",
    broker=redis_url,
    backend=redis_url,
)

celery_app.autodiscover_tasks(["workers"])

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    timezone="UTC",
    enable_utc=True,

    task_track_started=True,

    worker_prefetch_multiplier=1,

    task_acks_late=True,

    task_reject_on_worker_lost=True,
)
