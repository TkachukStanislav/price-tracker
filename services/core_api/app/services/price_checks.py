from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.item import TrackedItem
from app.repositories.item import ItemRepository

Publisher = Callable[[str, dict[str, Any]], Awaitable[None]]


def build_scrape_task_payload(item: TrackedItem) -> dict[str, Any]:
    """Повідомлення для scraper_service: які дані потрібні, щоб перевірити ціну."""
    return {
        "item_id": item.id,
        "ticker_or_url": item.ticker_or_url,
        "target_price": item.target_price,
        "owner_id": item.owner_id,
    }


async def dispatch_price_checks(session: AsyncSession, publish: Publisher) -> int:
    """Ставить усі товари в чергу на скрапінг і повертає їх кількість."""
    items = await ItemRepository(session).get_all()
    for item in items:
        await publish(settings.SCRAPER_QUEUE_NAME, build_scrape_task_payload(item))
    return len(items)
