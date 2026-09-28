import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self) -> None:
        self.redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Створює пул з'єднань з Redis."""
        if not self.redis:
            self.redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Успішно підключено до Redis")

    async def close(self) -> None:
        """Закриває пул з'єднань під час зупинки сервісу."""
        if self.redis:
            await self.redis.close()
            logger.info("З'єднання з Redis закрито")

    async def get_cached_price(self, ticker_or_url: str) -> float | None:
        """Повертає кешовану ціну, якщо вона ще валідна."""
        if not self.redis:
            return None
        cached = await self.redis.get(f"price:{ticker_or_url}")
        return float(cached) if cached else None

    async def set_cached_price(self, ticker_or_url: str, price: float) -> None:
        """Зберігає ціну в кеш із часом життя (TTL)."""
        if self.redis:
            await self.redis.set(
                f"price:{ticker_or_url}",
                str(price),
                ex=settings.REDIS_CACHE_TTL_SECONDS,
            )


redis_client = RedisClient()
