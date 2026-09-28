"""Кеш результатів /items/{id}/similar у Redis з версіонованими ключами.

Замість того щоб шукати й видаляти всі ключі користувача при зміні товару,
у ключ входить «версія» його товарів: items_version:<owner_id>. Будь-яка зміна
(створення, оновлення, видалення) робить INCR версії, і старі ключі просто
перестають читатися, а Redis сам видалить їх за TTL.
"""

import logging

import redis.asyncio as aioredis
from pydantic import TypeAdapter
from redis.exceptions import RedisError

from app.schemas.item import SimilarItemResponse

logger = logging.getLogger(__name__)

_results_adapter = TypeAdapter(list[SimilarItemResponse])


class SimilarItemsCache:
    def __init__(self, redis: aioredis.Redis, ttl_seconds: int) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    async def build_key(self, owner_id: int, item_id: int, limit: int) -> str | None:
        """Ключ для запиту. Версію читаємо один раз: з нею ж і записуємо результат,
        інакше зміна товару посеред запиту записала б старий результат під нову версію.
        """
        try:
            version = await self.redis.get(f"items_version:{owner_id}") or "0"
        except RedisError:
            logger.warning("Кеш недоступний", exc_info=True)
            return None
        return f"similar:{owner_id}:v{version}:{item_id}:{limit}"

    async def get(self, key: str | None) -> list[SimilarItemResponse] | None:
        if key is None:
            return None
        try:
            cached = await self.redis.get(key)
        except RedisError:
            logger.warning("Кеш недоступний", exc_info=True)
            return None
        return _results_adapter.validate_json(cached) if cached else None

    async def set(self, key: str | None, results: list[SimilarItemResponse]) -> None:
        if key is None:
            return
        try:
            await self.redis.set(
                key, _results_adapter.dump_json(results), ex=self.ttl_seconds
            )
        except RedisError:
            logger.warning("Кеш недоступний", exc_info=True)

    async def invalidate(self, owner_id: int) -> None:
        try:
            await self.redis.incr(f"items_version:{owner_id}")
        except RedisError:
            # Кеш застаріє не довше ніж на TTL
            logger.warning("Не вдалося скинути кеш", exc_info=True)
