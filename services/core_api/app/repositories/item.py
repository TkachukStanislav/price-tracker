from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import TrackedItem
from app.repositories.base import BaseRepository


class ItemRepository(BaseRepository[TrackedItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TrackedItem, session)

    async def get_by_owner(
        self, owner_id: int, skip: int = 0, limit: int = 100
    ) -> Sequence[TrackedItem]:
        """Отримує всі товари конкретного користувача."""
        result = await self.session.execute(
            select(TrackedItem)
            .where(TrackedItem.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
