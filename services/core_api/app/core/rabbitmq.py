import json
import logging
from typing import Any

import aio_pika
from aio_pika import Message, RobustConnection

from app.core.config import settings

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
            # durable=True означає, що черга переживе перезавантаження сервера RabbitMQ
            queue = await channel.declare_queue(queue_name, durable=True)

            # Перетворюємо словник у JSON-байти
            message_body = json.dumps(payload).encode("utf-8")

            # PERSISTENT вказує зберегти це повідомлення на диск, а не тільки в RAM
            message = Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )

            await channel.default_exchange.publish(message, routing_key=queue.name)
            logger.info(f"Завдання надіслано в чергу '{queue_name}': {payload}")


# Створюємо глобальний інстанс (Singleton)
rabbitmq_client = RabbitMQClient()
