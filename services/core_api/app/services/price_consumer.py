"""Слухає події оновлення цін від scraper_service і записує їх у БД.

Працює окремим процесом (не всередині API), див. docker-compose.yml:
    python -m app.services.price_consumer
"""

import asyncio
import json
import logging
import signal

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.core.config import settings
from app.core.database import async_session_maker
from app.repositories.item import ItemRepository

logger = logging.getLogger(__name__)


class PriceUpdateConsumer:
    def __init__(self) -> None:
        self.connection: aio_pika.abc.AbstractRobustConnection | None = None

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process():
            payload = json.loads(message.body.decode("utf-8"))
            item_id = payload.get("item_id")
            current_price = payload.get("current_price")

            if not item_id or current_price is None:
                return

            async with async_session_maker() as session:
                item_repo = ItemRepository(session)
                item = await item_repo.get_by_id(item_id)
                if item:
                    await item_repo.update(item, current_price=current_price)
                    logger.info(
                        "Товар #%s отримав current_price = %s", item_id, current_price
                    )

    async def start(self) -> None:
        """Підключається до RabbitMQ і починає слухати чергу (не блокує)."""
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await self.connection.channel()
        queue = await channel.declare_queue(
            settings.PRICE_UPDATED_QUEUE_NAME,
            durable=True,
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # docker stop надсилає SIGTERM: коректно закриваємо з'єднання
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await price_update_consumer.start()
    await stop_event.wait()
    await price_update_consumer.stop()
    logger.info("Слухач оновлення цін зупинено")


if __name__ == "__main__":
    asyncio.run(main())
