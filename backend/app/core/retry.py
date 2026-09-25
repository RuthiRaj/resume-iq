"""
Centralized Transient Retry Utility for ResumeIQ.
Provides bounded exponential backoff with jitter for network/transient service errors.
Strictly avoids retrying deterministic client/data errors (400, 401, 403, 404, 409, 422).
"""

import asyncio
import random
import time
from typing import Callable, TypeVar, Any, Optional, Tuple, Type
import httpx
from fastapi import HTTPException
from app.core.logging import get_logger, get_request_id

logger = get_logger("app.core.retry")

T = TypeVar("T")

TRANSIENT_STATUS_CODES = {429, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 409, 422}


def is_transient_exception(exc: Exception) -> bool:
    """Classifies whether an exception is a transient network or server error."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, HTTPException):
        return exc.status_code in TRANSIENT_STATUS_CODES
    return False


async def async_retry_transient(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 2,
    base_delay: float = 0.05,
    max_delay: float = 0.5,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    operation_name: str = "operation",
    **kwargs: Any,
) -> Any:
    """
    Executes an async callable with bounded exponential backoff on transient errors.

    Args:
        func: Async function to execute.
        max_retries: Maximum number of retry attempts after initial failure.
        base_delay: Initial backoff delay in seconds.
        max_delay: Cap on backoff delay in seconds.
        backoff_factor: Multiplier for backoff calculation.
        jitter: Whether to add random jitter to prevent thundering herd.
        operation_name: Semantic label for structured logging.
    """
    last_exc: Optional[Exception] = None
    req_id = get_request_id()

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc

            # Never retry deterministic non-transient or client errors
            if isinstance(exc, (ValueError, TypeError)):
                raise exc
            if isinstance(exc, HTTPException) and exc.status_code in NON_RETRYABLE_STATUS_CODES:
                raise exc

            if not is_transient_exception(exc):
                # Unknown unclassified exception: fail immediately
                raise exc

            if attempt < max_retries:
                # Calculate exponential backoff
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                if jitter:
                    delay += random.uniform(0.005, 0.02)
                delay = min(delay, max_delay)

                logger.warning(
                    f"Transient error during {operation_name} (attempt {attempt + 1}/{max_retries + 1}): {str(exc)}. Retrying in {round(delay, 3)}s",
                    extra={
                        "event": "transient_retry",
                        "operation": operation_name,
                        "attempt": attempt + 1,
                        "delay_s": round(delay, 3),
                        "request_id": req_id,
                    },
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"Retries exhausted for {operation_name} after {max_retries + 1} attempts: {str(exc)}",
                    extra={
                        "event": "retry_exhausted",
                        "operation": operation_name,
                        "attempts": max_retries + 1,
                        "request_id": req_id,
                    },
                )
                raise last_exc

    if last_exc:
        raise last_exc
