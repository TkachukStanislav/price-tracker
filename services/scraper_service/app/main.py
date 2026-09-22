import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI

from app.core.config import settings
from app.core.redis import redis_client
from app.services.worker import scraper_worker

# Explicitly display INFO-level logs in Docker
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.connect()
    worker_task = asyncio.create_task(scraper_worker.start())

    yield

    worker_task.cancel()
    await scraper_worker.stop()
    await redis_client.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"service": "scraper_service", "status": "online"}
