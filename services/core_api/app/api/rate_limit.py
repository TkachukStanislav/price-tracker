import logging
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from redis.exceptions import RedisError

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class RateLimiter:
    """Обмежує кількість запитів з однієї IP-адреси за вікно часу (fixed window).

    Використання: Depends(RateLimiter("login", limit=5, window_seconds=60)).
    Лічильник — ключ Redis rate:<scope>:<ip>, який живе window_seconds.
    """

    def __init__(self, scope: str, limit: int, window_seconds: int) -> None:
        self.scope = scope
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(
        self,
        request: Request,
        redis: Annotated[aioredis.Redis, Depends(get_redis)],
    ) -> None:
        # За reverse proxy тут буде IP проксі: тоді uvicorn --proxy-headers
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate:{self.scope}:{client_ip}"

        try:
            # INCR і EXPIRE в одній транзакції: ключ не може залишитися без TTL.
            # nx=True — TTL ставиться лише першим запитом у вікні
            async with redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, self.window_seconds, nx=True)
                count, _ = await pipe.execute()
            if count <= self.limit:
                return
            retry_after = await redis.ttl(key)
        except RedisError:
            # Fail open: недоступний Redis не повинен блокувати вхід у систему
            logger.warning("Rate limiter недоступний, запит пропущено", exc_info=True)
            return

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Забагато спроб. Спробуйте пізніше.",
            headers={"Retry-After": str(max(retry_after, 1))},
        )
