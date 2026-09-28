import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rabbitmq import rabbitmq_client
from app.models.item import TrackedItem
from app.models.price_history import PriceHistory
from app.repositories.item import ItemRepository
from app.repositories.price_history import PriceHistoryRepository
from app.schemas.item import (
    SimilarItemResponse,
    TrackedItemCreate,
    TrackedItemResponse,
    TrackedItemUpdate,
)
from app.services.embedding_service import embedding_service
from app.services.price_checks import build_scrape_task_payload
from app.services.similar_cache import SimilarItemsCache

logger = logging.getLogger(__name__)

# Косинусна відстань: 0 — однакові за змістом, 1 — не пов'язані, 2 — протилежні
# Підібрано під paraphrase-multilingual-MiniLM: однакові товари (у т.ч. EN↔UA)
# дають до ~0.27, різні — від ~0.46. Поріг посередині розриву.
SIMILARITY_MAX_DISTANCE = 0.35


class ItemService:
    def __init__(
        self,
        session_or_repo: AsyncSession | ItemRepository,
        similar_cache: SimilarItemsCache | None = None,
    ) -> None:
        self.similar_cache = similar_cache
        if isinstance(session_or_repo, AsyncSession):
            self.repository = ItemRepository(session_or_repo)
            self.session = session_or_repo
        else:
            self.repository = session_or_repo
            self.session = getattr(session_or_repo, "session", None)

    async def create_item(
        self, item_in: TrackedItemCreate, owner_id: int
    ) -> TrackedItem:
        # 1. Generate text embedding
        embedding = await embedding_service.generate_embedding_async(item_in.title)

        # 2. Create record with embedding
        item_data = item_in.model_dump()
        item = await self.repository.create(
            **item_data,
            owner_id=owner_id,
            title_embedding=embedding,
        )

        # 3. Dispatch scraper event
        await rabbitmq_client.publish_message(
            queue_name=settings.SCRAPER_QUEUE_NAME,
            payload=build_scrape_task_payload(item),
        )
        await self._invalidate_similar_cache(owner_id)
        return item

    async def get_item_by_id(self, item_id: int, owner_id: int) -> TrackedItem:
        item = await self.repository.get_by_id(item_id)
        if item is None or item.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Товар не знайдено",
            )
        return item

    async def get_user_items(
        self, owner_id: int, skip: int = 0, limit: int = 100
    ) -> list[TrackedItem]:
        items = await self.repository.get_by_owner(
            owner_id=owner_id, skip=skip, limit=limit
        )
        return list(items)

    async def get_similar_items(
        self, item_id: int, owner_id: int, limit: int
    ) -> list[SimilarItemResponse]:
        # Перевірка власника — завжди, навіть якщо результат є в кеші
        item = await self.get_item_by_id(item_id=item_id, owner_id=owner_id)

        cache = self.similar_cache
        cache_key = await cache.build_key(owner_id, item_id, limit) if cache else None
        if cache and (cached := await cache.get(cache_key)) is not None:
            return cached

        similar = await self.repository.find_similar(
            item, max_distance=SIMILARITY_MAX_DISTANCE, limit=limit
        )
        results = [
            SimilarItemResponse(
                item=TrackedItemResponse.model_validate(similar_item),
                distance=distance,
            )
            for similar_item, distance in similar
        ]
        if cache:
            await cache.set(cache_key, results)
        return results

    async def get_price_history(
        self, item_id: int, owner_id: int, limit: int
    ) -> list[PriceHistory]:
        await self.get_item_by_id(item_id=item_id, owner_id=owner_id)
        history = await PriceHistoryRepository(self.session).get_for_item(
            item_id, limit
        )
        return list(history)

    async def _invalidate_similar_cache(self, owner_id: int) -> None:
        if self.similar_cache:
            await self.similar_cache.invalidate(owner_id)

    async def update_item(
        self, item_id: int, item_in: TrackedItemUpdate, owner_id: int
    ) -> TrackedItem:
        item = await self.get_item_by_id(item_id=item_id, owner_id=owner_id)

        update_data = item_in.model_dump(exclude_unset=True, exclude_none=True)
        if "title" in update_data:
            new_title = update_data["title"]
            embedding = await embedding_service.generate_embedding_async(new_title)
            update_data["title_embedding"] = embedding
        item = await self.repository.update(item, **update_data)
        await self._invalidate_similar_cache(owner_id)
        return item

    async def delete_item(self, item_id: int, owner_id: int) -> None:
        item = await self.get_item_by_id(item_id=item_id, owner_id=owner_id)
        await self.repository.delete(item)
        await self._invalidate_similar_cache(owner_id)
