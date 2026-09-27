[![CI Pipeline](https://github.com/TkachukStanislav/price-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/TkachukStanislav/price-tracker/actions/workflows/ci.yml)

# ⚡ Distributed Price Tracker & Semantic Deduplication Engine

Подієво-орієнтована мікросервісна система для відстеження цін у реальному часі з автономним семантичним дедуплікатором товарів на базі PostgreSQL (`pgvector`) та локальних ONNX-ембеддингів.

---

## 💡 Яку проблему вирішує проєкт?

1. **Проблема моніторингу цін у масштабі:** Синхронний парсинг товарів блокує REST API та швидко призводить до падіння під навантаженням.
   * **Рішення:** Архітектура побудована на чергах задач (RabbitMQ) та фонових воркерах, що повністю ізолює API від затримок веб-скрапінгу.
2. **Семантичні дублікати різними мовами:** Традиційний `SQL LIKE` або точний пошук не можуть зв'язати між собою позиції на кшталт *"Apple iPhone 15 Pro 128GB Black Titanium"* та *"Смартфон Apple iPhone 15 Pro 128GB чорний титан"*.
   * **Рішення:** Векторизація назв через `fastembed` на льоту та векторний пошук косинусної відстані прямо всередині PostgreSQL (`pgvector`). Схожість фіксується автоматично (косинусна відстань $\approx 0.15$).

---

## 🛠 Стек технологій

* **Backend:** Python 3.11+, FastAPI (повністю асинхронний пайплайн), Pydantic v2
* **База даних та вектори:** PostgreSQL 16, розширення `pgvector`, SQLAlchemy 2.0 (asyncpg), міграції Alembic
* **ML / Ембеддинги:** `fastembed` (локальний ONNX Runtime, без платних зовнішніх API на кшталт OpenAI)
* **Асинхронний брокер та кеш:** RabbitMQ, Redis
* **Інфраструктура та UI:** Docker Compose, інтегрований Tailwind CSS дашборд

---

## 🏗 Архітектурна схема

```text
[ Клієнт / Браузер ]
         │
         ▼
[ FastAPI Core API ] ──( Генерація вектора: fastembed )
         │                               │
         │ (pgvector cosine search)      ▼
         ├──────────────────────► [ PostgreSQL 16 ]
         │
         ▼ (Публікація задачі)
    [ RabbitMQ ]
         │
         ▼ (Споживання черги)
[ Scraper Worker ] ──► [ Зовнішні ресурси / Магазини ]
```
---

## Швидкий запуск

```bash
git clone [https://github.com/TkachukStanislav/price-tracker.git](https://github.com/TkachukStanislav/price-tracker.git)
cd price-tracker
cp .env.example .env
docker compose up --build -d
docker compose exec core_api alembic upgrade head
```

Точки доступу
Веб-дашборд: http://localhost:8000/
Swagger документація API: http://localhost:8000/docs
RabbitMQ Dashboard: http://localhost:15672 (Логін/Пароль: guest / guest)
