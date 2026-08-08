import os
from functools import lru_cache
from pathlib import Path
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for the backend (where .env file lives)
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """
    VisionForge-AI Application Settings.
    Loads and validates environment variables from system environment and backend/.env file.
    """
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ── App ──────────────────────────────────────────────────────
    APP_NAME: str = Field(default="VisionForge-AI", description="Application name")
    APP_ENV: str = Field(default="development", description="Application environment (development, staging, production)")
    DEBUG: bool = Field(default=True, description="Enable debug mode")
    SECRET_KEY: str = Field(default="change-me-to-a-random-secret-key", description="Application secret key")
    API_VERSION: str = Field(default="v1", description="API version prefix")

    # ── Server ───────────────────────────────────────────────────
    HOST: str = Field(default="0.0.0.0", description="Server host interface")
    PORT: int = Field(default=8000, description="Server port")
    RELOAD: bool = Field(default=True, description="Auto-reload on code changes")
    WORKERS: int = Field(default=1, description="Number of worker processes")

    # ── Database (SQLite for local dev / PostgreSQL for production) ──
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./visionforge.db",
        description="Async database connection URL (SQLite for local dev, PostgreSQL for prod)",
    )
    DATABASE_ECHO: bool = Field(default=False, description="Echo SQL queries to log")

    # ── JWT Auth ────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(default="change-me-to-a-strong-jwt-secret", description="JWT signing key")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="Access token expiration in minutes")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token expiration in days")

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ORIGINS: Union[str, List[str]] = Field(
        default="http://localhost:5173,http://localhost:3000",
        description="Allowed CORS origins (comma-separated or JSON list)",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, description="Allow CORS credentials")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    # ── File Storage ─────────────────────────────────────────────
    UPLOAD_DIR: Path = Field(default=PROJECT_ROOT / "data" / "inspection_uploads", description="Directory for uploaded inspection images")
    GOLDEN_IMAGE_DIR: Path = Field(default=PROJECT_ROOT / "data" / "golden_images", description="Directory for reference golden images")
    HEATMAP_DIR: Path = Field(default=PROJECT_ROOT / "data" / "heatmaps", description="Directory for generated heatmap overlays")
    REPORT_DIR: Path = Field(default=PROJECT_ROOT / "data" / "reports", description="Directory for generated PDF reports")
    ROI_TEMPLATE_DIR: Path = Field(default=PROJECT_ROOT / "data" / "roi_templates", description="Directory for ROI template JSON files")
    FAISS_INDEX_DIR: Path = Field(default=PROJECT_ROOT / "data" / "faiss_index", description="Directory for FAISS vector index files")

    # ── CLIP / Embedding ────────────────────────────────────────
    CLIP_MODEL_NAME: str = Field(default="ViT-B/32", description="OpenCLIP model architecture name")
    FAISS_SIMILARITY_THRESHOLD: float = Field(default=0.75, description="Minimum similarity threshold for FAISS vector match")

    # ── NVIDIA NIM (LLM + Vision) ────────────────────────────────
    NVIDIA_NIM_API_KEY: str = Field(default="nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", description="NVIDIA NIM API key")
    NVIDIA_NIM_BASE_URL: str = Field(default="https://integrate.api.nvidia.com/v1", description="NVIDIA NIM API base URL")

    # Text LLM — 124B MoE, 1M context
    NVIDIA_NIM_CHAT_MODEL: str = Field(default="nvidia/nemotron-3-super-120b-a12b", description="Primary text LLM for reasoning & debate")
    NVIDIA_NIM_CHAT_MAX_TOKENS: int = Field(default=16384, description="Max response tokens for text LLM")

    # Vision LLM — 33B, 262K context
    NVIDIA_NIM_VISION_MODEL: str = Field(default="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", description="Primary Vision LLM for visual defect analysis")
    NVIDIA_NIM_VISION_MAX_TOKENS: int = Field(default=65536, description="Max response tokens for vision LLM")

    NVIDIA_NIM_TIMEOUT: int = Field(default=60, description="NVIDIA NIM API request timeout in seconds")
    NVIDIA_NIM_TEMPERATURE: float = Field(default=0.6, description="Sampling temperature")
    NVIDIA_NIM_TOP_P: float = Field(default=0.95, description="Nucleus sampling top_p")

    # ── Pipeline Thresholds ─────────────────────────────────────
    QUALITY_BLUR_THRESHOLD: float = Field(default=100.0, description="OpenCV Laplacian variance blur detection threshold")
    QUALITY_MIN_RESOLUTION: int = Field(default=640, description="Minimum image dimension in pixels")
    AUTHENTICITY_THRESHOLD: float = Field(default=0.7, description="Minimum acceptable image authenticity score")
    FRAUD_SCORE_QUARANTINE_THRESHOLD: int = Field(default=90, description="Fraud score threshold to trigger quarantine action")
    FRAUD_SCORE_REVIEW_THRESHOLD: int = Field(default=60, description="Fraud score threshold to trigger human review")
    CONFIDENCE_REVIEW_THRESHOLD: int = Field(default=60, description="Confidence threshold below which human review is required")

    # ── Logging ──────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO", description="Log verbosity level (DEBUG, INFO, WARNING, ERROR)")
    LOG_FORMAT: str = Field(default="json", description="Log format (json or console)")

    # ── Upstash Redis (Rate Limiting + Caching) ──────────────────
    UPSTASH_REDIS_URL: str = Field(default="https://xxxxxxxx.upstash.io", description="Upstash Redis REST URL")
    UPSTASH_REDIS_TOKEN: str = Field(default="AXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", description="Upstash Redis REST Token")

    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=60, description="Max requests per minute per IP/user")
    RATE_LIMIT_BURST: int = Field(default=10, description="Allowed burst capacity")

    # Cache TTL (seconds)
    CACHE_TTL_INSPECTION_RESULT: int = Field(default=3600, description="TTL for cached inspection results")
    CACHE_TTL_GOLDEN_REFERENCE: int = Field(default=86400, description="TTL for golden reference cache")
    CACHE_TTL_ANALYTICS: int = Field(default=300, description="TTL for analytics summary cache")

    def ensure_directories_exist(self) -> None:
        """Create storage directories if they do not exist."""
        directories = [
            self.UPLOAD_DIR,
            self.GOLDEN_IMAGE_DIR,
            self.HEATMAP_DIR,
            self.REPORT_DIR,
            self.ROI_TEMPLATE_DIR,
            self.FAISS_INDEX_DIR,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached instance of application settings.
    Copies backend/.env.example to backend/.env if backend/.env doesn't exist.
    """
    env_file = BACKEND_DIR / ".env"
    env_example = BACKEND_DIR / ".env.example"

    if not env_file.exists() and env_example.exists():
        env_file.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")

    settings = Settings()
    settings.ensure_directories_exist()
    return settings


# Convenience global instance
settings = get_settings()
