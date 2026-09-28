import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.rabbitmq import rabbitmq_client
from app.services.price_consumer import price_update_consumer
from app.services.scheduler import price_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await rabbitmq_client.connect()
    consumer_task = asyncio.create_task(price_update_consumer.start())
    scheduler_task = asyncio.create_task(price_scheduler.start())

    yield

    # Shutdown
    scheduler_task.cancel()
    price_scheduler.stop()
    consumer_task.cancel()
    await price_update_consumer.stop()
    await rabbitmq_client.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"service": "core_api", "status": "online"}


# Віддаємо фронтенд-дашборд на головній сторінці
@app.get("/", include_in_schema=False)
async def serve_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"message": "Frontend static file not found"}


app.include_router(api_router, prefix=settings.API_V1_STR)
