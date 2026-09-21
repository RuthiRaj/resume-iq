from typing import Optional
from app.core.config import settings
from app.ai.provider import AiAnalyzerProvider
from app.ai.providers.gemini_provider import GeminiAnalyzerProvider
from app.ai.providers.groq_provider import GroqAnalyzerProvider
from app.ai.providers.nvidia_provider import NvidiaAnalyzerProvider
from app.ai.fallback_provider import FallbackProvider


class ConfigError(ValueError):
    """Raised when an invalid, unsupported, or unknown AI provider name is configured."""
    pass


def create_provider_by_name(name: str) -> AiAnalyzerProvider:
    """
    Instantiates an AI Analyzer provider instance by name.
    Raises ConfigError for unknown provider names (no silent defaults).
    """
    norm_name = name.lower().strip()
    if norm_name == "groq":
        return GroqAnalyzerProvider()
    elif norm_name == "gemini":
        return GeminiAnalyzerProvider()
    elif norm_name == "nvidia":
        return NvidiaAnalyzerProvider()
    elif norm_name in ("fallback", "chain"):
        return FallbackProvider()
    else:
        raise ConfigError(
            f"Unknown AI provider '{name}'. Supported providers are: 'groq', 'gemini', 'nvidia', 'fallback'."
        )


def get_ai_analyzer_provider(provider_name: Optional[str] = None) -> AiAnalyzerProvider:
    """
    Factory to retrieve the configured AI Analyzer provider.
    Raises ConfigError if the configured provider name is unknown.
    """
    name = (provider_name or settings.AI_ANALYZER_PROVIDER).lower().strip()
    return create_provider_by_name(name)
