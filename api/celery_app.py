from celery import Celery
from celery.schedules import crontab

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

# Configuração de tarefas agendadas
celery_app.conf.beat_schedule = {
    # Coleta diária de processos judiciais (todos os tribunais)
    "coleta-diaria-processos": {
        "task": "coleta.todos_tribunais",
        "schedule": crontab(hour=3, minute=0),  # 3h da manhã todo dia
        "options": {
            "expires": 3600 * 6,  # Expira em 6 horas se não executar
        },
    },
}

celery_app.autodiscover_tasks(["services"], force=True)

# Import tasks explicitly to ensure they're registered
import services.coleta_tasks  # noqa: F401, E402
