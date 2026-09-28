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
        query = select(TrackedItem)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def find_similar_by_embedding(
        self, embedding: list[float], threshold: float = 0.25
    ) -> TrackedItem | None:
        distance_expr = TrackedItem.title_embedding.cosine_distance(embedding)
        query = (
            select(TrackedItem)
            .where(TrackedItem.title_embedding.is_not(None))
            .where(distance_expr < threshold)
            .order_by(distance_expr)
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalars().first()
