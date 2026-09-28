"""Слухає події оновлення цін від scraper_service і записує їх у БД.

Працює окремим процесом (не всередині API), див. docker-compose.yml:
    python -m app.services.price_consumer
"""

import asyncio
import logging
import signal
from datetime import UTC, datetime
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from prometheus_client import Counter, start_http_server
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.logging import setup_logging
from app.core.messaging import (
    PermanentMessageError,
    declare_queue_with_retry,
    handle_with_retry,
    parse_json,
)
from app.repositories.item import ItemRepository
from app.repositories.price_history import PriceHistoryRepository

logger = logging.getLogger(__name__)

METRICS_PORT = 9100
PRICE_UPDATES = Counter(
    "price_updates_total",
    "Оброблені події оновлення ціни",
    # updated | stale (подія старіша або дублікат) | item_not_found
    ["result"],
)


async def apply_price_update(session: AsyncSession, payload: dict[str, Any]) -> str:
    """Записує ціну з події в БД. Ідемпотентно: повтор тієї ж події нічого не змінить."""
    try:
        item_id = int(payload["item_id"])
        price = float(payload["current_price"])
        checked_at = (
            datetime.fromisoformat(payload["checked_at"])
            if payload.get("checked_at")
            else datetime.now(UTC)
        )
    except (KeyError, TypeError, ValueError) as e:
        raise PermanentMessageError(f"Некоректна подія оновлення ціни: {e}") from e

    repo = ItemRepository(session)
    if await repo.update_price_if_newer(item_id, price, checked_at):
        # Та сама транзакція: або оновлено і ціну, і історію, або нічого
        await PriceHistoryRepository(session).add_if_changed(item_id, price, checked_at)
        await session.commit()
        return "updated"
    await session.rollback()
    if await repo.get_by_id(item_id) is None:
        return "item_not_found"
    return "stale"


class PriceUpdateConsumer:
    def __init__(self) -> None:
        self.connection: aio_pika.abc.AbstractRobustConnection | None = None
        self.channel: AbstractChannel | None = None

    async def _handle(self, message: AbstractIncomingMessage) -> None:
        payload = parse_json(message)
        async with async_session_maker() as session:
            result = await apply_price_update(session, payload)
        PRICE_UPDATES.labels(result).inc()
        logger.info("Товар #%s: %s", payload.get("item_id"), result)

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        await handle_with_retry(
            message, self.channel, settings.PRICE_UPDATED_QUEUE_NAME, self._handle
        )

    async def start(self) -> None:
        """Підключається до RabbitMQ і починає слухати чергу (не блокує)."""
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)
        queue = await declare_queue_with_retry(
            self.channel, settings.PRICE_UPDATED_QUEUE_NAME
        )
        await queue.consume(self.process_message)
        logger.info(
            "Слухач оновлення цін запущено на черзі '%s'",
            settings.PRICE_UPDATED_QUEUE_NAME,
        )

    async def stop(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()


price_update_consumer = PriceUpdateConsumer()


async def main() -> None:
    setup_logging("price_consumer", settings.LOG_FORMAT, settings.LOG_LEVEL)
    # docker stop надсилає SIGTERM: коректно закриваємо з'єднання
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    # Окремий процес без FastAPI, тому метрики віддає вбудований HTTP-сервер
    start_http_server(METRICS_PORT)
    await price_update_consumer.start()
    await stop_event.wait()
    await price_update_consumer.stop()
    logger.info("Слухач оновлення цін зупинено")


if __name__ == "__main__":
    asyncio.run(main())
