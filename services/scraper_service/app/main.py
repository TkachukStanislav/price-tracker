from fastapi import FastAPI

app = FastAPI(title="Price Tracker - Scraper Service", version="1.0.0")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"service": "scraper_service", "status": "online"}
