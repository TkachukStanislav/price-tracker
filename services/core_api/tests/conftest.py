import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

# Додай це у верхній блок імпортів conftest.py:
import app.models  # noqa: F401 (або конкретні моделі: from app.models.user import User)

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base, get_async_session
from app.main import app

# Використовуємо тестову URL із змінних середовища або дефолтне значення
TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://test_user:test_password@localhost:5432/test_db",
)

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    """Створює структуру таблиць перед початком тестів і видаляє після."""
    async with test_engine.begin() as conn:
        # Увімкнення розширення vector (для pgvector)
        await conn.execute(
            Base.metadata.schema and "" or "CREATE EXTENSION IF NOT EXISTS vector;"
        )
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Надає окрему транзакційну сесію для кожного тесту."""
    async with TestAsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Створює тестовий HTTP-клієнт із підміною сесії бази та моком RabbitMQ."""

    async def _override_get_async_session():
        yield db_session

    app.dependency_overrides[get_async_session] = _override_get_async_session

    # Заглушаємо запуск фонових задач RabbitMQ, щоб тести не шукали брокер
    with (
        patch("app.core.rabbitmq.rabbitmq_client.connect", new_callable=AsyncMock),
        patch("app.core.rabbitmq.rabbitmq_client.close", new_callable=AsyncMock),
        patch(
            "app.services.price_consumer.price_update_consumer.start",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.price_consumer.price_update_consumer.stop",
            new_callable=AsyncMock,
        ),
        patch("app.services.scheduler.price_scheduler.start", new_callable=AsyncMock),
        patch("app.services.scheduler.price_scheduler.stop", new_callable=AsyncMock),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()
