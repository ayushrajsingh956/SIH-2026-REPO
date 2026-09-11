from app.core.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.PROJECT_NAME == "LegalMetro Shield"
    assert settings.GEMINI_MODEL == "gemini-2.5-flash"
    assert settings.OCR_PROVIDER == "gemini"
    assert settings.ACCESS_TOKEN_EXPIRE_MIN == 30
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 30
    assert "legalmetro-scans" in settings.MINIO_BUCKET
