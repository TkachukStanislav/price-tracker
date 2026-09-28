from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import settings
from app.core.logging import setup_logging
from app.services.worker import notification_worker

setup_logging("notifier_service", settings.LOG_FORMAT, settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Не create_task: якщо підключитися до черги не вдалося, сервіс має впасти
    # на старті, а не працювати «здоровим» без споживача
    await notification_worker.start()
    yield
    await notification_worker.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"service": "notifier_service", "status": "online"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
