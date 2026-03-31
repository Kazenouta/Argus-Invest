"""
Argus-Invest Backend - FastAPI Application Entry
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.routers import portfolio, trades, weakness, rules, thinking


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: ensure data directories exist
    settings.ensure_dirs()
    yield
    # Shutdown: close DuckDB connection
    from app.services.data_storage import DataStorage
    DataStorage.close()


app = FastAPI(
    title="Argus-Invest API",
    description="私人投顾系统后端 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow local frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(portfolio.router)
app.include_router(trades.router)
app.include_router(weakness.router)
app.include_router(rules.router)
app.include_router(thinking.router)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "data_dir": str(settings.DATA_DIR),
        "dirs_ready": all(
            d.exists()
            for d in [settings.USER_DIR, settings.KV_DIR,
                        settings.MARKET_DIR, settings.RULES_DIR]
        )
    }


@app.get("/")
def root():
    return {"message": "Argus-Invest API is running. See /docs for API docs."}
