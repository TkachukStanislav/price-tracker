from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_item_service
from app.models.user import User
from app.schemas.item import (
    PriceHistoryResponse,
    SimilarItemResponse,
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
    item_service: Annotated[ItemService, Depends(get_item_service)],
):
    """Створює новий товар для відстеження (прив'язується до поточного користувача)."""
    return await item_service.create_item(item_in=item_in, owner_id=current_user.id)


@router.get(
    "/",
    response_model=list[TrackedItemResponse],
)
async def read_items(
    current_user: Annotated[User, Depends(get_current_user)],
    item_service: Annotated[ItemService, Depends(get_item_service)],
    skip: int = 0,
    limit: int = 100,
):
    """Отримує список усіх товарів, які належать поточному користувачу."""
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
    item_service: Annotated[ItemService, Depends(get_item_service)],
):
    """Отримує один конкретний товар за ID з перевіркою доступу."""
    return await item_service.get_item_by_id(item_id=item_id, owner_id=current_user.id)


@router.get(
    "/{item_id}/similar",
    response_model=list[SimilarItemResponse],
)
async def read_similar_items(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    item_service: Annotated[ItemService, Depends(get_item_service)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
):
    """Повертає схожі за назвою товари поточного користувача (векторний пошук)."""
    return await item_service.get_similar_items(
        item_id=item_id, owner_id=current_user.id, limit=limit
    )


@router.get(
    "/{item_id}/price-history",
    response_model=list[PriceHistoryResponse],
)
async def read_price_history(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    item_service: Annotated[ItemService, Depends(get_item_service)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
):
    """Історія змін ціни товару, найновіші спочатку."""
    return await item_service.get_price_history(
        item_id=item_id, owner_id=current_user.id, limit=limit
    )


@router.patch(
    "/{item_id}",
    response_model=TrackedItemResponse,
)
async def update_item(
    item_id: int,
    item_in: TrackedItemUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    item_service: Annotated[ItemService, Depends(get_item_service)],
):
    """Частково оновлює товар (назву або цільову ціну)."""
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
    item_service: Annotated[ItemService, Depends(get_item_service)],
):
    """Видаляє товар за ID."""
    await item_service.delete_item(item_id=item_id, owner_id=current_user.id)
