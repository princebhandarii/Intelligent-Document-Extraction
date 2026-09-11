import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Document Intelligence Platform"
    environment: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./document_intelligence.db")
    cors_allowed_origin: str = os.getenv("CORS_ALLOWED_ORIGIN", "http://localhost:5500")
    max_upload_pages: int = int(os.getenv("MAX_UPLOAD_PAGES", "3"))
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "15"))
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    tesseract_cmd: str = os.getenv("TESSERACT_CMD", "tesseract")
    financial_tolerance_percent: float = float(os.getenv("FINANCIAL_TOLERANCE_PERCENT", "1.0"))

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
