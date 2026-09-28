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
* **ML / Ембеддинги:** `fastembed` з мультимовною моделлю `paraphrase-multilingual-MiniLM-L12-v2` (локальний ONNX Runtime, без платних зовнішніх API на кшталт OpenAI)
* **Асинхронний брокер та кеш:** RabbitMQ, Redis
* **Інфраструктура та UI:** Docker Compose, інтегрований Tailwind CSS дашборд

---

## 🏗 Архітектурна схема

```text
[ Клієнт / Браузер ]
         │
         ▼
[ core_api (FastAPI) ] ──► PostgreSQL 16 + pgvector (HNSW)
         │ нові товари
         ▼
 [ celery_beat ] ─(раз на хвилину)─► [ celery_worker ] ─┐
                                                        ▼
                                  RabbitMQ: price_scraping_tasks
                                                        │
                                                        ▼
                     [ scraper_service ] ◄──► Redis (кеш цін) ──► магазини
                        │                         │
       price_updated_events               price_alert_notifications
                        ▼                         ▼
              [ price_consumer ]          [ notifier_service ]
               (current_price у БД)        (сповіщення)
```

### Процеси

| Сервіс | Що робить | Масштабування |
|---|---|---|
| `core_api` | Лише HTTP API | Горизонтально, скільки завгодно копій |
| `price_consumer` | Слухає `price_updated_events`, пише ціни в БД | Кілька копій ділять чергу між собою |
| `celery_worker` | Виконує фонові задачі Celery | `docker compose up -d --scale celery_worker=3` |
| `celery_beat` | Розклад: раз на `PRICE_CHECK_INTERVAL_SECONDS` ставить товари на перевірку | **Рівно один екземпляр** |
| `scraper_service` | Отримує ціни зі сторінок, кешує в Redis | Кілька копій ділять чергу |
| `notifier_service` | Надсилає сповіщення про зниження ціни | Кілька копій ділять чергу |

Фонові процеси винесені з API, щоб запуск кількох копій API не дублював розклад перевірок. Celery використовується для запланованих задач усередині сервісу, а обмін подіями між сервісами йде напряму через RabbitMQ (aio-pika).

---

## Швидкий запуск

```bash
git clone https://github.com/TkachukStanislav/price-tracker.git
cd price-tracker
cp .env.example .env
docker compose up --build -d
docker compose exec core_api alembic upgrade head
```

Після зміни моделі ембеддингів (`EMBEDDING_MODEL`) перерахуйте вектори наявних товарів:

```bash
docker compose exec core_api python -m app.scripts.reembed_items
```

Точки доступу
Веб-дашборд: http://localhost:8000/
Swagger документація API: http://localhost:8000/docs
RabbitMQ Dashboard: http://localhost:15672 (Логін/Пароль: guest / guest)
