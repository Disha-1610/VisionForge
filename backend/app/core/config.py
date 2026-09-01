from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    APP_NAME: str = "VisionForge-AI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # ---------- Database ----------
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/visionforge"
    DATABASE_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # ---------- JWT ----------
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---------- CORS ----------
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ---------- Gemini (Google AI Studio) ----------
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_VLM_MODEL: str = "gemini-3.5-flash"
    GEMINI_JUDGE_MODEL: str = "gemini-3.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"

    # ---------- Groq ----------
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_VLM_MODEL: str = "qwen/qwen3.6-27b"
    GROQ_JUDGE_MODEL: str = "openai/gpt-oss-20b"

    # ---------- File Storage ----------
    UPLOAD_DIR: str = str(BASE_DIR / "data" / "inspection_uploads")
    GOLDEN_IMAGE_DIR: str = str(BASE_DIR / "data" / "golden_images")
    FAISS_INDEX_DIR: str = str(BASE_DIR / "data" / "faiss_index")
    ROI_TEMPLATE_DIR: str = str(BASE_DIR / "data" / "roi_templates")
    YOLO_WEIGHTS_DIR: str = str(BASE_DIR / "data" / "yolo_weights")
    REPORTS_DIR: str = str(BASE_DIR / "data" / "reports")

    # ---------- Embedding / CLIP ----------
    CLIP_MODEL: str = "openai/clip-vit-base-patch32"
    FAISS_INDEX_PATH: str = str(BASE_DIR / "data" / "faiss_index" / "golden.index")
    SIMILARITY_THRESHOLD: float = 0.75

    # ---------- Pipeline Stage 1: Quality Validation (admin-tunable) ----------
    MIN_BLUR_VARIANCE: float = 100.0      # Laplacian variance below this = too blurry
    MIN_BRIGHTNESS: float = 40.0          # mean pixel brightness below this = too dark
    MAX_BRIGHTNESS: float = 220.0         # mean pixel brightness above this = overexposed
    MIN_IMAGE_WIDTH: int = 640            # minimum usable resolution
    MIN_IMAGE_HEIGHT: int = 480
    DUPLICATE_HASH_MAX_DISTANCE: int = 4  # hamming distance <= this => duplicate image


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

