import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.core.metrics import SCRAPE_RESULTS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
PRICE_CLASS_PATTERN = re.compile(r"price|product-price|cost", re.IGNORECASE)
# Сервер перевантажений або обмежує частоту запитів: варто повторити пізніше
TEMPORARY_STATUS_CODES = {429, 500, 502, 503, 504}


def parse_price(raw_text: str) -> float | None:
    """Дістає число з тексту ціни: '12 999,50 ₴' -> 12999.5."""
    # Прибираємо пробіли між розрядами, включно з нерозривним пробілом
    cleaned = re.sub(r"[\s ]", "", raw_text)
    match = re.search(r"\d+(?:[.,]\d{1,2})?", cleaned)
    if match is None:
        return None
    return float(match.group().replace(",", "."))


class TemporaryScrapeError(Exception):
    """Тимчасова помилка (таймаут, 5xx, 429): має сенс спробувати пізніше."""


class PriceScraper:
    @staticmethod
    async def fetch_price(
        ticker_or_url: str, client: httpx.AsyncClient | None = None
    ) -> float | None:
        """Повертає ціну зі сторінки або None, якщо на сторінці її немає.

        Тимчасові мережеві збої піднімають TemporaryScrapeError, щоб
        повідомлення пішло на повтор. Постійні (404, немає ціни) дають None.
        """
        if not ticker_or_url.startswith(("http://", "https://")):
            logger.warning("Непідтримуване джерело ціни: %s", ticker_or_url)
            SCRAPE_RESULTS.labels("unsupported").inc()
            return None

        http = client or httpx.AsyncClient(timeout=10.0, follow_redirects=True)
        try:
            response = await http.get(ticker_or_url, headers=HEADERS)
        except httpx.TransportError as e:
            SCRAPE_RESULTS.labels("temporary_error").inc()
            raise TemporaryScrapeError(f"{ticker_or_url}: {e!r}") from e
        finally:
            if client is None:
                await http.aclose()

        if response.status_code in TEMPORARY_STATUS_CODES:
            SCRAPE_RESULTS.labels("temporary_error").inc()
            raise TemporaryScrapeError(f"{ticker_or_url}: HTTP {response.status_code}")
        if response.is_error:
            logger.warning(
                "Не вдалося завантажити %s: HTTP %s",
                ticker_or_url,
                response.status_code,
            )
            SCRAPE_RESULTS.labels("fetch_error").inc()
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        price_element = soup.find(class_=PRICE_CLASS_PATTERN)
        if price_element is None:
            logger.warning("Ціну не знайдено на сторінці %s", ticker_or_url)
            SCRAPE_RESULTS.labels("not_found").inc()
            return None

        price = parse_price(price_element.get_text())
        SCRAPE_RESULTS.labels("success" if price is not None else "not_found").inc()
        return price
