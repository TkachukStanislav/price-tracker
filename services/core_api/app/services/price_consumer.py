import asyncio
import json
import logging

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.core.config import settings
from app.core.database import async_session_maker
from app.repositories.item import ItemRepository

logger = logging.getLogger(__name__)


class PriceUpdateConsumer:
    def __init__(self) -> None:
        self.connection: aio_pika.RobustConnection | None = None

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process():
            payload = json.loads(message.body.decode("utf-8"))
            item_id = payload.get("item_id")
            current_price = payload.get("current_price")

            if not item_id or current_price is None:
                return

            # Створюємо власну асинхронну сесію до БД
            async with async_session_maker() as session:
                item_repo = ItemRepository(session)
                item = await item_repo.get_by_id(item_id)
                if item:
                    await item_repo.update(item, current_price=current_price)
                    logger.info(
                        f"[DB UPDATED] Товар #{item_id} отримав current_price = {current_price}"
                    )

    async def start(self) -> None:
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await self.connection.channel()
        queue = await channel.declare_queue(
            settings.PRICE_UPDATED_QUEUE_NAME,
            durable=True,
        )
        await queue.consume(self.process_message)
        logger.info(
            f"Слухач оновлення цін запущено на черзі: '{settings.PRICE_UPDATED_QUEUE_NAME}'"
        )

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()


price_update_consumer = PriceUpdateConsumer()
