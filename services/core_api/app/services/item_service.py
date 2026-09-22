from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rabbitmq import rabbitmq_client
from app.models.item import TrackedItem
from app.repositories.item import ItemRepository
from app.schemas.item import TrackedItemCreate, TrackedItemUpdate


class ItemService:
    def __init__(self, session: AsyncSession) -> None:
        self.item_repo = ItemRepository(session)

    async def create_item(
        self, item_in: TrackedItemCreate, owner_id: int
    ) -> TrackedItem:
        # 1. Зберігаємо товар у PostgreSQL
        item = await self.item_repo.create(
            title=item_in.title,
            ticker_or_url=item_in.ticker_or_url,
            target_price=item_in.target_price,
            owner_id=owner_id,
        )

        # 2. Відправляємо подію для сервісу-скрапера в RabbitMQ
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

    async def get_user_items(
        self, owner_id: int, skip: int = 0, limit: int = 100
    ) -> Sequence[TrackedItem]:
        return await self.item_repo.get_by_owner(
            owner_id=owner_id, skip=skip, limit=limit
        )

    async def get_item_by_id(self, item_id: int, owner_id: int) -> TrackedItem:
        item = await self.item_repo.get_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Товар не знайдено",
            )
        if item.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Немає доступу до цього товару",
            )
        return item

    async def update_item(
        self,
        item_id: int,
        item_in: TrackedItemUpdate,
        owner_id: int,
    ) -> TrackedItem:
        item = await self.get_item_by_id(item_id, owner_id)
        update_data = item_in.model_dump(exclude_unset=True)
        return await self.item_repo.update(item, **update_data)

    async def delete_item(self, item_id: int, owner_id: int) -> None:
        item = await self.get_item_by_id(item_id, owner_id)
        await self.item_repo.delete(item)
