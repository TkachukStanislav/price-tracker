import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.anyio
async def test_health_check_endpoint():
    # 1. Arrange: Налаштовуємо ASGI-транспорт безпосередньо на наш FastAPI додаток
    # ASGITransport дозволяє надсилати запити в пам'яті без відкриття мережевих портів
    transport = ASGITransport(app=app)

    # 2. Act: Робимо асинхронний GET-запит до ендпоінта /health
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    # 3. Assert: Перевіряємо статус відповіді та JSON
    assert response.status_code == 200
    assert response.json() == {
        "service": "core_api",
        "status": "online",
    }
