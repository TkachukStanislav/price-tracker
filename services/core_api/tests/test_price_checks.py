from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.item import TrackedItem
from app.models.user import User
from app.services.price_checks import dispatch_price_checks
from app.worker.celery_app import celery_app
from app.worker.tasks import dispatch_price_checks_task


async def test_dispatch_price_checks_publishes_every_item(db_session: AsyncSession):
    user = User(email="dispatch@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    items = [
        TrackedItem(
            title=f"Товар {i}",
            ticker_or_url=f"https://example.com/{i}",
            target_price=100.0,
            owner_id=user.id,
        )
        for i in range(3)
    ]
    db_session.add_all(items)
    await db_session.flush()
    publish = AsyncMock()

    count = await dispatch_price_checks(db_session, publish)

    assert count == 3
    assert publish.await_count == 3
    queues = {call.args[0] for call in publish.await_args_list}
    assert queues == {settings.SCRAPER_QUEUE_NAME}
    published_ids = {call.args[1]["item_id"] for call in publish.await_args_list}
    assert published_ids == {item.id for item in items}


async def test_dispatch_price_checks_with_no_items(db_session: AsyncSession):
    publish = AsyncMock()

    count = await dispatch_price_checks(db_session, publish)

    assert count == 0
    publish.assert_not_awaited()


def test_beat_schedules_price_checks():
    entry = celery_app.conf.beat_schedule["dispatch-price-checks"]

    # Назва в розкладі має збігатися з назвою зареєстрованої задачі
    assert entry["task"] == dispatch_price_checks_task.name
    assert entry["schedule"] == settings.PRICE_CHECK_INTERVAL_SECONDS
