from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.messaging import PermanentMessageError
from app.models.item import TrackedItem
from app.models.user import User
from app.services.price_consumer import apply_price_update

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


@pytest.fixture
async def item(db_session: AsyncSession) -> TrackedItem:
    user = User(email="consumer@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    item = TrackedItem(
        title="Товар",
        ticker_or_url="https://example.com",
        target_price=100.0,
        owner_id=user.id,
    )
    db_session.add(item)
    await db_session.commit()
    return item


def event(item_id: int, price: float, checked_at: datetime) -> dict:
    return {
        "item_id": item_id,
        "current_price": price,
        "checked_at": checked_at.isoformat(),
    }


async def test_price_update_is_applied(db_session: AsyncSession, item: TrackedItem):
    result = await apply_price_update(db_session, event(item.id, 950.0, NOW))

    await db_session.refresh(item)
    assert result == "updated"
    assert item.current_price == 950.0
    assert item.price_checked_at == NOW


async def test_duplicate_event_is_ignored(db_session: AsyncSession, item: TrackedItem):
    await apply_price_update(db_session, event(item.id, 950.0, NOW))

    # Та сама подія вдруге (RabbitMQ доставив повторно)
    result = await apply_price_update(db_session, event(item.id, 950.0, NOW))

    assert result == "stale"


async def test_older_event_does_not_overwrite_newer(
    db_session: AsyncSession, item: TrackedItem
):
    await apply_price_update(db_session, event(item.id, 800.0, NOW))

    # Подія, отримана раніше, прийшла пізніше (наприклад, після повтору)
    result = await apply_price_update(
        db_session, event(item.id, 1200.0, NOW - timedelta(minutes=5))
    )

    await db_session.refresh(item)
    assert result == "stale"
    assert item.current_price == 800.0


async def test_event_for_missing_item(db_session: AsyncSession):
    result = await apply_price_update(db_session, event(999999, 100.0, NOW))

    assert result == "item_not_found"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"item_id": 1},
        {"item_id": "abc", "current_price": 1},
        {"item_id": 1, "current_price": "дорого"},
    ],
)
async def test_invalid_event_is_permanent_error(db_session: AsyncSession, payload):
    with pytest.raises(PermanentMessageError):
        await apply_price_update(db_session, payload)
