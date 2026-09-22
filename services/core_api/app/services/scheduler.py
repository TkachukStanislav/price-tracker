import asyncio
import logging

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.rabbitmq import rabbitmq_client
from app.repositories.item import ItemRepository

logger = logging.getLogger(__name__)


class PriceCheckScheduler:
    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self._is_running = False

    async def check_all_items(self) -> None:
        """Збирає всі товари з БД і відправляє завдання на скрапінг у RabbitMQ."""
        async with async_session_maker() as session:
            item_repo = ItemRepository(session)
            items = await item_repo.get_all()

            if not items:
                logger.info("[SCHEDULER] У базі немає товарів для перевірки.")
                return

            logger.info(
                f"[SCHEDULER] Запуск періодичної перевірки для {len(items)} товарів..."
            )

            for item in items:
                await rabbitmq_client.publish_message(
                    queue_name=settings.SCRAPER_QUEUE_NAME,
                    payload={
                        "item_id": item.id,
                        "ticker_or_url": item.ticker_or_url,
                        "target_price": item.target_price,
                        "owner_id": item.owner_id,
                    },
                )

    async def start(self) -> None:
        """Нескінченний цикл періодичного опитування."""
        self._is_running = True
        logger.info(
            f"[SCHEDULER] Планувальник запущено. Інтервал: {self.interval_seconds} сек."
        )

        while self._is_running:
            try:
                await asyncio.sleep(self.interval_seconds)
                await self.check_all_items()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SCHEDULER] Помилка під час періодичної перевірки: {e}")

    def stop(self) -> None:
        self._is_running = False


# Для тесту ставимо інтервал 60 секунд (у продакшені можна 3600 або брати з config)
price_scheduler = PriceCheckScheduler(interval_seconds=60)
