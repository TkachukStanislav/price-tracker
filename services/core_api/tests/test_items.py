from unittest.mock import AsyncMock

from httpx import AsyncClient

from app.core.config import settings
from app.services.item_service import SIMILARITY_MAX_DISTANCE

AUTH_PREFIX = f"{settings.API_V1_STR}/auth"
ITEMS_PREFIX = f"{settings.API_V1_STR}/items"

ITEM_PAYLOAD = {
    "title": "Apple iPhone 15 Pro 128GB",
    "ticker_or_url": "https://example.com/iphone",
    "target_price": 900.0,
}


async def get_auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    """Реєструє користувача, логінить і повертає заголовок авторизації."""
    password = "StrongPassword123!"
    await client.post(
        f"{AUTH_PREFIX}/register", json={"email": email, "password": password}
    )
    response = await client.post(
        f"{AUTH_PREFIX}/login", data={"username": email, "password": password}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_item_success(client: AsyncClient, mock_publish: AsyncMock):
    # Arrange
    headers = await get_auth_headers(client, "creator@example.com")

    # Act
    response = await client.post(f"{ITEMS_PREFIX}/", json=ITEM_PAYLOAD, headers=headers)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == ITEM_PAYLOAD["title"]
    assert data["current_price"] is None

    # Задача на скрапінг пішла в чергу рівно один раз і з правильним товаром
    mock_publish.assert_awaited_once()
    payload = mock_publish.call_args.kwargs["payload"]
    assert payload["item_id"] == data["id"]


async def create_item(
    client: AsyncClient, headers: dict[str, str], **overrides
) -> dict:
    """Створює товар через API і повертає його JSON."""
    payload = {**ITEM_PAYLOAD, **overrides}
    response = await client.post(f"{ITEMS_PREFIX}/", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def test_create_item_unauthorized(client: AsyncClient, mock_publish: AsyncMock):
    response = await client.post(f"{ITEMS_PREFIX}/", json=ITEM_PAYLOAD)

    assert response.status_code == 401
    mock_publish.assert_not_awaited()


async def test_list_items_returns_only_own(client: AsyncClient):
    owner_headers = await get_auth_headers(client, "list_owner@example.com")
    other_headers = await get_auth_headers(client, "list_other@example.com")
    await create_item(client, owner_headers, title="Мій товар")
    await create_item(client, other_headers, title="Чужий товар")

    response = await client.get(f"{ITEMS_PREFIX}/", headers=owner_headers)

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == ["Мій товар"]


async def test_get_item_success(client: AsyncClient):
    headers = await get_auth_headers(client, "get_owner@example.com")
    item = await create_item(client, headers)

    response = await client.get(f"{ITEMS_PREFIX}/{item['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == item["id"]


async def test_get_item_of_another_user_returns_404(client: AsyncClient):
    owner_headers = await get_auth_headers(client, "idor_owner@example.com")
    intruder_headers = await get_auth_headers(client, "idor_intruder@example.com")
    item = await create_item(client, owner_headers)

    response = await client.get(
        f"{ITEMS_PREFIX}/{item['id']}", headers=intruder_headers
    )

    assert response.status_code == 404


async def test_get_nonexistent_item_returns_404(client: AsyncClient):
    headers = await get_auth_headers(client, "missing@example.com")

    response = await client.get(f"{ITEMS_PREFIX}/999999", headers=headers)

    assert response.status_code == 404


async def test_update_item_partial(client: AsyncClient):
    headers = await get_auth_headers(client, "patch_owner@example.com")
    item = await create_item(client, headers)

    response = await client.patch(
        f"{ITEMS_PREFIX}/{item['id']}", json={"target_price": 500.0}, headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["target_price"] == 500.0
    assert data["title"] == item["title"]


async def test_update_item_null_title_is_ignored(client: AsyncClient):
    headers = await get_auth_headers(client, "patch_null@example.com")
    item = await create_item(client, headers)

    response = await client.patch(
        f"{ITEMS_PREFIX}/{item['id']}", json={"title": None}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["title"] == item["title"]


async def test_delete_item(client: AsyncClient):
    headers = await get_auth_headers(client, "delete_owner@example.com")
    item = await create_item(client, headers)

    delete_response = await client.delete(
        f"{ITEMS_PREFIX}/{item['id']}", headers=headers
    )
    get_response = await client.get(f"{ITEMS_PREFIX}/{item['id']}", headers=headers)

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


async def test_delete_item_of_another_user_returns_404(client: AsyncClient):
    owner_headers = await get_auth_headers(client, "del_owner@example.com")
    intruder_headers = await get_auth_headers(client, "del_intruder@example.com")
    item = await create_item(client, owner_headers)

    delete_response = await client.delete(
        f"{ITEMS_PREFIX}/{item['id']}", headers=intruder_headers
    )
    get_response = await client.get(
        f"{ITEMS_PREFIX}/{item['id']}", headers=owner_headers
    )

    assert delete_response.status_code == 404
    assert get_response.status_code == 200


async def test_similar_items_returns_close_own_items(client: AsyncClient):
    headers = await get_auth_headers(client, "similar_owner@example.com")
    other_headers = await get_auth_headers(client, "similar_other@example.com")
    source = await create_item(client, headers, title="Apple iPhone 15 Pro 128GB")
    close = await create_item(client, headers, title="Apple iPhone 15 Pro 256GB")
    await create_item(client, headers, title="Samsung washing machine 7kg")
    await create_item(client, other_headers, title="Apple iPhone 15 Pro 128GB Black")

    response = await client.get(
        f"{ITEMS_PREFIX}/{source['id']}/similar", headers=headers
    )

    assert response.status_code == 200
    results = response.json()
    # Лише схожий товар цього ж користувача: без себе, пральки і чужого iPhone
    assert [result["item"]["id"] for result in results] == [close["id"]]
    assert 0 <= results[0]["distance"] < SIMILARITY_MAX_DISTANCE


async def test_similar_items_of_another_user_returns_404(client: AsyncClient):
    owner_headers = await get_auth_headers(client, "sim_idor_owner@example.com")
    intruder_headers = await get_auth_headers(client, "sim_idor_intruder@example.com")
    item = await create_item(client, owner_headers)

    response = await client.get(
        f"{ITEMS_PREFIX}/{item['id']}/similar", headers=intruder_headers
    )

    assert response.status_code == 404


async def test_similar_items_rejects_invalid_limit(client: AsyncClient):
    headers = await get_auth_headers(client, "sim_limit@example.com")
    item = await create_item(client, headers)

    response = await client.get(
        f"{ITEMS_PREFIX}/{item['id']}/similar?limit=0", headers=headers
    )

    assert response.status_code == 422
