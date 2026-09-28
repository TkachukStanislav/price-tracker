from httpx import AsyncClient


async def test_health_check_endpoint(client: AsyncClient):
    # Використовуємо спільну фікстуру client із conftest.py
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "core_api",
        "status": "online",
    }


async def test_metrics_endpoint_uses_route_template(client: AsyncClient):
    # Запит до конкретного id має потрапити в метрики як шаблон маршруту,
    # інакше кожен id створював би окремий часовий ряд у Prometheus
    await client.get("/api/v1/items/12345")

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert 'handler="/api/v1/items/{item_id}"' in response.text
    assert 'handler="/api/v1/items/12345"' not in response.text
