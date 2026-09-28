"""Налаштування логування: JSON у продакшені, звичайний текст у розробці.

JSON-рядок на кожен запис легко збирати й фільтрувати в Loki/ELK за полями
(service, level, logger, message_id...). Поля з logger.info(..., extra={...})
потрапляють у JSON окремими ключами.

Та сама копія модуля живе в кожному сервісі.
"""

import json
import logging
import sys
from datetime import UTC, datetime

TEXT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Стандартні атрибути LogRecord: усе інше прийшло через extra
_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging(service: str, log_format: str = "text", level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        handler.setFormatter(JsonFormatter(service))
    else:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT))

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # uvicorn налаштовує власні обробники; прибираємо їх, щоб його логи
    # (зокрема access-лог) ішли через наш формат
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
