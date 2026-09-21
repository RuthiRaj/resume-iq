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
    AI_ANALYZER_PROVIDER: str = "groq"
    AI_ANALYZER_MODEL: str = "llama-3.3-70b-versatile"
    AI_PROVIDER_CHAIN: str = "groq,gemini,nvidia"
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "meta/llama-3.2-11b-vision-instruct"

    # Cloudinary (optional) — server-side backup storage for uploaded resume
    # files. No credit card required on Cloudinary's free tier, unlike
    # Firebase Storage (which requires the Blaze plan as of Feb 2026). If
    # unset, ingestion/parsing still works fully; only the "view original
    # file later" feature is unavailable. See app/services/cloud_storage_service.py.
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
