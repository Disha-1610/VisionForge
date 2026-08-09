import os
from functools import lru_cache
from pathlib import Path
from typing import List, Union

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
    System environment variables aur backend/.env file se saare configs load aur validate karta hai.
    """

    # ── Pydantic Settings Configuration ─────────────────────────────────────
    # model_config Pydantic v2 ka tarika hai batane ka ki env file kahan hai aur kaise read karni hai.
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),  # backend/.env file se values read karega
        env_file_encoding="utf-8",           # UTF-8 text encoding format
        extra="ignore",                       # `.env` mein koi extra unlisted variable ho toh crash mat hone do
        case_sensitive=True,                  # Variable names exact UPPERCASE match hone chahiye
    )

    # ── App Basic Configs ───────────────────────────────────────────────────
    APP_NAME: str = Field(default="VisionForge-AI", description="Application ka naam")
    APP_ENV: str = Field(default="development", description="Environment stage: development, staging, or production")
    DEBUG: bool = Field(default=True, description="Debug mode enable/disable (detailed errors display hongi)")
    SECRET_KEY: str = Field(default="change-me-to-a-random-secret-key", description="JWT / Session sign karne ke liye main secret key")
    API_VERSION: str = Field(default="v1", description="FastAPI route ka version prefix (e.g. /api/v1)")

    # ── Server Options ───────────────────────────────────────────────────────
    HOST: str = Field(default="0.0.0.0", description="Uvicorn server interface (0.0.0.0 matlab sab local IPs se accept karega)")
    PORT: int = Field(default=8000, description="FastAPI backend application port")
    RELOAD: bool = Field(default=True, description="Code save hone par dev server auto-reload hoga (development format)")
    WORKERS: int = Field(default=1, description="Production environment mein kitne parallel process workers chalenge")

    # ── Database Configs ────────────────────────────────────────────────────
    # Local dev ke liye SQLite (sqlite+aiosqlite) default set hai.
    # Production mein PostgreSQL URL set karenge (postgresql+asyncpg://user:pass@host:port/dbname).
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./visionforge.db",
        description="Async database connection URL (Local dev mein SQLite, Prod mein Postgres)",
    )
    DATABASE_ECHO: bool = Field(default=False, description="True hone par SQLAlchemy saari raw SQL queries terminal pe print karega")

    # ── JWT Authentication ──────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(default="change-me-to-a-strong-jwt-secret", description="User tokens generate aur verify karne ki secret key")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT token ka encryption algorithm")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="Login access token kitne minutes tak valid rahega")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token kitne din tak valid rahega")

    # ── CORS Settings ────────────────────────────────────────────────────────
    # CORS (Cross-Origin Resource Sharing): Browser ko permission deta hai ki frontend se backend API hit kar sake.
    CORS_ORIGINS: Union[str, List[str]] = Field(
        default="http://localhost:5173,http://localhost:3000",
        description="Allowed frontend URLs (comma-separated string ya array list)",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, description="Cookies aur Authorization headers allow karne ke liye")

    # ── Field Validator for CORS ─────────────────────────────────────────────
    # mode="before" ka matlab: Pydantic type checking se PEHLE ye function chalega.
    # Agar `.env` mein CORS_ORIGINS simple string hai "http://a.com,http://b.com",
    # toh ye function usko comma (,) se break karke list ['http://a.com', 'http://b.com'] bana deta hai.
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    # ── File Storage Paths ───────────────────────────────────────────────────
    # Local disk folders jahan inspection images, golden references, aur generated PDF reports save hongi.
    UPLOAD_DIR: Path = Field(default=PROJECT_ROOT / "data" / "inspection_uploads", description="Uploaded inspection images ka folder")
    GOLDEN_IMAGE_DIR: Path = Field(default=PROJECT_ROOT / "data" / "golden_images", description="Reference golden images ka folder")
    HEATMAP_DIR: Path = Field(default=PROJECT_ROOT / "data" / "heatmaps", description="Generated defect heatmap images ka folder")
    REPORT_DIR: Path = Field(default=PROJECT_ROOT / "data" / "reports", description="Generated PDF reports ka folder")
    ROI_TEMPLATE_DIR: Path = Field(default=PROJECT_ROOT / "data" / "roi_templates", description="ROI bounding box JSON files ka folder")
    FAISS_INDEX_DIR: Path = Field(default=PROJECT_ROOT / "data" / "faiss_index", description="FAISS vector similarity index storage folder")

    # ── CLIP Embeddings & Vector Search ──────────────────────────────────────
    CLIP_MODEL_NAME: str = Field(default="ViT-B/32", description="OpenCLIP model architecture (image features vector generate karne ke liye)")
    FAISS_SIMILARITY_THRESHOLD: float = Field(default=0.75, description="FAISS search match ka minimum confidence score threshold (0.0 se 1.0)")

    # ── NVIDIA NIM Cloud API Configs ─────────────────────────────────────────
    # NVIDIA NIM endpoints standard OpenAI SDK format use karte hain.
    NVIDIA_NIM_API_KEY: str = Field(default="nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", description="NVIDIA Developer portal ka API key")
    NVIDIA_NIM_BASE_URL: str = Field(default="https://integrate.api.nvidia.com/v1", description="NVIDIA NIM API entry endpoint")

    # Text LLM — Multi-agent debate, causal reasoning, aur final verdict ke liye
    NVIDIA_NIM_CHAT_MODEL: str = Field(default="nvidia/nemotron-3-super-120b-a12b", description="Primary text reasoning LLM model")
    NVIDIA_NIM_CHAT_MAX_TOKENS: int = Field(default=16384, description="Text LLM response tokens limit")

    # Vision LLM — Visual inspection agent (images detect karke defect explain karne ke liye)
    NVIDIA_NIM_VISION_MODEL: str = Field(default="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", description="Primary image+text vision model")
    NVIDIA_NIM_VISION_MAX_TOKENS: int = Field(default=65536, description="Vision LLM response tokens limit")

    NVIDIA_NIM_TIMEOUT: int = Field(default=60, description="API request call ka max timeout limit (seconds mein)")
    NVIDIA_NIM_TEMPERATURE: float = Field(default=0.6, description="LLM creativity / randomness scale (0.0 strictly logical, 1.0 creative)")
    NVIDIA_NIM_TOP_P: float = Field(default=0.95, description="Nucleus sampling threshold for response generation")

    # ── Inspection Pipeline Thresholds ──────────────────────────────────────
    # Fixed thresholds jo computer vision stages decide karte hain
    QUALITY_BLUR_THRESHOLD: float = Field(default=100.0, description="OpenCV Laplacian variance — 100 se kam hone par image blurry mark hogi")
    QUALITY_MIN_RESOLUTION: int = Field(default=640, description="Image ka min height/width in pixels")
    AUTHENTICITY_THRESHOLD: float = Field(default=0.7, description="Image ELA/EXIF authenticity score minimum limit")
    FRAUD_SCORE_QUARANTINE_THRESHOLD: int = Field(default=90, description="Fraud score > 90 hone par product quarantine action trigger hoga")
    FRAUD_SCORE_REVIEW_THRESHOLD: int = Field(default=60, description="Fraud score > 60 hone par human review required hoga")
    CONFIDENCE_REVIEW_THRESHOLD: int = Field(default=60, description="AI verdict confidence < 60 hone par human reviewer review karega")

    # ── Logging Settings ────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO", description="Terminal log level: DEBUG, INFO, WARNING, ya ERROR")
    LOG_FORMAT: str = Field(default="json", description="Log format: json (production log parsing ke liye) ya console (readable text)")

    # ── Upstash Redis (API Rate Limiting + Caching) ──────────────────────────
    UPSTASH_REDIS_URL: str = Field(default="https://xxxxxxxx.upstash.io", description="Upstash Redis REST endpoint URL")
    UPSTASH_REDIS_TOKEN: str = Field(default="AXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", description="Upstash Redis authentication token")

    # Rate Limiting Controls
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=60, description="Ek User/IP max kitne API requests per minute bhej sakta hai")
    RATE_LIMIT_BURST: int = Field(default=10, description="Quick burst request allowance limit")

    # Cache TTL (Time-To-Live in seconds)
    CACHE_TTL_INSPECTION_RESULT: int = Field(default=3600, description="Inspection result kitne time tak cache rahega (1 hour)")
    CACHE_TTL_GOLDEN_REFERENCE: int = Field(default=86400, description="Golden image info kitne time tak cache rahegi (24 hours)")
    CACHE_TTL_ANALYTICS: int = Field(default=300, description="Analytics summary metrics cache time (5 minutes)")

    # ── Automated Directory Creation Method ──────────────────────────────────
    # Ye method application startup par saare necessary local storage folders create karta hai.
    # mkdir(parents=True, exist_ok=True) ka matlab:
    # - parents=True: parent directories (e.g. data/) missing hain toh woh bhi bana do
    # - exist_ok=True: agar folder pehle se bana hua hai toh error mat pheko
    def ensure_directories_exist(self) -> None:
        """App startup par sabhi required storage folders create karta hai."""
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
# Initial launch par ek baar `Settings()` object create hone ke baad ye function result memory mein freeze kar leta hai.
# Jab bhi code mein `get_settings()` call hoga, `.env` file dobara parse nahi hogi — instantly cached Settings return hongi.
@lru_cache()
def get_settings() -> Settings:
    """
    Settings object ki single cached instance return karta hai.
    Agar backend/.env file gayab ho, toh .env.example se auto-copy karke .env file create kar deta hai.
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
