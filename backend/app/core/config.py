from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Application
    PROJECT_NAME: str = "LegalMetro Shield"
    API_V1_STR: str = "/api/v1"
    ENV: Literal["development", "staging", "production", "test"] = "development"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/legalmetro",
        description="Async PostgreSQL connection string",
    )

    # Redis (broker & cache)
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string",
    )

    # MinIO / S3 Object Storage
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "legalmetro-scans"
    MINIO_SECURE: bool = False

    # AI & Vision
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    OCR_PROVIDER: Literal["gemini", "groq", "tesseract", "gcv"] = "gemini"

    # Groq Fallback & Multi-Model
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "groq/compound"
    GROQ_FALLBACK_MODELS: list[str] = [
        "groq/compound",
        "groq/compound-mini",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
    ]

    # Authentication & Tokens
    JWT_SECRET: str = "dev-insecure-secret-key-change-in-production-min-32-chars"
    ACCESS_TOKEN_EXPIRE_MIN: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Rate Limiting
    RATE_LIMITING_ENABLED: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Groq Tier Model Limits Metadata (RPM, RPD, TPM, TPD)
GROQ_MODEL_LIMITS: dict[str, dict[str, int | None]] = {
    "groq/compound": {"rpm": 30, "rpd": 250, "tpm": 70_000, "tpd": None},
    "groq/compound-mini": {"rpm": 30, "rpd": 250, "tpm": 70_000, "tpd": None},
    "openai/gpt-oss-120b": {"rpm": 30, "rpd": 1_000, "tpm": 8_000, "tpd": 200_000},
    "openai/gpt-oss-20b": {"rpm": 30, "rpd": 1_000, "tpm": 8_000, "tpd": 200_000},
    "openai/gpt-oss-safeguard-20b": {"rpm": 30, "rpd": 1_000, "tpm": 8_000, "tpd": 200_000},
    "qwen/qwen3.6-27b": {"rpm": 30, "rpd": 1_000, "tpm": 8_000, "tpd": 200_000},
    "qwen/qwen3.8-27b": {"rpm": 30, "rpd": 1_000, "tpm": 8_000, "tpd": 200_000},
}
