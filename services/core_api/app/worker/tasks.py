import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.rabbitmq import RabbitMQClient
from app.services.price_checks import dispatch_price_checks
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _dispatch_price_checks() -> int:
    # Celery-задача синхронна, тому кожен запуск — новий event loop (asyncio.run).
    # Пул з'єднань прив'язаний до loop, у якому створений, тому тут окремий
    # engine без пулу і власне з'єднання з RabbitMQ, які закриваються в кінці.
    engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    rabbitmq = RabbitMQClient()
    try:
        await rabbitmq.connect()
        async with session_maker() as session:
            return await dispatch_price_checks(session, rabbitmq.publish_message)
    finally:
        await rabbitmq.close()
        await engine.dispose()


@celery_app.task(name="price_checks.dispatch")
def dispatch_price_checks_task() -> int:
    """Ставить усі товари на перевірку ціни. Запускається Celery beat за розкладом."""
    count = asyncio.run(_dispatch_price_checks())
    logger.info("Поставлено на перевірку ціни товарів: %d", count)
    return count
