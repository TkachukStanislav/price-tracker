import logging
from datetime import UTC, datetime
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage

from app.core.config import settings
from app.core.messaging import (
    PermanentMessageError,
    build_message,
    declare_queue_with_retry,
    handle_with_retry,
    parse_json,
)
from app.core.metrics import PRICE_ALERTS, SCRAPE_DURATION, SCRAPE_RESULTS
from app.core.redis import redis_client
from app.services.scraper import PriceScraper

logger = logging.getLogger(__name__)


class ScraperWorker:
    def __init__(self) -> None:
        self.connection: aio_pika.abc.AbstractRobustConnection | None = None
        self.channel: AbstractChannel | None = None

    async def publish(self, queue_name: str, payload: dict[str, Any]) -> None:
        # Оголошуємо з тими ж аргументами, що й споживач (retry/DLQ)
        queue = await declare_queue_with_retry(self.channel, queue_name)
        await self.channel.default_exchange.publish(
            build_message(payload), routing_key=queue.name
        )

    async def _handle(self, message: AbstractIncomingMessage) -> None:
        """Обробляє одне завдання на скрапінг. Помилки обробляє handle_with_retry."""
        payload = parse_json(message)
        try:
            item_id = int(payload["item_id"])
            ticker_or_url = str(payload["ticker_or_url"])
        except (KeyError, TypeError, ValueError) as e:
            raise PermanentMessageError(f"Некоректне завдання: {e}") from e
        target_price = payload.get("target_price")

        # 1. Кеш Redis: якщо ціну нещодавно отримували, сайт не чіпаємо
        price = await redis_client.get_cached_price(ticker_or_url)
        if price is not None:
            SCRAPE_RESULTS.labels("cache_hit").inc()
        else:
            # 2. Скрапінг. TemporaryScrapeError піде на повтор через 5 с
            with SCRAPE_DURATION.time():
                price = await PriceScraper.fetch_price(ticker_or_url)
            if price is not None:
                await redis_client.set_cached_price(ticker_or_url, price)

        logger.info("Товар #%s: ціна %s", item_id, price)
        if price is None:
            return

        # 3. Подія для core_api. checked_at дозволяє споживачу відкинути
        # застарілі й повторні події (ідемпотентність)
        await self.publish(
            settings.PRICE_UPDATED_QUEUE_NAME,
            {
                "item_id": item_id,
                "current_price": price,
                "checked_at": datetime.now(UTC).isoformat(),
            },
        )

        # 4. Ціна досягла цілі — сповіщення
        if target_price is not None and price <= target_price:
            await self.publish(
                settings.NOTIFIER_QUEUE_NAME,
                {
                    "item_id": item_id,
                    "owner_id": payload.get("owner_id"),
                    "ticker_or_url": ticker_or_url,
                    "current_price": price,
                    "target_price": target_price,
                },
            )
            PRICE_ALERTS.inc()
            logger.info("Товар #%s: ціна досягла цілі, сповіщення надіслано", item_id)

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        await handle_with_retry(
            message, self.channel, settings.SCRAPER_QUEUE_NAME, self._handle
        )

    async def start(self) -> None:
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=5)

        queue = await declare_queue_with_retry(
            self.channel, settings.SCRAPER_QUEUE_NAME
        )
        logger.info(
            "Воркер запущено. Слухаємо чергу: '%s'", settings.SCRAPER_QUEUE_NAME
        )
        await queue.consume(self.process_message)

    async def stop(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()


scraper_worker = ScraperWorker()
