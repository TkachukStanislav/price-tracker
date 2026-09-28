import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rabbitmq import rabbitmq_client
from app.models.item import TrackedItem
from app.repositories.item import ItemRepository
from app.schemas.item import TrackedItemCreate, TrackedItemUpdate
from app.services.embedding_service import embedding_service
from app.services.price_checks import build_scrape_task_payload

logger = logging.getLogger(__name__)

# Косинусна відстань: 0 — однакові за змістом, 1 — не пов'язані, 2 — протилежні
# Підібрано під paraphrase-multilingual-MiniLM: однакові товари (у т.ч. EN↔UA)
# дають до ~0.27, різні — від ~0.46. Поріг посередині розриву.
SIMILARITY_MAX_DISTANCE = 0.35


class ItemService:
    def __init__(self, session_or_repo: AsyncSession | ItemRepository) -> None:
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
    ) -> list[dict]:
        item = await self.get_item_by_id(item_id=item_id, owner_id=owner_id)
        similar = await self.repository.find_similar(
            item, max_distance=SIMILARITY_MAX_DISTANCE, limit=limit
        )
        return [
            {"item": similar_item, "distance": distance}
            for similar_item, distance in similar
        ]

    async def update_item(
        self, item_id: int, item_in: TrackedItemUpdate, owner_id: int
    ) -> TrackedItem:
        item = await self.get_item_by_id(item_id=item_id, owner_id=owner_id)

        update_data = item_in.model_dump(exclude_unset=True, exclude_none=True)
        if "title" in update_data:
            new_title = update_data["title"]
            embedding = await embedding_service.generate_embedding_async(new_title)
            update_data["title_embedding"] = embedding
        return await self.repository.update(item, **update_data)

    async def delete_item(self, item_id: int, owner_id: int) -> None:
        item = await self.get_item_by_id(item_id=item_id, owner_id=owner_id)
        await self.repository.delete(item)
