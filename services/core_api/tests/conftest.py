import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import app.models
from app.core.database import Base, get_async_session
from app.main import app

TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://test_user:test_password@localhost:5432/test_db",
)

# NullPool guarantees connections are not reused across distinct event loops
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
    future=True,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    """Створює структуру таблиць та розширення vector перед початком тестів."""
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Надає транзакційну сесію з savepoint для повної ізоляції кожного тесту."""
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            if trans.is_active:
                await trans.rollback()


@pytest.fixture
def mock_publish():
    """Підміняє публікацію в RabbitMQ і дає тесту доступ до моку."""
    with patch(
        "app.core.rabbitmq.rabbitmq_client.publish_message",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, mock_publish: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    """Створює тестовий клієнт із підміненою сесією та замоканим RabbitMQ."""

    async def _override_get_async_session():
        yield db_session

    app.dependency_overrides[get_async_session] = _override_get_async_session

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
