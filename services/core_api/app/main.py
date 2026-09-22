from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import settings
from app.core.rabbitmq import rabbitmq_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код ДО yield виконується при старті додатку:
    await rabbitmq_client.connect()
    yield
    # Код ПІСЛЯ yield виконується при зупинці додатку:
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


app.include_router(api_router, prefix=settings.API_V1_STR)
