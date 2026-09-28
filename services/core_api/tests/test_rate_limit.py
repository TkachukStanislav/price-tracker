import fakeredis
from httpx import AsyncClient

from app.core.config import settings
from app.core.redis import get_redis
from app.main import app

LOGIN_URL = f"{settings.API_V1_STR}/auth/login"
WRONG_CREDENTIALS = {"username": "nobody@example.com", "password": "wrong"}


async def test_login_is_rate_limited(client: AsyncClient):
    for _ in range(settings.LOGIN_RATE_LIMIT):
        response = await client.post(LOGIN_URL, data=WRONG_CREDENTIALS)
        assert response.status_code == 401

    response = await client.post(LOGIN_URL, data=WRONG_CREDENTIALS)

    assert response.status_code == 429
    assert (
        0 < int(response.headers["Retry-After"]) <= settings.LOGIN_RATE_WINDOW_SECONDS
    )


async def test_rate_limit_counter_expires(
    client: AsyncClient, fake_redis: fakeredis.FakeAsyncRedis
):
    await client.post(LOGIN_URL, data=WRONG_CREDENTIALS)

    # Лічильник має TTL, інакше користувача було б заблоковано назавжди
    ttl = await fake_redis.ttl("rate:login:127.0.0.1")
    assert 0 < ttl <= settings.LOGIN_RATE_WINDOW_SECONDS


async def test_login_works_when_redis_is_down(client: AsyncClient):
    server = fakeredis.FakeServer()
    server.connected = False
    app.dependency_overrides[get_redis] = lambda: fakeredis.FakeAsyncRedis(
        server=server
    )

    # Fail open: недоступний Redis не блокує вхід
    for _ in range(settings.LOGIN_RATE_LIMIT + 1):
        response = await client.post(LOGIN_URL, data=WRONG_CREDENTIALS)
        assert response.status_code == 401
