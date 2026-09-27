import pytest
from app.services.embedding_service import embedding_service
import numpy as np


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

    # Рахуємо схожість
    similarity_same = cosine_similarity(vec_a, vec_b)
    similarity_diff = cosine_similarity(vec_a, vec_diff)

# 3. Assert:
    # Схожі товари мають високу подібність
    assert similarity_same > 0.80, f"Очікували високу схожість, отримали {similarity_same}"

    # Сторонній товар помітно нижчий за порогом
    assert similarity_diff < 0.65, f"Очікували низьку схожість, отримали {similarity_diff}"

    # Різниця між схожим і несхожим товаром суттєва (> 0.15)
    assert (similarity_same - similarity_diff) > 0.15