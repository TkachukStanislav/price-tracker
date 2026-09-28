from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PriceHistory(Base):
    """Зміни ціни товару. Рядок додається, лише коли ціна відрізняється від попередньої."""

    __tablename__ = "price_history"
    __table_args__ = (
        # Типовий запит: історія одного товару, найновіші спочатку
        Index("ix_price_history_item_id_checked_at", "item_id", "checked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracked_items.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
