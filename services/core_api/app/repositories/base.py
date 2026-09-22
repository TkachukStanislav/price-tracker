from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, item_id: int) -> ModelType | None:
        """Отримує один запис за первинним ключем."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == item_id)
        )
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[ModelType]:
        """Отримує список записів із пагінацією."""
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, **kwargs) -> ModelType:
        """Створює новий об'єкт у базі даних."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelType) -> None:
        """Видаляє об'єкт із бази даних."""
        await self.session.delete(instance)
        await self.session.commit()

    async def update(self, instance: ModelType, **kwargs) -> ModelType:
        """Оновлює поля переданого об'єкта в базі даних."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance
