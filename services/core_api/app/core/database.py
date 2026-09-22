from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# 1. Асинхронний рушій підключення до БД (Engine)
engine = create_async_engine(
    settings.async_database_url,
    echo=False,  # Якщо True — виводитиме всі сирі SQL-запити в консоль (зручно для дебагу)
    future=True,
    pool_size=10,  # Базова кількість відкритих з'єднань у пулі
    max_overflow=20,  # Скільки додаткових з'єднань можна відкрити при піковому навантаженні
)

# 2. Фабрика асинхронних сесій
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Щоб атрибути об'єктів залишалися доступними після commit
)


# 3. Базовий клас для всіх моделей (Base)
class Base(DeclarativeBase):
    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
