import asyncio
import random
import time
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
import httpx

from app.core.config import settings
from app.schemas.candidate import CandidateEvidence
from app.schemas.analyze import AnalyzeResponse
from app.ai.provider import AiAnalyzerProvider
from app.ai.resilience import (
    ProviderErrorType,
    ProviderExecutionEvent,
    ProviderResilienceError,
    classify_provider_exception,
    is_transient_error,
)


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
    - Supports bounded in-provider retry (max 1 retry) for transient errors with jittered backoff.
    - Fails over to next provider on timeout, rate limit (429), 5xx server errors, or malformed JSON.
    - NEVER falls back on client validation errors (400, 422, ValueError, TypeError).
    - Preserves exact input context and ResumePlan across all failovers.
    """

    def __init__(
        self,
        providers: Optional[List[AiAnalyzerProvider]] = None,
        chain: Optional[str] = None,
        max_retries_per_provider: int = 1,
    ):
        if providers is not None:
            self._providers = providers
        else:
            self._providers = self._build_chain(chain or settings.AI_PROVIDER_CHAIN)
        self._max_retries = max_retries_per_provider
        self._last_provider: Optional[str] = None
        self._last_model: Optional[str] = None
        self._failover_log: List[Dict[str, Any]] = []
        self._execution_events: List[ProviderExecutionEvent] = []

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
    def execution_events(self) -> List[ProviderExecutionEvent]:
        return list(self._execution_events)

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
            provider = create_provider_by_name(name)
            if has_key_for_provider(name):
                resolved.append(provider)
        return resolved

    async def _execute_with_retry(
        self,
        provider: AiAnalyzerProvider,
        func_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Executes a provider method with bounded retry on transient errors."""
        raw_p = getattr(provider, "name", "unknown")
        p_name = str(raw_p) if not hasattr(raw_p, "_mock_name") and isinstance(raw_p, str) else str(getattr(provider, "name", "unknown"))
        raw_m = getattr(provider, "model_name", p_name)
        m_name = str(raw_m) if not hasattr(raw_m, "_mock_name") and isinstance(raw_m, str) else p_name

        last_exc: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            start_time = time.perf_counter()
            try:
                method = getattr(provider, func_name)
                res = await method(*args, **kwargs)
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                event = ProviderExecutionEvent(
                    provider_name=p_name,
                    model_name=m_name,
                    latency_ms=latency_ms,
                    error_type=None,
                    error_detail=None,
                    retry_count=attempt,
                    success=True,
                )
                self._execution_events.append(event)
                self._last_provider = p_name
                self._last_model = m_name
                return res
            except Exception as exc:
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                last_exc = exc
                err_type = classify_provider_exception(exc, provider_name=p_name)

                try:
                    event = ProviderExecutionEvent(
                        provider_name=p_name,
                        model_name=m_name,
                        latency_ms=latency_ms,
                        error_type=err_type,
                        error_detail=str(exc),
                        retry_count=attempt,
                        success=False,
                    )
                    self._execution_events.append(event)
                except Exception:
                    pass

                # Client data errors should immediately fail without retry or fallback
                if isinstance(exc, (ValueError, TypeError)):
                    raise exc
                if isinstance(exc, HTTPException) and exc.status_code in (400, 422):
                    raise exc

                # Check if transient and we have retries left
                if attempt < self._max_retries and is_transient_error(err_type):
                    backoff = min(0.05 * (2 ** attempt) + random.uniform(0.01, 0.05), 0.5)
                    await asyncio.sleep(backoff)
                    continue

                # Non-transient or retries exhausted: break out of retry loop to trigger fallback
                break

        if last_exc:
            raise last_exc

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
        self._execution_events = []
        last_error: Optional[Exception] = None

        for provider in self._providers:
            try:
                return await self._execute_with_retry(
                    provider,
                    "analyze",
                    target_role=target_role,
                    target_company=target_company,
                    job_description=job_description,
                    job_description_hash=job_description_hash,
                    candidate_evidence=candidate_evidence,
                )
            except HTTPException as http_exc:
                last_error = http_exc
                if http_exc.status_code == 429 or http_exc.status_code >= 500:
                    self._failover_log.append({
                        "provider": provider.name,
                        "error_type": f"HTTP {http_exc.status_code}",
                        "reason": f"Provider {provider.name} failed with status {http_exc.status_code}: {http_exc.detail}",
                    })
                    continue
                # Do not fall back on 400 Bad Request, 422 Unprocessable, etc.
                raise
            except (ValueError, TypeError):
                raise
            except (asyncio.TimeoutError, httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = net_err
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": "Timeout" if isinstance(net_err, (asyncio.TimeoutError, httpx.TimeoutException)) else "NetworkError",
                    "reason": f"Provider {provider.name} network/timeout error: {net_err}",
                })
                continue
            except ProviderResilienceError as pre:
                last_error = pre
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": pre.error_type.value,
                    "reason": pre.detail,
                })
                continue
            except Exception as exc:
                last_error = exc
                err_type = classify_provider_exception(exc, provider_name=provider.name)
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": err_type.value,
                    "reason": f"Provider {provider.name} error: {exc}",
                })
                continue

        err_detail = getattr(last_error, "detail", str(last_error))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All AI providers in fallback chain failed. Last error: {err_detail}",
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
        self._execution_events = []
        last_error: Optional[Exception] = None

        for provider in self._providers:
            try:
                return await self._execute_with_retry(
                    provider,
                    "generate_json",
                    system_instruction=system_instruction,
                    user_prompt=user_prompt,
                    schema_hint=schema_hint,
                )
            except HTTPException as http_exc:
                last_error = http_exc
                if http_exc.status_code == 429 or http_exc.status_code >= 500:
                    self._failover_log.append({
                        "provider": provider.name,
                        "error_type": f"HTTP {http_exc.status_code}",
                        "reason": f"Provider {provider.name} failed with status {http_exc.status_code}: {http_exc.detail}",
                    })
                    continue
                # Do not fall back on 400 Bad Request, 422 Unprocessable, etc.
                raise
            except (ValueError, TypeError):
                raise
            except (asyncio.TimeoutError, httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = net_err
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": "Timeout" if isinstance(net_err, (asyncio.TimeoutError, httpx.TimeoutException)) else "NetworkError",
                    "reason": f"Provider {provider.name} network/timeout error: {net_err}",
                })
                continue
            except ProviderResilienceError as pre:
                last_error = pre
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": pre.error_type.value,
                    "reason": pre.detail,
                })
                continue
            except Exception as exc:
                last_error = exc
                err_type = classify_provider_exception(exc, provider_name=provider.name)
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": err_type.value,
                    "reason": f"Provider {provider.name} error: {exc}",
                })
                continue

        err_detail = getattr(last_error, "detail", str(last_error))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All AI providers in fallback chain failed. Last error: {err_detail}",
        )
