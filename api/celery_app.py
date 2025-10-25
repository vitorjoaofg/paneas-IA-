from celery import Celery

from config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_stack",
    broker=settings.celery_broker_url,
    backend=settings.celery_backend_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_time_limit=settings.celery_task_time_limit,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    beat_scheduler="celery.beat:PersistentScheduler",
)

celery_app.autodiscover_tasks(["services"], force=True)
