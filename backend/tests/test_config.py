from app.core.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.PROJECT_NAME == "LegalMetro Shield"
    assert settings.GEMINI_MODEL == "gemini-3.6-flash"
    assert settings.OCR_PROVIDER == "gemini"
    assert settings.GROQ_BASE_URL == "https://api.groq.com/openai/v1"
    assert settings.GROQ_MODEL == "groq/compound"
    assert "groq/compound-mini" in settings.GROQ_FALLBACK_MODELS
    assert settings.ACCESS_TOKEN_EXPIRE_MIN == 30
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 30
    assert "legalmetro-scans" in settings.MINIO_BUCKET


def test_groq_model_limits_metadata():
    from app.core.config import GROQ_MODEL_LIMITS

    assert "groq/compound" in GROQ_MODEL_LIMITS
    assert GROQ_MODEL_LIMITS["groq/compound"]["rpm"] == 30
    assert GROQ_MODEL_LIMITS["groq/compound"]["rpd"] == 250
    assert GROQ_MODEL_LIMITS["openai/gpt-oss-120b"]["rpd"] == 1_000
    assert GROQ_MODEL_LIMITS["qwen/qwen3.8-27b"]["tpm"] == 8_000
