from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.messaging import (
    MAX_RETRIES,
    RETRY_HEADER,
    PermanentMessageError,
    handle_with_retry,
    parse_json,
)

QUEUE = "test_queue"


def make_message(body: bytes = b"{}", retry_count: int | None = None) -> MagicMock:
    message = MagicMock()
    message.body = body
    message.headers = {} if retry_count is None else {RETRY_HEADER: retry_count}
    message.message_id = "msg-1"
    message.content_type = "application/json"
    message.ack = AsyncMock()
    message.reject = AsyncMock()
    return message


def make_channel() -> MagicMock:
    channel = MagicMock()
    channel.default_exchange.publish = AsyncMock()
    return channel


async def test_success_acks_message():
    message, channel = make_message(), make_channel()

    await handle_with_retry(message, channel, QUEUE, AsyncMock())

    message.ack.assert_awaited_once()
    channel.default_exchange.publish.assert_not_awaited()


async def test_failure_sends_to_retry_queue_with_incremented_counter():
    message, channel = make_message(retry_count=1), make_channel()

    await handle_with_retry(
        message, channel, QUEUE, AsyncMock(side_effect=ConnectionError)
    )

    retry_message = channel.default_exchange.publish.await_args.args[0]
    assert channel.default_exchange.publish.await_args.kwargs["routing_key"] == (
        f"{QUEUE}.retry"
    )
    assert retry_message.headers[RETRY_HEADER] == 2
    assert retry_message.message_id == "msg-1"
    message.ack.assert_awaited_once()
    message.reject.assert_not_awaited()


async def test_exhausted_retries_go_to_dlq():
    message, channel = make_message(retry_count=MAX_RETRIES), make_channel()

    await handle_with_retry(
        message, channel, QUEUE, AsyncMock(side_effect=ConnectionError)
    )

    # reject без requeue: RabbitMQ перекладе повідомлення в <queue>.dlq
    message.reject.assert_awaited_once_with(requeue=False)
    channel.default_exchange.publish.assert_not_awaited()


async def test_permanent_error_goes_straight_to_dlq():
    message, channel = make_message(), make_channel()

    await handle_with_retry(
        message, channel, QUEUE, AsyncMock(side_effect=PermanentMessageError)
    )

    message.reject.assert_awaited_once_with(requeue=False)
    channel.default_exchange.publish.assert_not_awaited()


@pytest.mark.parametrize("body", [b"not json", b"\xff\xfe", b"[1, 2]"])
def test_parse_json_rejects_poison_messages(body: bytes):
    with pytest.raises(PermanentMessageError):
        parse_json(make_message(body))
