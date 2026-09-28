from httpx import AsyncClient


async def test_health_check_endpoint(client: AsyncClient):
    # Використовуємо спільну фікстуру client із conftest.py
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "core_api",
        "status": "online",
    }
