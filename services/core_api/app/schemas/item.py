from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrackedItemBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    ticker_or_url: str = Field(min_length=1, max_length=500)
    target_price: float = Field(gt=0)


# Схема для створення товару
class TrackedItemCreate(TrackedItemBase):
    pass


# Схема для оновлення товару (ціни або назви)
class TrackedItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    target_price: float | None = Field(default=None, gt=0)


# Схема для відповіді API
class TrackedItemResponse(TrackedItemBase):
    id: int
    owner_id: int
    current_price: float | None = None
    price_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Запис історії цін
class PriceHistoryResponse(BaseModel):
    price: float
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Схожий товар разом із косинусною відстанню до вихідного
class SimilarItemResponse(BaseModel):
    item: TrackedItemResponse
    distance: float
