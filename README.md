[![CI Pipeline](https://github.com/TkachukStanislav/price-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/TkachukStanislav/price-tracker/actions/workflows/ci.yml)

# ⚡ Price Tracker

Мікросервісна система відстеження цін: користувач додає товари, система періодично перевіряє ціни на сайтах магазинів, зберігає історію змін і надсилає сповіщення, коли ціна опускається до бажаної. Схожі товари (зокрема з назвами різними мовами) знаходяться векторним пошуком у PostgreSQL.

**Стек:** Python 3.11 · FastAPI · SQLAlchemy 2 (async) · PostgreSQL 16 + pgvector · Alembic · RabbitMQ · Celery · Redis · Prometheus · Grafana · Docker Compose · GitHub Actions

---

## Можливості

* **API товарів** з JWT-автентифікацією: CRUD, доступ лише до власних товарів.
* **Періодична перевірка цін**: Celery beat раз на хвилину ставить товари в чергу, scraper отримує ціни, результат записується в БД.
* **Історія цін**: зберігаються лише зміни ціни, `GET /items/{id}/price-history`.
* **Сповіщення** про досягнення бажаної ціни, без дублікатів.
* **Схожі товари** `GET /items/{id}/similar`: мультимовні ембеддинги + HNSW-індекс у pgvector. *"Apple iPhone 15 Pro 128GB"* і *"Смартфон Apple iPhone 15 Pro 128 ГБ"* знаходяться як схожі.
* **Надійність**: повтори із затримкою, dead-letter черги, ідемпотентні обробники.
* **Спостережуваність**: метрики Prometheus, готовий дашборд Grafana, JSON-логи.
* **Захист**: rate limiting логіну й реєстрації, bcrypt, обов'язковий `SECRET_KEY`.

---

## 🏗 Архітектура

```text
[ Клієнт / Браузер ]
         │
         ▼
[ core_api (FastAPI) ] ──► PostgreSQL 16 + pgvector (HNSW)      Redis
         │ нові товари                                     (rate limit, кеш)
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
         (ціна + історія в БД)         (сповіщення, дедуплікація)
```

| Сервіс | Що робить | Масштабування |
|---|---|---|
| `core_api` | Лише HTTP API | Горизонтально, скільки завгодно копій |
| `migrate` | Одноразово виконує `alembic upgrade head` перед стартом решти | — |
| `price_consumer` | Слухає `price_updated_events`, пише ціну та історію в БД | Кілька копій ділять чергу |
| `celery_worker` | Виконує фонові задачі Celery | `docker compose up -d --scale celery_worker=3` |
| `celery_beat` | Розклад: раз на `PRICE_CHECK_INTERVAL_SECONDS` ставить товари на перевірку | **Рівно один екземпляр** |
| `scraper_service` | Отримує ціни зі сторінок, кешує в Redis | Кілька копій ділять чергу |
| `notifier_service` | Надсилає сповіщення про зниження ціни | Кілька копій ділять чергу |

---

## 🔌 API

Повна документація: http://localhost:8000/docs

| Метод | Шлях | Опис |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Реєстрація (10 спроб/год з IP) |
| `POST` | `/api/v1/auth/login` | JWT-токен (5 спроб/хв з IP) |
| `POST` | `/api/v1/items/` | Додати товар для відстеження |
| `GET` | `/api/v1/items/` | Мої товари |
| `GET` / `PATCH` / `DELETE` | `/api/v1/items/{id}` | Товар (чужий → 404) |
| `GET` | `/api/v1/items/{id}/similar?limit=5` | Схожі товари за змістом назви |
| `GET` | `/api/v1/items/{id}/price-history?limit=100` | Історія змін ціни |
| `GET` | `/health`, `/metrics` | Стан сервісу, метрики Prometheus |

---

## 🚀 Швидкий запуск

```bash
git clone https://github.com/TkachukStanislav/price-tracker.git
cd price-tracker
cp .env.example .env
# Задайте SECRET_KEY у .env (мінімум 32 символи):
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build -d
```

Міграції БД виконуються автоматично: сервіс `migrate` запускає `alembic upgrade head`, і лише після його успішного завершення стартують API та фонові процеси. Усі сервіси чекають, поки PostgreSQL, Redis і RabbitMQ пройдуть healthcheck.

| Що | Адреса |
|---|---|
| Swagger | http://localhost:8000/docs |
| Веб-дашборд | http://localhost:8000/ |
| Grafana, дашборд **Price Tracker** | http://localhost:3000 (admin / admin) |
| Prometheus | http://localhost:9090 |
| RabbitMQ UI | http://localhost:15672 (guest / guest) |

**Режими запуску:**

| Команда | Що відбувається |
|---|---|
| `docker compose up -d` | Розробка: підключається `docker-compose.override.yml` — код монтується з диска, HTTP-сервіси перезапускаються при змінах, логи текстом |
| `docker compose -f docker-compose.yml up -d` | Як у продакшені: код усередині образів, без `--reload`, JSON-логи |

Образи збираються в два етапи (multi-stage): залежності встановлюються в окремому етапі, у фінальний образ потрапляють лише віртуальне оточення й код. Процеси працюють від непривілейованого користувача `app`.

Після зміни моделі ембеддингів (`EMBEDDING_MODEL`) перерахуйте вектори наявних товарів:

```bash
docker compose exec core_api python -m app.scripts.reembed_items
```

---

## 🧪 Тести

```bash
cd services/core_api && pip install -r requirements-dev.txt && pytest
```

79 тестів у трьох сервісах: інтеграційні тести API на справжньому PostgreSQL (кожен тест у транзакції з відкатом), логіка повторів і DLQ, ідемпотентне оновлення цін, класифікація HTTP-помилок scraper (`httpx.MockTransport`), дедуплікація сповіщень і rate limiting (`fakeredis`).

CI (GitHub Actions) на кожен PR: ruff, тести трьох сервісів паралельно, збірка образів із кешем шарів; при злитті в `main` образи публікуються в GHCR.

---

## 🛡 Надійність обробки повідомлень

Кожна робоча черга `<name>` має дві допоміжні:

```text
обробник впав ──► спроба ≤ 3? ──так──► <name>.retry ──(через 5 с)──► <name>
                            └──ні───► <name>.dlq  (для ручного аналізу)
```

* **Тимчасові помилки** (таймаут, 5xx, 429 від магазину, недоступна БД) повторюються до 3 разів із затримкою 5 с. Затримку робить сам RabbitMQ: TTL черги `.retry` + dead-letter назад у робочу чергу.
* **Постійні помилки** (битий JSON, некоректні поля, 404) одразу йдуть у `.dlq` або завершуються без повтору, бо повтор нічого не змінить.
* **Ідемпотентність**: доставка at-least-once, тому повідомлення може прийти двічі, і обробники це витримують:
  * `price_consumer` пише ціну одним `UPDATE ... WHERE price_checked_at < :checked_at`: дублікати й застарілі події ігноруються, навіть коли їх одночасно обробляють кілька споживачів. Історія цін пишеться в тій самій транзакції;
  * `notifier_service` ставить у Redis `SET NX notified:<товар>:<ціна>` на добу: те саме сповіщення не надсилається двічі.

> Якщо черги вже існували без DLQ (стара версія), RabbitMQ відповість `PRECONDITION_FAILED`: аргументи наявної черги змінити не можна. Зупиніть сервіси й видаліть старі черги: `docker compose exec rabbitmq rabbitmqctl delete_queue price_scraping_tasks` (так само `price_updated_events`, `price_alert_notifications`).

---

## ⚡ Redis

| Для чого | Як працює |
|---|---|
| **Rate limiting** логіну і реєстрації | `INCR` + `EXPIRE NX` в одній транзакції; понад ліміт — `429` з `Retry-After` |
| **Кеш** `/items/{id}/similar` (5 хв) | Версіоновані ключі `similar:<user>:v<версія>:...`; зміна товарів робить `INCR items_version:<user>`, і старий кеш просто перестає читатися |
| **Кеш цін** у scraper (10 хв) | Один товар у кількох користувачів — один запит до магазину |
| **Дедуплікація сповіщень** | `SET NX notified:<товар>:<ціна>` на добу |
| **Result backend Celery** | Статуси й результати задач |

Якщо Redis недоступний, API працює далі (fail open): rate limit і кеш пропускаються, у лог пишеться попередження.

---

## 📈 Моніторинг і логи

Prometheus кожні 15 секунд забирає `/metrics` з `core_api`, `price_consumer`, `scraper_service`, `notifier_service` і RabbitMQ. Дашборд і datasource Grafana підключаються автоматично з `monitoring/grafana`.

| Метрика | Що показує |
|---|---|
| `http_requests_total`, `http_request_duration_seconds` | Трафік, коди відповідей і затримки API за шаблоном маршруту |
| `scrape_results_total{result}` | Скільки цін отримано / взято з кешу / не вдалося отримати |
| `price_updates_total{result}` | Оновлення цін: записано / застаріла подія / товар не знайдено |
| `messages_retried_total`, `messages_dead_lettered_total` | Повтори й повідомлення в DLQ |
| `rabbitmq_queue_messages_ready` | Черги, що накопичуються (споживачі не встигають) |

Логи: у розробці звичайний текст, у продакшен-режимі JSON, один об'єкт на рядок (`timestamp`, `level`, `service`, `logger`, `message` + поля на кшталт `queue`, `message_id`). Формат задає `LOG_FORMAT=text|json`.

---

## 🧭 Архітектурні рішення та компроміси

| Рішення | Чому | Ціна / альтернатива |
|---|---|---|
| **Фонова робота поза API** (Celery, окремий consumer) | Кілька копій API не дублюють розклад; HTTP і фонова робота масштабуються окремо | Більше процесів і конфігурації |
| **Celery для задач, чистий AMQP для подій** | Celery зручний для розкладу й повторів задач усередині сервісу; події між сервісами не прив'язують кожен сервіс до Celery | Два способи роботи з RabbitMQ у проєкті |
| **Векторний пошук у PostgreSQL** (pgvector), а не окрема векторна БД | Одна БД, транзакції, JOIN з рештою даних; для мільйонів векторів HNSW достатньо | На сотнях мільйонів векторів варто дивитися на Qdrant/Milvus |
| **Локальна модель ембеддингів** (ONNX, fastembed) | Без платних API і без відправлення даних назовні | ~220 МБ модель у кеші; якість нижча за великі хмарні моделі |
| **Поріг схожості 0.35** | Виміряно: однакові товари, зокрема EN↔UA, до ~0.27; різні — від ~0.46 | Поріг залежить від моделі; при заміні моделі треба перевимірювати |
| **HNSW-індекс** | Пошук найближчих сусідів за ~O(log n) замість повного перебору | Пошук приблизний (ANN): зрідка може пропустити найближчого сусіда |
| **Зберігання лише змін ціни** | Перевірка щохвилини з тією самою ціною не роздуває таблицю | Не видно, коли саме ціну перевіряли без змін (є `price_checked_at` товару) |
| **Retry через TTL-чергу RabbitMQ** | Затримку тримає брокер, воркер не блокується `sleep` | Затримка фіксована (5 с), без експоненційного зростання |
| **Fixed window rate limiting** | Просто і дешево: один `INCR` | На межі вікна можливий короткий сплеск до 2× ліміту; точніше — sliding window |
| **Fail open для Redis** | Недоступний кеш не повинен ламати логін і пошук | На час збою Redis rate limit не працює |
| **Копія модуля messaging у кожному сервісі** | Сервіси збираються незалежно, без спільної бібліотеки | Зміни треба синхронізувати вручну; альтернатива — окремий пакет із версіонуванням |

### Відомі обмеження

* Scraper шукає ціну за CSS-класом `price` — це евристика. Надійніше мати парсер для кожного магазину або читати JSON-LD (`schema.org/Product`), який більшість магазинів додає для пошуковиків.
* Сповіщення поки лише пишуться в лог (заглушка під email / Telegram).
* Задача перевірки цін читає всі товари одним запитом; для великої кількості товарів варто розсилати їх пачками.
