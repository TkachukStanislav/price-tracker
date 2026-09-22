import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI

from app.core.config import settings
from app.services.worker import notification_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(notification_worker.start())
    yield
    worker_task.cancel()
    await notification_worker.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"service": "notifier_service", "status": "online"}
