import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1 import api_router
from app.core.config import settings
from app.core.metrics import PrometheusMiddleware
from app.core.rabbitmq import rabbitmq_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # API лише публікує задачі. Фонова робота живе в окремих процесах:
    # price_consumer, celery_worker, celery_beat (див. docker-compose.yml)
    await rabbitmq_client.connect()
    yield
    await rabbitmq_client.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(PrometheusMiddleware)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"service": "core_api", "status": "online"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Віддаємо фронтенд-дашборд на головній сторінці
@app.get("/", include_in_schema=False)
async def serve_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"message": "Frontend static file not found"}


app.include_router(api_router, prefix=settings.API_V1_STR)
