from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class TrackedItem(Base):
    __tablename__ = "tracked_items"
    __table_args__ = (
        # HNSW-індекс для швидкого пошуку найближчих векторів за косинусною відстанню
        Index(
            "ix_tracked_items_title_embedding_hnsw",
            "title_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"title_embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker_or_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    title_embedding = mapped_column(Vector(384), nullable=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner: Mapped["User"] = relationship(
        "User",
        back_populates="items",
    )
