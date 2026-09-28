from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_session
from app.core.redis import get_redis
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.token import TokenPayload
from app.services.item_service import ItemService
from app.services.similar_cache import SimilarItemsCache

# Вказуємо FastAPI, звідки клієнт має отримувати токен (URL ендпоінта логіну)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    """Витягує користувача з JWT токена.

    Якщо токен невалідний або користувача немає — кидає 401 помилку.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не вдалося підтвердити облікові дані",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Розшифровуємо токен за допомогою нашого SECRET_KEY
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenPayload(sub=int(user_id))
    except (JWTError, ValueError):
        raise credentials_exception

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(token_data.sub)

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Користувач неактивний",
        )

    return user


async def get_item_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> ItemService:
    """Збирає ItemService з усіма залежностями для роутерів."""
    cache = SimilarItemsCache(redis, ttl_seconds=settings.SIMILAR_CACHE_TTL_SECONDS)
    return ItemService(session, similar_cache=cache)
