import asyncio
import random
import time
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
import httpx

from app.core.config import settings
from app.core.logging import get_logger
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
from app.ai.observability import (
    TokenUsage,
    CostBreakdown,
    calculate_token_cost,
)

logger = get_logger("app.ai.fallback")


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
    def providers(self) -> List[AiAnalyzerProvider]:
        return list(self._providers)

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
    def cumulative_usage(self) -> TokenUsage:
        """Returns the sum of all token usages across all attempts in this execution chain."""
        total = TokenUsage()
        for ev in self._execution_events:
            if ev.token_usage:
                total = total.add(ev.token_usage)
        return total

    @property
    def cumulative_cost(self) -> CostBreakdown:
        """Returns the sum of all costs across all attempts in this execution chain."""
        total = CostBreakdown()
        for ev in self._execution_events:
            if ev.cost:
                total = total.add(ev.cost)
        return total

    @property
    def total_latency_ms(self) -> float:
        """Returns the sum of all execution latencies in milliseconds."""
        return sum(ev.latency_ms for ev in self._execution_events)

    def _build_chain(self, chain_str: str) -> List[AiAnalyzerProvider]:
        from app.ai.providers.groq_provider import GroqAnalyzerProvider
        from app.ai.providers.gemini_provider import GeminiAnalyzerProvider
        from app.ai.providers.nvidia_provider import NvidiaAnalyzerProvider

        provider_map = {
            "groq": GroqAnalyzerProvider,
            "gemini": GeminiAnalyzerProvider,
            "nvidia": NvidiaAnalyzerProvider,
        }

        names = [n.strip().lower() for n in chain_str.split(",") if n.strip()]
        chain: List[AiAnalyzerProvider] = []
        for name in names:
            if name in provider_map and has_key_for_provider(name):
                chain.append(provider_map[name]())
        return chain

    async def _execute_with_retry(
        self,
        provider: AiAnalyzerProvider,
        operation: str,
        **kwargs,
    ) -> Any:
        last_exc: Optional[Exception] = None
        raw_p = getattr(provider, "name", "unknown")
        p_name = raw_p if isinstance(raw_p, str) else "unknown"
        raw_m = (
            getattr(provider, "model_name", None)
            or getattr(provider, "_model_name", None)
            or getattr(provider, "model", None)
            or "unknown"
        )
        m_name = raw_m if isinstance(raw_m, str) else "unknown"



        for attempt in range(self._max_retries + 1):
            start_time = time.perf_counter()
            try:
                if operation == "analyze":
                    res = await provider.analyze(**kwargs)
                elif operation == "generate_json":
                    res = await provider.generate_json(**kwargs)
                else:
                    raise ValueError(f"Unknown operation: {operation}")

                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                raw_u = getattr(provider, "last_usage", None)
                usage = raw_u if isinstance(raw_u, TokenUsage) else None
                cost = calculate_token_cost(p_name, m_name, usage) if usage else None

                event = ProviderExecutionEvent(
                    provider_name=p_name,
                    model_name=m_name,
                    latency_ms=latency_ms,
                    error_type=None,
                    error_detail=None,
                    retry_count=attempt,
                    success=True,
                    token_usage=usage,
                    cost=cost,
                    operation=operation,
                )
                self._execution_events.append(event)
                self._last_provider = p_name
                self._last_model = m_name

                logger.info(
                    f"AI provider {p_name} executed successfully in {latency_ms}ms",
                    extra={
                        "event": "ai_provider_success",
                        "provider": p_name,
                        "model": m_name,
                        "duration_ms": latency_ms,
                        "attempt": attempt,
                        "total_tokens": usage.total_tokens if usage else 0,
                    },
                )
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
                        token_usage=None,
                        cost=None,
                        operation=operation,
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
                    logger.warning(
                        f"AI provider {p_name} transient error ({err_type.value}), retrying attempt {attempt + 1}",
                        extra={
                            "event": "ai_provider_retry",
                            "provider": p_name,
                            "model": m_name,
                            "attempt": attempt,
                            "error_type": err_type.value,
                            "duration_ms": latency_ms,
                        },
                    )
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
                    err_label = f"HTTP {http_exc.status_code}"
                    self._failover_log.append({
                        "provider": provider.name,
                        "error_type": err_label,
                        "reason": f"Provider {provider.name} failed with status {http_exc.status_code}: {http_exc.detail}",
                    })
                    logger.warning(
                        f"AI provider failover from {provider.name} due to {err_label}",
                        extra={
                            "event": "ai_provider_failover",
                            "provider": provider.name,
                            "error_type": err_label,
                        },
                    )
                    continue
                # Do not fall back on 400 Bad Request, 422 Unprocessable, etc.
                raise
            except (ValueError, TypeError):
                raise
            except (asyncio.TimeoutError, httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = net_err
                err_label = "Timeout" if isinstance(net_err, (asyncio.TimeoutError, httpx.TimeoutException)) else "NetworkError"
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": err_label,
                    "reason": f"Provider {provider.name} network/timeout error: {net_err}",
                })
                logger.warning(
                    f"AI provider failover from {provider.name} due to {err_label}",
                    extra={
                        "event": "ai_provider_failover",
                        "provider": provider.name,
                        "error_type": err_label,
                    },
                )
                continue
            except ProviderResilienceError as pre:
                last_error = pre
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": pre.error_type.value,
                    "reason": pre.detail,
                })
                logger.warning(
                    f"AI provider failover from {provider.name} due to {pre.error_type.value}",
                    extra={
                        "event": "ai_provider_failover",
                        "provider": provider.name,
                        "error_type": pre.error_type.value,
                    },
                )
                continue
            except Exception as exc:
                last_error = exc
                err_type = classify_provider_exception(exc, provider_name=provider.name)
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": err_type.value,
                    "reason": f"Provider {provider.name} error: {exc}",
                })
                logger.warning(
                    f"AI provider failover from {provider.name} due to {err_type.value}",
                    extra={
                        "event": "ai_provider_failover",
                        "provider": provider.name,
                        "error_type": err_type.value,
                    },
                )
                continue

        err_detail = getattr(last_error, "detail", str(last_error))
        logger.error(
            f"All AI providers in fallback chain failed. Last error: {err_detail}",
            extra={"event": "ai_generation_failed", "component": "fallback_provider"},
        )
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
                    err_label = f"HTTP {http_exc.status_code}"
                    self._failover_log.append({
                        "provider": provider.name,
                        "error_type": err_label,
                        "reason": f"Provider {provider.name} failed with status {http_exc.status_code}: {http_exc.detail}",
                    })
                    logger.warning(
                        f"AI provider failover from {provider.name} due to {err_label}",
                        extra={
                            "event": "ai_provider_failover",
                            "provider": provider.name,
                            "error_type": err_label,
                        },
                    )
                    continue
                # Do not fall back on 400 Bad Request, 422 Unprocessable, etc.
                raise
            except (ValueError, TypeError):
                raise
            except (asyncio.TimeoutError, httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = net_err
                err_label = "Timeout" if isinstance(net_err, (asyncio.TimeoutError, httpx.TimeoutException)) else "NetworkError"
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": err_label,
                    "reason": f"Provider {provider.name} network/timeout error: {net_err}",
                })
                logger.warning(
                    f"AI provider failover from {provider.name} due to {err_label}",
                    extra={
                        "event": "ai_provider_failover",
                        "provider": provider.name,
                        "error_type": err_label,
                    },
                )
                continue
            except ProviderResilienceError as pre:
                last_error = pre
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": pre.error_type.value,
                    "reason": pre.detail,
                })
                logger.warning(
                    f"AI provider failover from {provider.name} due to {pre.error_type.value}",
                    extra={
                        "event": "ai_provider_failover",
                        "provider": provider.name,
                        "error_type": pre.error_type.value,
                    },
                )
                continue
            except Exception as exc:
                last_error = exc
                err_type = classify_provider_exception(exc, provider_name=provider.name)
                self._failover_log.append({
                    "provider": provider.name,
                    "error_type": err_type.value,
                    "reason": f"Provider {provider.name} error: {exc}",
                })
                logger.warning(
                    f"AI provider failover from {provider.name} due to {err_type.value}",
                    extra={
                        "event": "ai_provider_failover",
                        "provider": provider.name,
                        "error_type": err_type.value,
                    },
                )
                continue

        err_detail = getattr(last_error, "detail", str(last_error))
        logger.error(
            f"All AI providers in fallback chain failed. Last error: {err_detail}",
            extra={"event": "ai_generation_failed", "component": "fallback_provider"},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All AI providers in fallback chain failed. Last error: {err_detail}",
        )
