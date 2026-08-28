from app.core.config import settings
from app.ai.provider import AiAnalyzerProvider
from app.ai.providers.gemini_provider import GeminiAnalyzerProvider
from app.ai.providers.groq_provider import GroqAnalyzerProvider


def get_ai_analyzer_provider() -> AiAnalyzerProvider:
    """
    Factory to retrieve the configured AI Analyzer provider.
    Supports 'groq' and 'gemini' based on the AI_ANALYZER_PROVIDER environment variable.
    """
    provider_name = settings.AI_ANALYZER_PROVIDER.lower().strip()
    if provider_name == "gemini":
        return GeminiAnalyzerProvider()
    if provider_name == "groq":
        return GroqAnalyzerProvider()
    return GroqAnalyzerProvider()
