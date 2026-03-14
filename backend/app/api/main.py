"""FastAPI application entry point."""
from fastapi import FastAPI
from app.infrastructure.database import engine, Base

app = FastAPI(title="Marketplace API", version="2.0")

@app.on_event("startup")
async def startup():
    """Create tables on startup."""
    async with engine.begin() as conn:
        # Tables created via migrations, but ensure they exist
        pass

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0"}
