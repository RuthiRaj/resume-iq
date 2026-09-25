import json
from typing import List, Union, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server Settings
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: Union[List[str], str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def validate_log_level(cls, v: Any) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        val_str = str(v).upper().strip() if v else "INFO"
        return val_str if val_str in valid else "INFO"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                return []
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    parsed = json.loads(v_stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in v_stripped.split(",") if item.strip()]
        elif isinstance(v, (list, tuple, set)):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

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

    def validate_production_preflight(self) -> None:
        """
        Validates critical configuration when running in production mode.
        Fails fast at startup with actionable error messages without exposing secret values.
        Preserves development and test defaults when ENVIRONMENT != 'production'.
        """
        if self.ENVIRONMENT.lower() != "production":
            return

        errors: List[str] = []

        if not self.FIREBASE_PROJECT_ID or not self.FIREBASE_PROJECT_ID.strip():
            errors.append("FIREBASE_PROJECT_ID must be set in production.")

        if not self.AI_PROVIDER_CHAIN or not self.AI_PROVIDER_CHAIN.strip():
            errors.append("AI_PROVIDER_CHAIN must be configured in production.")
        else:
            configured_providers = [p.strip().lower() for p in self.AI_PROVIDER_CHAIN.split(",") if p.strip()]
            valid_providers = {"groq", "gemini", "nvidia"}
            unknown = [p for p in configured_providers if p not in valid_providers]
            if unknown:
                errors.append(f"AI_PROVIDER_CHAIN contains invalid provider(s): {', '.join(unknown)}")

            # In production, at least one provider in the chain must have an API key configured
            has_valid_key = False
            for p in configured_providers:
                if p == "groq" and self.GROQ_API_KEY and len(self.GROQ_API_KEY.strip()) > 5:
                    has_valid_key = True
                elif p == "gemini" and self.GEMINI_API_KEY and len(self.GEMINI_API_KEY.strip()) > 5:
                    has_valid_key = True
                elif p == "nvidia" and self.NVIDIA_API_KEY and len(self.NVIDIA_API_KEY.strip()) > 5:
                    has_valid_key = True

            if not has_valid_key:
                errors.append(
                    "At least one AI provider in AI_PROVIDER_CHAIN must have a valid API key configured "
                    "(GROQ_API_KEY, GEMINI_API_KEY, or NVIDIA_API_KEY)."
                )

        if not self.CORS_ORIGINS:
            errors.append("CORS_ORIGINS must not be empty in production.")
        elif "*" in self.CORS_ORIGINS and len(self.CORS_ORIGINS) == 1:
            errors.append("Wildcard CORS_ORIGINS ['*'] is not permitted in production with allow_credentials=True.")

        if errors:
            joined_errors = "; ".join(errors)
            raise RuntimeError(f"Production configuration preflight failed: {joined_errors}")


settings = Settings()
