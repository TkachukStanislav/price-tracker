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

---

## 🛡 Надійність обробки повідомлень

Кожна робоча черга `<name>` має дві допоміжні:

```text
обробник впав ──► спроба ≤ 3? ──так──► <name>.retry ──(через 5 с)──► <name>
                            └──ні───► <name>.dlq  (для ручного аналізу)
```

* **Тимчасові помилки** (таймаут, 5xx, 429 від магазину, недоступна БД) повторюються до 3 разів із затримкою 5 с. Затримку робить сам RabbitMQ: TTL черги `.retry` + dead-letter назад у робочу чергу.
* **Постійні помилки** (битий JSON, некоректні поля) одразу йдуть у `.dlq`, бо повтор нічого не змінить.
* **Ідемпотентність**: повідомлення може прийти двічі (at-least-once), тому обробники це витримують:
  * `price_consumer` пише ціну одним `UPDATE ... WHERE price_checked_at < :checked_at`: дублікати й застарілі події ігноруються, навіть якщо їх одночасно обробляють кілька споживачів;
  * `notifier_service` ставить у Redis `SET NX` ключ `notified:<товар>:<ціна>` на добу: те саме сповіщення не надсилається двічі.

Черги `.dlq` видно на дашборді Grafana та в RabbitMQ UI.

> Якщо черги вже існували без DLQ (стара версія), RabbitMQ відповість `PRECONDITION_FAILED`: аргументи наявної черги змінити не можна. Зупиніть сервіси й видаліть старі черги: `docker compose exec rabbitmq rabbitmqctl delete_queue price_scraping_tasks` (так само `price_updated_events`, `price_alert_notifications`).

---

## ⚡ Redis

| Для чого | Як працює |
|---|---|
| **Rate limiting** логіну (5 спроб/хв) і реєстрації (10/год) з однієї IP | `INCR` + `EXPIRE NX` в одній транзакції; понад ліміт — `429` з `Retry-After` |
| **Кеш** `GET /items/{id}/similar` (5 хв) | Версіоновані ключі `similar:<user>:v<версія>:...`; будь-яка зміна товарів користувача робить `INCR items_version:<user>`, і старий кеш більше не читається |
| **Кеш цін** у scraper (10 хв) | Один товар у кількох користувачів — один запит до магазину |
| **Дедуплікація сповіщень** | `SET NX notified:<товар>:<ціна>` на добу |
| **Result backend Celery** | Статуси й результати задач |

Якщо Redis недоступний, API працює далі (fail open): rate limit і кеш просто пропускаються, а в лог пишеться попередження.

---

## 📈 Моніторинг

| Що | Адреса |
|---|---|
| Grafana, дашборд **Price Tracker** | http://localhost:3000 (admin / admin) |
| Prometheus | http://localhost:9090 |
| Сирі метрики API | http://localhost:8000/metrics |

Prometheus кожні 15 секунд забирає `/metrics` з `core_api`, `price_consumer`, `scraper_service`, `notifier_service` і RabbitMQ (вбудований плагін `rabbitmq_prometheus`). Дашборд і datasource Grafana підключаються автоматично з `monitoring/grafana`.

Основні метрики:

| Метрика | Що показує |
|---|---|
| `http_requests_total`, `http_request_duration_seconds` | Трафік, коди відповідей і затримки API за шаблоном маршруту |
| `scrape_results_total{result}` | Скільки цін отримано / взято з кешу / не вдалося отримати |
| `price_updates_total{result}` | Оновлення цін, записані в БД |
| `rabbitmq_queue_messages_ready` | Черги, що накопичуються (споживачі не встигають) |
| `embedding_duration_seconds` | Час обчислення векторів |
