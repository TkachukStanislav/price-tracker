from unittest.mock import AsyncMock

import fakeredis
import pytest

from app.services.worker import NotificationWorker

PAYLOAD = {
    "item_id": 7,
    "owner_id": 1,
    "ticker_or_url": "https://shop.ua/p",
    "current_price": 899.0,
    "target_price": 900.0,
}


@pytest.fixture
def worker() -> NotificationWorker:
    worker = NotificationWorker(fakeredis.FakeAsyncRedis(decode_responses=True))
    worker.send_notification = AsyncMock()
    return worker


async def test_first_notification_is_sent(worker: NotificationWorker):
    assert await worker.notify_once(PAYLOAD) is True
    worker.send_notification.assert_awaited_once_with(PAYLOAD)


async def test_duplicate_notification_is_skipped(worker: NotificationWorker):
    await worker.notify_once(PAYLOAD)

    # Те саме повідомлення доставлено вдруге
    assert await worker.notify_once(PAYLOAD) is False
    worker.send_notification.assert_awaited_once()


async def test_new_price_is_notified_again(worker: NotificationWorker):
    await worker.notify_once(PAYLOAD)

    assert await worker.notify_once({**PAYLOAD, "current_price": 850.0}) is True
    assert worker.send_notification.await_count == 2


async def test_failed_send_can_be_retried(worker: NotificationWorker):
    worker.send_notification.side_effect = [ConnectionError, None]

    with pytest.raises(ConnectionError):
        await worker.notify_once(PAYLOAD)

    # Позначку знято, тому повтор надсилає сповіщення
    assert await worker.notify_once(PAYLOAD) is True
