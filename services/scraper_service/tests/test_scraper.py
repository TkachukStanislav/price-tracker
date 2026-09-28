import httpx
import pytest

from app.services.scraper import PriceScraper, TemporaryScrapeError, parse_price


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("1299", 1299.0),
        ("12 999 ₴", 12999.0),
        ("12 999 грн", 12999.0),
        ("999,50 ₴", 999.5),
        ("$1499.99", 1499.99),
        ("Ціна: 450 грн", 450.0),
    ],
)
def test_parse_price(raw_text: str, expected: float):
    assert parse_price(raw_text) == expected


@pytest.mark.parametrize("raw_text", ["", "Немає в наявності", "₴"])
def test_parse_price_returns_none_without_digits(raw_text: str):
    assert parse_price(raw_text) is None


async def test_fetch_price_rejects_non_url():
    assert await PriceScraper.fetch_price("AAPL") is None


def mock_client(handler) -> httpx.AsyncClient:
    """HTTP-клієнт, який замість мережі віддає відповідь з handler."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_price_parses_page():
    html = '<div class="product-price">12 999 ₴</div>'
    client = mock_client(lambda request: httpx.Response(200, text=html))

    assert await PriceScraper.fetch_price("https://shop.ua/p", client) == 12999.0


async def test_fetch_price_without_price_element_returns_none():
    client = mock_client(lambda request: httpx.Response(200, text="<p>Товар</p>"))

    assert await PriceScraper.fetch_price("https://shop.ua/p", client) is None


async def test_fetch_price_not_found_page_returns_none():
    # 404 — постійна помилка: повтор не допоможе
    client = mock_client(lambda request: httpx.Response(404))

    assert await PriceScraper.fetch_price("https://shop.ua/p", client) is None


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_fetch_price_server_errors_are_temporary(status: int):
    client = mock_client(lambda request: httpx.Response(status))

    with pytest.raises(TemporaryScrapeError):
        await PriceScraper.fetch_price("https://shop.ua/p", client)


async def test_fetch_price_timeout_is_temporary():
    def timeout(request):
        raise httpx.ConnectTimeout("timeout", request=request)

    with pytest.raises(TemporaryScrapeError):
        await PriceScraper.fetch_price("https://shop.ua/p", mock_client(timeout))
