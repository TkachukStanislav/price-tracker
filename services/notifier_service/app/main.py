from fastapi import FastAPI

app = FastAPI(title="Price Tracker - Notifier Service", version="1.0.0")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"service": "notifier_service", "status": "online"}
