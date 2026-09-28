import pytest
from httpx import AsyncClient

from app.core.config import settings

AUTH_PREFIX = f"{settings.API_V1_STR}/auth"


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    """Тест успішної реєстрації нового користувача з записом у тестову БД."""
    payload = {
        "email": "tester@example.com",
        "password": "StrongPassword123!",
    }

    response = await client.post(f"{AUTH_PREFIX}/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert "id" in data
    # Переконуємося, що хеш пароля не повертається у відкриту
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Перевірка блокування реєстрації дубліката пошти."""
    payload = {
        "email": "duplicate@example.com",
        "password": "SecurePassword123!",
    }

    # Перша реєстрація
    first_resp = await client.post(f"{AUTH_PREFIX}/register", json=payload)
    assert first_resp.status_code == 201

    # Спроба зареєструвати той самий email вдруге
    second_resp = await client.post(f"{AUTH_PREFIX}/register", json=payload)
    assert second_resp.status_code in (400, 409)


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Тест отримання JWT токена через OAuth2 form-data."""
    email = "login_user@example.com"
    password = "CorrectPassword123!"

    # Створюємо користувача
    register_resp = await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": password},
    )
    assert register_resp.status_code == 201

    # Авторизуємося (OAuth2 очікує data типу application/x-www-form-urlencoded)
    login_resp = await client.post(
        f"{AUTH_PREFIX}/login",
        data={"username": email, "password": password},
    )

    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data.get("token_type") == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    """Перевірка відхилення входу з неправильним паролем."""
    email = "wrong_pwd@example.com"
    password = "RealPassword123!"

    await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": password},
    )

    login_resp = await client.post(
        f"{AUTH_PREFIX}/login",
        data={"username": email, "password": "WrongPassword!"},
    )

    assert login_resp.status_code in (400, 401)
