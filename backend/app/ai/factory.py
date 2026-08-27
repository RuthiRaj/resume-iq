from app.core.config import settings
from app.ai.provider import AiAnalyzerProvider
from app.ai.providers.gemini_provider import GeminiAnalyzerProvider


def get_ai_analyzer_provider() -> AiAnalyzerProvider:
    """Factory to retrieve the configured AI Analyzer provider."""
    provider_name = settings.AI_ANALYZER_PROVIDER.lower()
    if provider_name == "gemini":
        return GeminiAnalyzerProvider()
    return GeminiAnalyzerProvider()
