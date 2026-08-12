from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Paths Calculation ────────────────────────────────────────────────────────
# __file__ se is config.py file ka exact path milta hai.
# .resolve() relative path ko absolute full system path mein convert karta hai.
# 3 baar .parent karne par: config.py -> core -> app -> backend directory ka root path milta hai.
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# PROJECT_ROOT matlab poore VisionForge repo ka main root directory (backend ke upar wali directory)
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """
    VisionForge-AI Application Settings.
    Loads and validates environment variables from system environment and backend/.env file.
    """

    # ── Pydantic Settings Configuration ─────────────────────────────────────
    # model_config Pydantic v2 ka tarika hai batane ka ki env file kahan hai aur kaise read karni hai.
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),  # backend/.env file se values read karega
        env_file_encoding="utf-8",           # UTF-8 text encoding format
        extra="ignore",                       # .env mein koi extra unlisted variable ho toh crash mat hone do
        case_sensitive=True,                  # Variable names exact UPPERCASE match hone chahiye
    )

    # ── App Basic Configs ───────────────────────────────────────────────────
    APP_NAME: str = Field(default="VisionForge-AI", description="Application name")
    APP_ENV: str = Field(default="development", description="Application environment (development, staging, production)")
    DEBUG: bool = Field(default=True, description="Enable debug mode")
    SECRET_KEY: str = Field(default="change-me-to-a-random-secret-key", description="Application secret key")
    API_VERSION: str = Field(default="v1", description="API version prefix")

    # ── Server Options ───────────────────────────────────────────────────────
    # Uvicorn host: 0.0.0.0 matlab sab local IP interfaces se requests accept hongi.
    HOST: str = Field(default="0.0.0.0", description="Server host interface")
    PORT: int = Field(default=8000, description="Server port")
    RELOAD: bool = Field(default=True, description="Auto-reload on code changes")
    WORKERS: int = Field(default=1, description="Number of worker processes")

    # ── Database Configs ────────────────────────────────────────────────────
    # Local dev ke liye SQLite (sqlite+aiosqlite) default set hai.
    # Production mein PostgreSQL URL set karenge (postgresql+asyncpg://user:pass@host:port/dbname).
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./visionforge.db",
        description="Async database connection URL (SQLite for local dev, PostgreSQL for prod)",
    )
    DATABASE_ECHO: bool = Field(default=False, description="Echo SQL queries to log")

    # ── JWT Authentication ──────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(default="change-me-to-a-strong-jwt-secret", description="JWT signing key")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="Access token expiration in minutes")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token expiration in days")

    # ── CORS Settings ────────────────────────────────────────────────────────
    # CORS (Cross-Origin Resource Sharing): Browser permission to allow frontend to make API calls to backend.
    CORS_ORIGINS: str | list[str] = Field(
        default="http://localhost:5173,http://localhost:3000",
        description="Allowed CORS origins (comma-separated or JSON list)",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, description="Allow CORS credentials")

    # ── Field Validator for CORS ─────────────────────────────────────────────
    # mode="before" ka matlab: Pydantic type checking se PEHLE ye function chalega.
    # Agar .env mein CORS_ORIGINS simple string hai "http://a.com,http://b.com",
    # toh ye function usko comma (,) se break karke list ['http://a.com', 'http://b.com'] bana deta hai.
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    # ── File Storage Paths ───────────────────────────────────────────────────
    # Local disk storage directories jahan inspection uploads, reference images, and reports save honge.
    UPLOAD_DIR: Path = Field(default=PROJECT_ROOT / "data" / "inspection_uploads", description="Directory for uploaded inspection images")
    GOLDEN_IMAGE_DIR: Path = Field(default=PROJECT_ROOT / "data" / "golden_images", description="Directory for reference golden images")
    HEATMAP_DIR: Path = Field(default=PROJECT_ROOT / "data" / "heatmaps", description="Directory for generated heatmap overlays")
    REPORT_DIR: Path = Field(default=PROJECT_ROOT / "data" / "reports", description="Directory for generated PDF reports")
    ROI_TEMPLATE_DIR: Path = Field(default=PROJECT_ROOT / "data" / "roi_templates", description="Directory for ROI template JSON files")
    FAISS_INDEX_DIR: Path = Field(default=PROJECT_ROOT / "data" / "faiss_index", description="Directory for FAISS vector index files")

    # ── CLIP Embeddings & Vector Search ──────────────────────────────────────
    CLIP_MODEL_NAME: str = Field(default="ViT-B/32", description="OpenCLIP model architecture name")
    FAISS_SIMILARITY_THRESHOLD: float = Field(default=0.75, description="Minimum similarity threshold for FAISS vector match")

    # ── NVIDIA NIM Cloud API Configs ─────────────────────────────────────────
    # NVIDIA NIM endpoints standard OpenAI SDK format use karte hain.
    NVIDIA_NIM_API_KEY: str = Field(default="nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", description="NVIDIA NIM API key")
    NVIDIA_NIM_BASE_URL: str = Field(default="https://integrate.api.nvidia.com/v1", description="NVIDIA NIM API base URL")

    # Text LLM — Multi-agent debate, causal reasoning, aur final verdict ke liye
    NVIDIA_NIM_CHAT_MODEL: str = Field(default="nvidia/nemotron-3-super-120b-a12b", description="Primary text LLM for reasoning & debate")
    NVIDIA_NIM_CHAT_MAX_TOKENS: int = Field(default=16384, description="Max response tokens for text LLM")

    # Vision LLM — Visual inspection agent (images detect karke defect explain karne ke liye)
    NVIDIA_NIM_VISION_MODEL: str = Field(default="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", description="Primary Vision LLM for visual defect analysis")
    NVIDIA_NIM_VISION_MAX_TOKENS: int = Field(default=65536, description="Max response tokens for vision LLM")

    NVIDIA_NIM_TIMEOUT: int = Field(default=60, description="NVIDIA NIM API request timeout in seconds")
    NVIDIA_NIM_TEMPERATURE: float = Field(default=0.6, description="Sampling temperature")
    NVIDIA_NIM_TOP_P: float = Field(default=0.95, description="Nucleus sampling top_p")

    # ── Groq Free Tier Fallback Configs (Optional) ───────────────────────────
    GROQ_API_KEY: str = Field(default="", description="Optional Groq API key for fallback")
    GROQ_BASE_URL: str = Field(default="https://api.groq.com/openai/v1", description="Groq API base URL")
    GROQ_CHAT_MODEL: str = Field(default="llama-3.3-70b-versatile", description="Groq fallback text LLM model")
    GROQ_VISION_MODEL: str = Field(default="llama-3.2-90b-vision-preview", description="Groq fallback vision LLM model")

    # ── Inspection Pipeline Thresholds ──────────────────────────────────────
    # Fixed thresholds jo computer vision stages decide karte hain
    QUALITY_BLUR_THRESHOLD: float = Field(default=100.0, description="OpenCV Laplacian variance blur detection threshold")
    QUALITY_MIN_RESOLUTION: int = Field(default=640, description="Minimum image dimension in pixels")
    AUTHENTICITY_THRESHOLD: float = Field(default=0.7, description="Minimum acceptable image authenticity score")
    FRAUD_SCORE_QUARANTINE_THRESHOLD: int = Field(default=90, description="Fraud score threshold to trigger quarantine action")
    FRAUD_SCORE_REVIEW_THRESHOLD: int = Field(default=60, description="Fraud score threshold to trigger human review")
    CONFIDENCE_REVIEW_THRESHOLD: int = Field(default=60, description="Confidence threshold below which human review is required")

    # ── Logging Settings ────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO", description="Log verbosity level (DEBUG, INFO, WARNING, ERROR)")
    LOG_FORMAT: str = Field(default="json", description="Log format (json or console)")

    # ── Upstash Redis (API Rate Limiting + Caching) ──────────────────────────
    UPSTASH_REDIS_URL: str = Field(default="https://xxxxxxxx.upstash.io", description="Upstash Redis REST URL")
    UPSTASH_REDIS_TOKEN: str = Field(default="AXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", description="Upstash Redis REST Token")

    # Rate Limiting Controls
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=60, description="Max requests per minute per IP/user")
    RATE_LIMIT_BURST: int = Field(default=10, description="Allowed burst capacity")

    # Cache TTL (Time-To-Live in seconds)
    CACHE_TTL_INSPECTION_RESULT: int = Field(default=3600, description="TTL for cached inspection results")
    CACHE_TTL_GOLDEN_REFERENCE: int = Field(default=86400, description="TTL for golden reference cache")
    CACHE_TTL_ANALYTICS: int = Field(default=300, description="TTL for analytics summary cache")

    # ── Server-Sent Events (SSE) Settings ───────────────────────────────────
    SSE_PING_INTERVAL_SECONDS: int = Field(default=15, description="Keep-alive ping interval for SSE streams in seconds")

    # ── Automated Directory Creation Method ──────────────────────────────────
    # Ye method application startup par saare necessary local storage folders create karta hai.
    # mkdir(parents=True, exist_ok=True) ka matlab:
    # - parents=True: parent directories (e.g. data/) missing hain toh woh bhi bana do
    # - exist_ok=True: agar folder pehle se bana hua hai toh error mat pheko
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


# ── LRU Cached Settings Factory Function ─────────────────────────────────────
# @lru_cache() ka matlab: "Least Recently Used Cache".
# Initial launch par ek baar Settings() object create hone ke baad ye function result memory mein freeze kar leta hai.
# Jab bhi code mein get_settings() call hoga, .env file dobara parse nahi hogi — instantly cached Settings return hongi.
@lru_cache
def get_settings() -> Settings:
    """
    Get cached instance of application settings.
    Copies backend/.env.example to backend/.env if backend/.env doesn't exist.
    """
    env_file = BACKEND_DIR / ".env"
    env_example = BACKEND_DIR / ".env.example"

    # Auto setup helper: pehli baar dev environment launch hone par automatic .env file create ho jayegi
    if not env_file.exists() and env_example.exists():
        env_file.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")

    settings = Settings()
    settings.ensure_directories_exist()  # Data folders create karo
    return settings


# Convenience global settings instance (direct import ke liye: from app.core import settings)
settings = get_settings()
