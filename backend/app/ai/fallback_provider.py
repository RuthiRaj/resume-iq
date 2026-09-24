import asyncio
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
import httpx

from app.core.config import settings
from app.schemas.candidate import CandidateEvidence
from app.schemas.analyze import AnalyzeResponse
from app.ai.provider import AiAnalyzerProvider


def has_key_for_provider(provider_name: str) -> bool:
    """Checks if a given provider name has a valid, non-placeholder API key configured."""
    norm = provider_name.lower().strip()
    if norm == "groq":
        k = settings.GROQ_API_KEY
        return bool(k and k.strip() and k.strip() != "your_server_side_groq_api_key_here")
    if norm == "gemini":
        k = settings.GEMINI_API_KEY
        return bool(k and k.strip() and k.strip() != "your_server_side_gemini_api_key_here")
    if norm == "nvidia":
        k = settings.NVIDIA_API_KEY
        return bool(k and k.strip() and k.strip() != "your_server_side_nvidia_api_key_here")
    return True


class FallbackProvider:
    """
    Wraps multiple AI providers in an ordered fallback chain.
    - Resolves chain from AI_PROVIDER_CHAIN (default: 'groq,gemini,nvidia').
    - Skips providers with no API key configured.
    - Tries next provider ONLY on timeout, 429 rate limit, or 5xx server errors.
    - NEVER falls back on data validation or client request errors.
    """

    def __init__(
        self,
        providers: Optional[List[AiAnalyzerProvider]] = None,
        chain: Optional[str] = None,
    ):
        if providers is not None:
            self._providers = providers
        else:
            self._providers = self._build_chain(chain or settings.AI_PROVIDER_CHAIN)
        self._last_provider: Optional[str] = None
        self._last_model: Optional[str] = None
        self._failover_log: List[Dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "fallback"

    @property
    def last_provider(self) -> Optional[str]:
        return self._last_provider

    @property
    def last_model(self) -> Optional[str]:
        return self._last_model

    @property
    def failover_log(self) -> List[Dict[str, Any]]:
        return list(self._failover_log)

    @property
    def providers(self) -> List[AiAnalyzerProvider]:
        return self._providers

    @staticmethod
    def _build_chain(chain_str: str) -> List[AiAnalyzerProvider]:
        from app.ai.factory import create_provider_by_name

        resolved: List[AiAnalyzerProvider] = []
        raw_names = [name.strip() for name in chain_str.split(",") if name.strip()]
        for name in raw_names:
            if name.lower() == "fallback":
                continue
            # Validate name will raise ConfigError for unknown providers
            provider = create_provider_by_name(name)
            # Skip providers with no key configured
            if has_key_for_provider(name):
                resolved.append(provider)
        return resolved

    async def analyze(
        self,
        target_role: str,
        target_company: Optional[str],
        job_description: str,
        job_description_hash: str,
        candidate_evidence: CandidateEvidence,
    ) -> AnalyzeResponse:
        if not self._providers:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No AI providers in fallback chain have valid API keys configured.",
            )

        self._failover_log = []
        last_error = None
        for provider in self._providers:
            try:
                res = await provider.analyze(
                    target_role=target_role,
                    target_company=target_company,
                    job_description=job_description,
                    job_description_hash=job_description_hash,
                    candidate_evidence=candidate_evidence,
                )
                self._last_provider = provider.name
                self._last_model = getattr(provider, "model_name", provider.name)
                return res
            except HTTPException as http_exc:
                last_error = http_exc
                # Fall back ONLY on 429 or 5xx status codes (500, 502, 503, 504)
                if http_exc.status_code == 429 or http_exc.status_code >= 500:
                    self._failover_log.append({
                        "provider": provider.name,
                        "error_type": f"HTTP {http_exc.status_code}",
                        "reason": f"Provider {provider.name} failed with status {http_exc.status_code}",
                    })
                    continue
                # Do not fall back on 400 Bad Request, 422 Unprocessable, etc.
                raise
            except (ValueError, TypeError):
                # Explicitly do not fall back on validation / data type errors
                raise
            except (asyncio.TimeoutError, httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = net_err
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": "Timeout" if isinstance(net_err, (asyncio.TimeoutError, httpx.TimeoutException)) else "NetworkError",
                    "reason": f"Provider {provider.name} network/timeout error",
                })
                continue
            except Exception as exc:
                last_error = exc
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": type(exc).__name__,
                    "reason": f"Provider {provider.name} unexpected error",
                })
                continue

        if isinstance(last_error, HTTPException):
            raise last_error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All AI providers in fallback chain failed. Last error: {last_error}",
        )

    async def generate_json(
        self,
        system_instruction: str,
        user_prompt: str,
        schema_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._providers:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No AI providers in fallback chain have valid API keys configured.",
            )

        self._failover_log = []
        last_error = None
        for provider in self._providers:
            try:
                res = await provider.generate_json(
                    system_instruction=system_instruction,
                    user_prompt=user_prompt,
                    schema_hint=schema_hint,
                )
                self._last_provider = provider.name
                self._last_model = getattr(provider, "model_name", provider.name)
                return res
            except HTTPException as http_exc:
                last_error = http_exc
                # Fall back ONLY on 429 or 5xx status codes (500, 502, 503, 504)
                if http_exc.status_code == 429 or http_exc.status_code >= 500:
                    self._failover_log.append({
                        "provider": provider.name,
                        "error_type": f"HTTP {http_exc.status_code}",
                        "reason": f"Provider {provider.name} failed with status {http_exc.status_code}",
                    })
                    continue
                # Do not fall back on 400 Bad Request, 422 Unprocessable, etc.
                raise
            except (ValueError, TypeError):
                # Explicitly do not fall back on validation / data type errors
                raise
            except (asyncio.TimeoutError, httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = net_err
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": "Timeout" if isinstance(net_err, (asyncio.TimeoutError, httpx.TimeoutException)) else "NetworkError",
                    "reason": f"Provider {provider.name} network/timeout error",
                })
                continue
            except Exception as exc:
                last_error = exc
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": type(exc).__name__,
                    "reason": f"Provider {provider.name} unexpected error",
                })
                continue

        if isinstance(last_error, HTTPException):
            raise last_error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All AI providers in fallback chain failed. Last error: {last_error}",
        )
