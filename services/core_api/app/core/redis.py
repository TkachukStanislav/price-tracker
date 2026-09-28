"""Клієнт Redis для core_api: rate limiting і кеш.

Клієнт лінивий: з'єднання відкривається при першій команді, тому його можна
створити на рівні модуля. У тестах get_redis підміняється на fakeredis.
"""

import redis.asyncio as aioredis

from app.core.config import settings

redis_client: aioredis.Redis = aioredis.from_url(
    settings.redis_url, decode_responses=True
)


async def get_redis() -> aioredis.Redis:
    return redis_client
