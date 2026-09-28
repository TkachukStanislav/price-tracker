from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import insert, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_history import PriceHistory


class PriceHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_if_changed(
        self, item_id: int, price: float, checked_at: datetime
    ) -> None:
        """Додає запис, якщо ціна відрізняється від останньої збереженої.

        Один INSERT ... SELECT ... WHERE: порівняння й вставка атомарні.
        Викликається після UPDATE товару в тій самій транзакції, тому рядок
        товару заблокований і паралельні споживачі не вставлять дубль.
        """
        last_price = (
            select(PriceHistory.price)
            .where(PriceHistory.item_id == item_id)
            .order_by(PriceHistory.checked_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        await self.session.execute(
            insert(PriceHistory).from_select(
                ["item_id", "price", "checked_at"],
                select(literal(item_id), literal(price), literal(checked_at)).where(
                    literal(price).is_distinct_from(last_price)
                ),
            )
        )

    async def get_for_item(self, item_id: int, limit: int) -> Sequence[PriceHistory]:
        result = await self.session.execute(
            select(PriceHistory)
            .where(PriceHistory.item_id == item_id)
            .order_by(PriceHistory.checked_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
