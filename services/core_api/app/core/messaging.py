"""Надійна обробка повідомлень RabbitMQ: повтори із затримкою і DLQ.

Для кожної черги <name> створюються ще дві:

    <name>.retry — повідомлення лежить там RETRY_DELAY_MS, після чого
                   RabbitMQ сам повертає його в <name> (TTL + dead-letter)
    <name>.dlq   — повідомлення, які не вдалося обробити за MAX_RETRIES
                   спроб, або «отруйні» (битий JSON). Лежать там для аналізу

    обробник впав ──► спроба < MAX_RETRIES? ──так──► <name>.retry ──(5 с)──► <name>
                                         └──ні───► <name>.dlq

Та сама копія модуля живе в core_api, scraper_service і notifier_service:
кожен сервіс збирається окремо, спільної бібліотеки між ними немає.
Черги мають оголошуватися з однаковими аргументами і видавцем, і споживачем,
інакше RabbitMQ відповість PRECONDITION_FAILED.
"""

import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractQueue
from prometheus_client import Counter

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_MS = 5000
RETRY_HEADER = "x-retry-count"

MESSAGES_RETRIED = Counter(
    "messages_retried_total",
    "Повідомлення, відправлені на повторну обробку",
    ["queue"],
)
MESSAGES_DEAD_LETTERED = Counter(
    "messages_dead_lettered_total",
    "Повідомлення, відправлені в DLQ",
    ["queue"],
)


class PermanentMessageError(Exception):
    """Помилка, яку повтор не виправить (битий JSON тощо): одразу в DLQ."""


async def declare_queue_with_retry(
    channel: AbstractChannel, name: str
) -> AbstractQueue:
    await channel.declare_queue(f"{name}.dlq", durable=True)
    await channel.declare_queue(
        f"{name}.retry",
        durable=True,
        arguments={
            "x-message-ttl": RETRY_DELAY_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": name,
        },
    )
    return await channel.declare_queue(
        name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": f"{name}.dlq",
        },
    )


def build_message(payload: dict[str, Any]) -> aio_pika.Message:
    return aio_pika.Message(
        body=json.dumps(payload).encode("utf-8"),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        content_type="application/json",
        # Унікальний id: допомагає відстежити повідомлення в логах і повторах
        message_id=str(uuid.uuid4()),
    )


def parse_json(message: AbstractIncomingMessage) -> dict[str, Any]:
    try:
        payload = json.loads(message.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise PermanentMessageError("Тіло повідомлення не є JSON") from e
    if not isinstance(payload, dict):
        raise PermanentMessageError("Очікувався JSON-об'єкт")
    return payload


async def handle_with_retry(
    message: AbstractIncomingMessage,
    channel: AbstractChannel,
    queue_name: str,
    handler: Callable[[AbstractIncomingMessage], Awaitable[None]],
) -> None:
    """Викликає handler; при помилці відправляє повідомлення на повтор або в DLQ.

    Повідомлення підтверджується (ack) лише після того, як копія опинилась у
    черзі повторів. Якщо процес впаде між цими кроками, повідомлення прийде
    ще раз — тому обробники мають бути ідемпотентними.
    """
    # Поля для пошуку в JSON-логах: усі записи про одне повідомлення
    log_fields = {"queue": queue_name, "message_id": message.message_id}
    try:
        await handler(message)
    except PermanentMessageError:
        logger.exception(
            "Повідомлення %s не можна обробити", message.message_id, extra=log_fields
        )
        MESSAGES_DEAD_LETTERED.labels(queue_name).inc()
        await message.reject(requeue=False)
        return
    except Exception:
        attempt = int((message.headers or {}).get(RETRY_HEADER, 0)) + 1
        if attempt > MAX_RETRIES:
            logger.exception(
                "Повідомлення %s: вичерпано %d спроб, відправляю в DLQ",
                message.message_id,
                MAX_RETRIES,
                extra=log_fields,
            )
            MESSAGES_DEAD_LETTERED.labels(queue_name).inc()
            await message.reject(requeue=False)
            return

        logger.warning(
            "Повідомлення %s: помилка обробки, спроба %d з %d через %d мс",
            message.message_id,
            attempt,
            MAX_RETRIES,
            RETRY_DELAY_MS,
            exc_info=True,
            extra={**log_fields, "attempt": attempt},
        )
        retry_message = aio_pika.Message(
            body=message.body,
            headers={**(message.headers or {}), RETRY_HEADER: attempt},
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type=message.content_type,
            message_id=message.message_id,
        )
        await channel.default_exchange.publish(
            retry_message, routing_key=f"{queue_name}.retry"
        )
        MESSAGES_RETRIED.labels(queue_name).inc()
        await message.ack()
        return

    await message.ack()
