"""Перераховує title_embedding для всіх товарів поточною моделлю.

Запускати після зміни EMBEDDING_MODEL: вектори різних моделей
не можна порівнювати між собою.

    docker compose exec core_api python -m app.scripts.reembed_items
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker
from app.models.item import TrackedItem
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


async def reembed_all_items(session: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """Обробляє товари пачками по id і повертає кількість оновлених."""
    processed = 0
    last_id = 0

    while True:
        # Keyset-пагінація: WHERE id > last_id швидша за OFFSET на великих таблицях
        result = await session.execute(
            select(TrackedItem)
            .where(TrackedItem.id > last_id)
            .order_by(TrackedItem.id)
            .limit(batch_size)
        )
        items = result.scalars().all()
        if not items:
            break

        vectors = await embedding_service.generate_embeddings_async(
            [item.title for item in items]
        )
        for item, vector in zip(items, vectors, strict=True):
            item.title_embedding = vector

        # Коміт після кожної пачки: якщо скрипт впаде, зроблене не втратиться
        await session.commit()
        processed += len(items)
        last_id = items[-1].id
        logger.info("Оновлено %d товарів (останній id=%d)", processed, last_id)

    return processed


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger.info("Модель: %s", settings.EMBEDDING_MODEL)
    async with async_session_maker() as session:
        total = await reembed_all_items(session)
    logger.info("Готово. Перераховано ембеддингів: %d", total)


if __name__ == "__main__":
    asyncio.run(main())
