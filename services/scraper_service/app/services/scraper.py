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


def parse_price(raw_text: str) -> float | None:
    """Дістає число з тексту ціни: '12 999,50 ₴' -> 12999.5."""
    # Прибираємо пробіли між розрядами, включно з нерозривним пробілом
    cleaned = re.sub(r"[\s ]", "", raw_text)
    match = re.search(r"\d+(?:[.,]\d{1,2})?", cleaned)
    if match is None:
        return None
    return float(match.group().replace(",", "."))


class PriceScraper:
    @staticmethod
    async def fetch_price(ticker_or_url: str) -> float | None:
        """Повертає ціну зі сторінки або None, якщо отримати її не вдалося."""
        if not ticker_or_url.startswith(("http://", "https://")):
            logger.warning("Непідтримуване джерело ціни: %s", ticker_or_url)
            SCRAPE_RESULTS.labels("unsupported").inc()
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(ticker_or_url, headers=HEADERS)
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Не вдалося завантажити %s: %s", ticker_or_url, e)
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
