from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import or_, select, update

from app.models.item import TrackedItem
from app.repositories.base import BaseRepository


class ItemRepository(BaseRepository[TrackedItem]):
    def __init__(self, session) -> None:
        super().__init__(TrackedItem, session)

    async def get_by_owner(
        self, owner_id: int, skip: int = 0, limit: int = 100
    ) -> Sequence[TrackedItem]:
        query = (
            select(TrackedItem)
            .where(TrackedItem.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all(self) -> Sequence[TrackedItem]:
        query = select(TrackedItem)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def find_similar(
        self, item: TrackedItem, max_distance: float, limit: int
    ) -> list[tuple[TrackedItem, float]]:
        """Шукає товари того ж власника, найближчі за косинусною відстанню."""
        if item.title_embedding is None:
            return []

        distance = TrackedItem.title_embedding.cosine_distance(item.title_embedding)
        query = (
            select(TrackedItem, distance.label("distance"))
            .where(TrackedItem.owner_id == item.owner_id)
            .where(TrackedItem.id != item.id)
            .where(TrackedItem.title_embedding.is_not(None))
            .where(distance < max_distance)
            .order_by(distance)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [(row.TrackedItem, row.distance) for row in result]

    async def update_price_if_newer(
        self, item_id: int, price: float, checked_at: datetime
    ) -> bool:
        """Оновлює ціну, лише якщо подія новіша за збережену. Повертає, чи оновлено.

        Перевірка і запис — один UPDATE ... WHERE, тому два споживачі, що
        одночасно обробляють події одного товару, не перезапишуть новішу ціну
        старішою (на відміну від «прочитати, порівняти, записати»).
        """
        result = await self.session.execute(
            update(TrackedItem)
            .where(TrackedItem.id == item_id)
            .where(
                or_(
                    TrackedItem.price_checked_at.is_(None),
                    TrackedItem.price_checked_at < checked_at,
                )
            )
            .values(current_price=price, price_checked_at=checked_at)
        )
        # Без commit: транзакцією керує той, хто викликає (разом з історією цін)
        return result.rowcount > 0
