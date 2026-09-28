"""Celery для фонових і запланованих задач core_api.

Запуск (див. docker-compose.yml):
    celery -A app.worker.celery_app worker   — виконує задачі (можна кілька)
    celery -A app.worker.celery_app beat     — розклад (рівно один екземпляр)
"""

from celery import Celery
from celery.signals import setup_logging as celery_setup_logging

from app.core.config import settings
from app.core.logging import setup_logging

celery_app = Celery(
    "core_api",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    timezone="UTC",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    task_time_limit=300,
    beat_schedule={
        "dispatch-price-checks": {
            "task": "price_checks.dispatch",
            "schedule": settings.PRICE_CHECK_INTERVAL_SECONDS,
            # Якщо воркер лежав, запуски не накопичуються: застарілий
            # (старший за один інтервал) просто відкидається
            "options": {"expires": settings.PRICE_CHECK_INTERVAL_SECONDS},
        },
    },
)


@celery_setup_logging.connect
def configure_logging(**kwargs) -> None:
    """Celery не чіпає логування сам, якщо є обробник цього сигналу."""
    setup_logging("celery", settings.LOG_FORMAT, settings.LOG_LEVEL)
