import logging
from typing import Any

import aio_pika
import redis.asyncio as aioredis
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from prometheus_client import Counter

from app.core.config import settings
from app.core.messaging import (
    declare_queue_with_retry,
    handle_with_retry,
    parse_json,
)

logger = logging.getLogger(__name__)

NOTIFICATIONS = Counter(
    "notifications_total",
    "Оброблені сповіщення про зниження ціни",
    # sent | duplicate (вже надсилали, пропущено)
    ["result"],
)


class NotificationWorker:
    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis
        self.connection: aio_pika.abc.AbstractRobustConnection | None = None
        self.channel: AbstractChannel | None = None

    async def send_notification(self, payload: dict[str, Any]) -> None:
        """Симулює відправку сповіщення (Email / Telegram / Webhook)."""
        message_text = (
            f"🚨 ЗНИЖЕННЯ ЦІНИ! 🚨\n"
            f"Користувач ID: {payload.get('owner_id')}\n"
            f"Товар ID: {payload.get('item_id')}\n"
            f"Посилання: {payload.get('ticker_or_url')}\n"
            f"Бажана ціна: {payload.get('target_price')} | "
            f"Поточна ціна: {payload.get('current_price')}!"
        )
        logger.info("\n" + "=" * 50 + f"\n{message_text}\n" + "=" * 50)

    async def notify_once(self, payload: dict[str, Any]) -> bool:
        """Надсилає сповіщення, якщо таке саме ще не надсилали. Повертає, чи надіслано.

        Ключ ідемпотентності — товар і ціна: повторна доставка того ж
        повідомлення і щохвилинні перевірки з незмінною ціною не дублюють
        сповіщення. SET NX атомарний, тож два воркери не надішлють його обидва.
        """
        key = f"notified:{payload.get('item_id')}:{payload.get('current_price')}"
        is_first = await self.redis.set(
            key, "1", nx=True, ex=settings.NOTIFICATION_DEDUP_TTL_SECONDS
        )
        if not is_first:
            NOTIFICATIONS.labels("duplicate").inc()
            return False

        try:
            await self.send_notification(payload)
        except Exception:
            # Не надіслали — знімаємо позначку, щоб повтор зміг надіслати
            await self.redis.delete(key)
            raise
        NOTIFICATIONS.labels("sent").inc()
        return True

    async def _handle(self, message: AbstractIncomingMessage) -> None:
        await self.notify_once(parse_json(message))

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        await handle_with_retry(
            message, self.channel, settings.NOTIFIER_QUEUE_NAME, self._handle
        )

    async def start(self) -> None:
        """Запуск прослуховування черги сповіщень."""
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)

        queue = await declare_queue_with_retry(
            self.channel, settings.NOTIFIER_QUEUE_NAME
        )
        logger.info(
            "Воркер сповіщень запущено. Слухаємо чергу: '%s'",
            settings.NOTIFIER_QUEUE_NAME,
        )
        await queue.consume(self.process_message)

    async def stop(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        await self.redis.aclose()


notification_worker = NotificationWorker(
    aioredis.from_url(settings.redis_url, decode_responses=True)
)
