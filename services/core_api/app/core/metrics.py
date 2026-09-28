"""Prometheus-метрики core_api.

Prometheus раз на кілька секунд забирає GET /metrics і зберігає значення
як часові ряди; Grafana будує з них графіки.
"""

import time

from prometheus_client import Counter, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Кількість HTTP-запитів",
    ["method", "handler", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Час обробки HTTP-запиту",
    ["method", "handler"],
)
EMBEDDING_DURATION = Histogram(
    "embedding_duration_seconds",
    "Час обчислення ембеддингу",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)


def route_template(scope: Scope) -> str:
    """Повертає шаблон маршруту запиту: /api/v1/items/{item_id}.

    Нові версії FastAPI кладуть у scope["route"] шлях відносно вкладеного
    роутера (/items/{item_id}), тому префікс відновлюємо з реального шляху.
    """
    route = scope.get("route")
    template = getattr(route, "path_format", None)
    if template is None:
        return "unmatched"

    params = {key: str(value) for key, value in scope.get("path_params", {}).items()}
    try:
        concrete = template.format(**params)
    except (KeyError, IndexError):
        return template

    path = scope["path"]
    prefix = path[: -len(concrete)] if path.endswith(concrete) else ""
    return prefix + template


class PrometheusMiddleware:
    """ASGI-middleware: рахує запити і їх тривалість для кожного ендпоінта."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == "/metrics":
            await self.app(scope, receive, send)
            return

        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        start = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Мітка handler — шаблон маршруту (/api/v1/items/{item_id}), а не
            # реальний шлях: інакше кожен id створював би окремий часовий ряд
            handler = route_template(scope)
            method = scope["method"]
            HTTP_REQUESTS.labels(method, handler, str(status_code)).inc()
            HTTP_REQUEST_DURATION.labels(method, handler).observe(
                time.perf_counter() - start
            )
