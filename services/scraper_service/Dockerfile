# ---- Етап 1: встановлення залежностей ----
# Компілятори й кеш pip лишаються тут і не потрапляють у фінальний образ
FROM python:3.11-slim AS builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ---- Етап 2: фінальний образ ----
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Процес працює не від root: зламаний застосунок не отримає root у контейнері
RUN useradd --create-home --uid 1000 app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .

USER app
EXPOSE 8001

# Без --reload: це для розробки (див. docker-compose.override.yml)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
