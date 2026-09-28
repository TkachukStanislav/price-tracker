"""Prometheus-метрики scraper_service (віддаються на GET /metrics)."""

from prometheus_client import Counter, Histogram

SCRAPE_RESULTS = Counter(
    "scrape_results_total",
    "Результати отримання ціни",
    # success | not_found | fetch_error | unsupported | cache_hit
    ["result"],
)
SCRAPE_DURATION = Histogram(
    "scrape_duration_seconds",
    "Час завантаження і розбору сторінки товару",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10),
)
PRICE_ALERTS = Counter(
    "price_alerts_total",
    "Опубліковані сповіщення про зниження ціни",
)
