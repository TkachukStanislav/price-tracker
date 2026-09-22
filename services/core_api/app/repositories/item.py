from collections.abc import Sequence
from sqlalchemy import select
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
        """Повертає абсолютно всі товари з бази для фонової перевірки цін."""
        query = select(TrackedItem)
        result = await self.session.execute(query)
        return result.scalars().all()
