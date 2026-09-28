import pytest

from app.services.scraper import PriceScraper, parse_price


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
