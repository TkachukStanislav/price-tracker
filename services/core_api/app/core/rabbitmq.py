import logging
from typing import Any

import aio_pika
from aio_pika import RobustConnection

from app.core.config import settings
from app.core.messaging import build_message, declare_queue_with_retry

logger = logging.getLogger(__name__)


class RabbitMQClient:
    def __init__(self) -> None:
        self.connection: RobustConnection | None = None

    async def connect(self) -> None:
        """Створює стійке з'єднання (RobustConnection).

        Якщо зв'язок з брокером зникне, клієнт сам буде намагатися
        перепідключитися у фоні.
        """
        if not self.connection or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            logger.info("Успішно підключено до RabbitMQ")

    async def close(self) -> None:
        """Коректно закриває з'єднання під час зупинки FastAPI."""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("З'єднання з RabbitMQ закрито")

    async def publish_message(self, queue_name: str, payload: dict[str, Any]) -> None:
        """Публікує JSON-повідомлення у вказану чергу."""
        if not self.connection or self.connection.is_closed:
            await self.connect()

        async with self.connection.channel() as channel:
            # Черги durable, повідомлення PERSISTENT: переживуть рестарт RabbitMQ.
            # Аргументи черги (retry/DLQ) мають збігатися зі споживачем
            queue = await declare_queue_with_retry(channel, queue_name)
            await channel.default_exchange.publish(
                build_message(payload), routing_key=queue.name
            )
            logger.info(f"Завдання надіслано в чергу '{queue_name}': {payload}")


# Створюємо глобальний інстанс (Singleton)
rabbitmq_client = RabbitMQClient()
