import asyncio
import json
import logging
import aio_pika
from aio_pika import Message
from aio_pika.abc import AbstractIncomingMessage

from app.core.config import settings
from app.core.metrics import PRICE_ALERTS, SCRAPE_DURATION, SCRAPE_RESULTS
from app.core.redis import redis_client
from app.services.scraper import PriceScraper

logger = logging.getLogger(__name__)


class ScraperWorker:
    def __init__(self) -> None:
        self.connection: aio_pika.RobustConnection | None = None

    async def publish_price_update(self, item_id: int, current_price: float) -> None:
        """Відправляє подію з новою ціною назад у core_api для збереження в БД."""
        if not self.connection or self.connection.is_closed:
            return

        async with self.connection.channel() as channel:
            queue = await channel.declare_queue(
                settings.PRICE_UPDATED_QUEUE_NAME,
                durable=True,
            )
            payload = {"item_id": item_id, "current_price": current_price}
            message = Message(
                body=json.dumps(payload).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await channel.default_exchange.publish(
                message,
                routing_key=queue.name,
            )
            logger.info(
                f"[DB SYNC] Відправлено нову ціну товару #{item_id} -> {current_price}"
            )

    async def publish_alert(self, payload: dict) -> None:
        """Публікує подію зниження ціни для сервісу сповіщень."""
        if not self.connection or self.connection.is_closed:
            return

        async with self.connection.channel() as channel:
            queue = await channel.declare_queue(
                settings.NOTIFIER_QUEUE_NAME,
                durable=True,
            )
            message = Message(
                body=json.dumps(payload).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await channel.default_exchange.publish(
                message,
                routing_key=queue.name,
            )
            logger.info(
                f"[ALERT TRIGGERED] Відправлено завдання в нотифікатор: {payload}"
            )

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        """Обробляє одне повідомлення з черги скрапінгу."""
        async with message.process():
            payload = json.loads(message.body.decode("utf-8"))
            item_id = payload.get("item_id")
            ticker_or_url = payload.get("ticker_or_url")
            target_price = payload.get("target_price")
            owner_id = payload.get("owner_id")

            logger.info(
                f"Отримано завдання на скрапінг: ID={item_id}, Ціль={target_price}"
            )

            # 1. Перевірка кешу Redis
            price = await redis_client.get_cached_price(ticker_or_url)

            if price is not None:
                SCRAPE_RESULTS.labels("cache_hit").inc()
                logger.info(f"[CACHE HIT] Ціна з Redis: {price} для {ticker_or_url}")
            else:
                # 2. Якщо немає в кеші — скрапимо
                with SCRAPE_DURATION.time():
                    price = await PriceScraper.fetch_price(ticker_or_url)
                if price is not None:
                    await redis_client.set_cached_price(ticker_or_url, price)
                    logger.info(
                        f"[SCRAPED] Отримана нова ціна: {price} (збережено в Redis)"
                    )

            logger.info(f"Обробка товару #{item_id} завершена. Поточна ціна: {price}")

            # 3. Синхронізуємо ціну з базою даних core_api
            if price is not None and item_id is not None:
                await self.publish_price_update(item_id=item_id, current_price=price)

            # 4. Перевірка критерію сповіщення
            if price is not None and target_price is not None and price <= target_price:
                alert_payload = {
                    "item_id": item_id,
                    "owner_id": owner_id,
                    "ticker_or_url": ticker_or_url,
                    "current_price": price,
                    "target_price": target_price,
                }
                await self.publish_alert(alert_payload)
                PRICE_ALERTS.inc()

    async def start(self) -> None:
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await self.connection.channel()
        await channel.set_qos(prefetch_count=5)

        queue = await channel.declare_queue(
            settings.SCRAPER_QUEUE_NAME,
            durable=True,
        )

        logger.info(f"Воркер запущено. Слухаємо чергу: '{settings.SCRAPER_QUEUE_NAME}'")
        await queue.consume(self.process_message)

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()


scraper_worker = ScraperWorker()
