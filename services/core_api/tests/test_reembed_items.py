import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import TrackedItem
from app.models.user import User
from app.scripts.reembed_items import reembed_all_items
from app.services.embedding_service import embedding_service


async def test_reembed_all_items_replaces_stale_vectors(db_session: AsyncSession):
    # Arrange: товари з "застарілими" векторами, наче від іншої моделі
    user = User(email="reembed@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    stale_vector = [0.1] * 384
    titles = ["Apple iPhone 15 Pro", "Пральна машина Samsung", "Кавоварка DeLonghi"]
    items = [
        TrackedItem(
            title=title,
            ticker_or_url="https://example.com",
            target_price=100.0,
            owner_id=user.id,
            title_embedding=stale_vector,
        )
        for title in titles
    ]
    db_session.add_all(items)
    await db_session.commit()

    # Act: batch_size=2 — перевіряємо, що пагінація проходить кілька пачок
    processed = await reembed_all_items(db_session, batch_size=2)

    # Assert
    assert processed == len(titles)
    for item in items:
        await db_session.refresh(item)
        expected = embedding_service.generate_embedding(item.title)
        assert list(item.title_embedding) == pytest.approx(expected, abs=1e-6)
