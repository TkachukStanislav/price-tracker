from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_async_session
from app.models.user import User
from app.schemas.item import (
    TrackedItemCreate,
    TrackedItemResponse,
    TrackedItemUpdate,
)
from app.services.item_service import ItemService

router = APIRouter(prefix="/items", tags=["Tracked Items"])


@router.post(
    "/",
    response_model=TrackedItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    item_in: TrackedItemCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Створює новий товар для відстеження (прив'язується до поточного користувача)."""
    item_service = ItemService(session)
    return await item_service.create_item(item_in=item_in, owner_id=current_user.id)


@router.get(
    "/",
    response_model=list[TrackedItemResponse],
)
async def read_items(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
):
    """Отримує список усіх товарів, які належать поточному користувачу."""
    item_service = ItemService(session)
    return await item_service.get_user_items(
        owner_id=current_user.id, skip=skip, limit=limit
    )


@router.get(
    "/{item_id}",
    response_model=TrackedItemResponse,
)
async def read_item_by_id(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Отримує один конкретний товар за ID з перевіркою доступу."""
    item_service = ItemService(session)
    return await item_service.get_item_by_id(item_id=item_id, owner_id=current_user.id)


@router.patch(
    "/{item_id}",
    response_model=TrackedItemResponse,
)
async def update_item(
    item_id: int,
    item_in: TrackedItemUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Частково оновлює товар (назву або цільову ціну)."""
    item_service = ItemService(session)
    return await item_service.update_item(
        item_id=item_id, item_in=item_in, owner_id=current_user.id
    )


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_item(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Видаляє товар за ID."""
    item_service = ItemService(session)
    await item_service.delete_item(item_id=item_id, owner_id=current_user.id)
    return None
