import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rabbitmq import rabbitmq_client
from app.models.item import TrackedItem
from app.repositories.item import ItemRepository
from app.schemas.item import TrackedItemCreate, TrackedItemUpdate
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


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

        # 2. Semantic deduplication check
        similar_item = await self.repository.find_similar_by_embedding(
            embedding=embedding, threshold=0.25
        )
        if similar_item:
            logger.info(
                f"[AI DEDUPLICATION] Duplicate detected! "
                f"New: '{item_in.title}' matches ID={similar_item.id} ('{similar_item.title}')"
            )

        # 3. Create record with embedding
        item_data = item_in.model_dump()
        item = await self.repository.create(
            **item_data,
            owner_id=owner_id,
            title_embedding=embedding,
        )

        # 4. Dispatch scraper event
        await rabbitmq_client.publish_message(
            queue_name=settings.SCRAPER_QUEUE_NAME,
            payload={
                "item_id": item.id,
                "ticker_or_url": item.ticker_or_url,
                "target_price": item.target_price,
                "owner_id": item.owner_id,
            },
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
