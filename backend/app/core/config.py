from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server Settings
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Firebase Settings
    FIREBASE_PROJECT_ID: str = "resumeiq-3cfe6"
    FIREBASE_CREDENTIALS_PATH: str = ""

    # AI Analyzer Settings (Server-Side Only)
    AI_ANALYZER_PROVIDER: str = "gemini"
    AI_ANALYZER_MODEL: str = "gemini-3.6-flash"
    GEMINI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
