import numpy as np
import pytest

from app.services.embedding_service import embedding_service
from app.services.item_service import SIMILARITY_MAX_DISTANCE


def test_embedding_output_structure():
    # 1. Arrange (Підготовка даних): вхідний текст
    text = "Apple iPhone 15 Pro 128GB"

    # 2. Act (Дія): викликаємо наш сервіс
    vector = embedding_service.generate_embedding(text)

    # 3. Assert (Перевірка очікувань):
    # Перевіряємо, що результат це список
    assert isinstance(vector, list)

    # Перевіряємо, що довжина вектора рівно 384 елементи
    assert len(vector) == 384

    # Перевіряємо, що перший елемент є числом з плаваючою крапкою
    assert isinstance(vector[0], float)


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    a = np.array(v1)
    b = np.array(v2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_semantic_similarity_deduplication():
    # 1. Arrange: Дві назви того самого телефону (навіть різними мовами) та абсолютно сторонній товар
    item_a = "Apple iPhone 15 Pro 128GB Black Titanium"
    item_b = "Смартфон Apple iPhone 15 Pro 128GB Black"
    unrelated_item = "Пральна машина автомат Samsung 7кг"

    # 2. Act: Отримуємо вектори
    vec_a = embedding_service.generate_embedding(item_a)
    vec_b = embedding_service.generate_embedding(item_b)
    vec_diff = embedding_service.generate_embedding(unrelated_item)

    # Рахуємо косинусну відстань
    distance_same = 1 - cosine_similarity(vec_a, vec_b)
    distance_diff = 1 - cosine_similarity(vec_a, vec_diff)

    # 3. Assert: той самий товар — в межах порогу, сторонній — за ним
    assert distance_same < SIMILARITY_MAX_DISTANCE, f"Відстань {distance_same}"
    assert distance_diff > SIMILARITY_MAX_DISTANCE, f"Відстань {distance_diff}"


async def test_async_embedding_matches_sync():
    text = "Apple iPhone 15 Pro 128GB"

    sync_vector = embedding_service.generate_embedding(text)
    async_vector = await embedding_service.generate_embedding_async(text)

    assert async_vector == sync_vector


@pytest.mark.parametrize(
    ("text_a", "text_b"),
    [
        ("Електрочайник", "Мікрохвильова піч"),
        ("Дитячий велосипед", "Зимова куртка"),
        ("Навушники Sony WH-1000XM5", "Кавоварка DeLonghi Magnifica"),
    ],
)
def test_different_ukrainian_items_are_not_similar(text_a: str, text_b: str):
    # Регресія: англомовна bge-small-en вважала різні українські товари схожими
    # (відстань "Електрочайник" ↔ "Мікрохвильова піч" була 0.18 < порогу 0.25)
    vec_a = embedding_service.generate_embedding(text_a)
    vec_b = embedding_service.generate_embedding(text_b)

    distance = 1 - cosine_similarity(vec_a, vec_b)

    assert distance > SIMILARITY_MAX_DISTANCE


def test_batch_embeddings_match_single():
    texts = ["Apple iPhone 15 Pro", "Пральна машина Samsung"]

    batch = embedding_service.generate_embeddings(texts)

    assert len(batch) == 2
    for text, vector in zip(texts, batch, strict=True):
        assert vector == pytest.approx(embedding_service.generate_embedding(text))
