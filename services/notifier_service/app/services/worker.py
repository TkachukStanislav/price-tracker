import asyncio
import json
import logging
import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from prometheus_client import Counter

from app.core.config import settings

logger = logging.getLogger(__name__)

NOTIFICATIONS_SENT = Counter(
    "notifications_sent_total",
    "Надіслані сповіщення про зниження ціни",
)


class NotificationWorker:
    def __init__(self) -> None:
        self.connection: aio_pika.RobustConnection | None = None

    async def send_notification(self, payload: dict) -> None:
        """Симулює відправку сповіщення (Email / Telegram / Webhook)."""
        item_id = payload.get("item_id")
        owner_id = payload.get("owner_id")
        current_price = payload.get("current_price")
        target_price = payload.get("target_price")
        url = payload.get("ticker_or_url")

        # Форматуємо текст сповіщення
        message_text = (
            f"🚨 ЗНИЖЕННЯ ЦІНИ! 🚨\n"
            f"Користувач ID: {owner_id}\n"
            f"Товар ID: {item_id}\n"
            f"Посилання: {url}\n"
            f"Бажана ціна: {target_price} | Поточна ціна: {current_price}!"
        )

        logger.info("\n" + "=" * 50 + f"\n{message_text}\n" + "=" * 50)
        NOTIFICATIONS_SENT.inc()

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        """Обробляє повідомлення з черги сповіщень."""
        async with message.process():
            payload = json.loads(message.body.decode("utf-8"))
            await self.send_notification(payload)

    async def start(self) -> None:
        """Запуск прослуховування черги сповіщень."""
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await self.connection.channel()
        await channel.set_qos(prefetch_count=10)

        queue = await channel.declare_queue(
            settings.NOTIFIER_QUEUE_NAME,
            durable=True,
        )

        logger.info(
            f"Воркер сповіщень запущено. Слухаємо чергу: '{settings.NOTIFIER_QUEUE_NAME}'"
        )
        await queue.consume(self.process_message)

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()


notification_worker = NotificationWorker()
