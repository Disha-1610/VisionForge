from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import engine, init_db
from app.core.exceptions import register_exception_handlers
from app.routers import analytics, auth, inspections, products, reports, system, vendors
from app.services.embedding_service import embedding_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    # Ensure data directories exist
    for dir_path in [
        settings.UPLOAD_DIR,
        settings.GOLDEN_IMAGE_DIR,
        settings.FAISS_INDEX_DIR,
        settings.ROI_TEMPLATE_DIR,
        settings.YOLO_WEIGHTS_DIR,
        settings.REPORTS_DIR,
    ]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    # Initialize database tables and seed demo users/vendors
    try:
        await init_db()
        logger.info("Database tables and seed data initialized successfully")
    except Exception as e:
        logger.warning("Database initialization deferred: %s", e)

    # Try to load existing FAISS index
    embedding_service.load_index(settings.FAISS_INDEX_PATH)

    yield

    # Shutdown
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handlers ────────────────────────────────────────────────────────
register_exception_handlers(app)

# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(vendors.router, prefix=API_PREFIX)
app.include_router(inspections.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(system.router, prefix=API_PREFIX)


# ── Static File Serving ───────────────────────────────────────────────────────
upload_path = Path(settings.UPLOAD_DIR)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=str(upload_path)), name="uploads")

golden_path = Path(settings.GOLDEN_IMAGE_DIR)
golden_path.mkdir(parents=True, exist_ok=True)
app.mount("/static/golden", StaticFiles(directory=str(golden_path)), name="golden")


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
