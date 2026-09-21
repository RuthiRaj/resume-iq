import time
import asyncio
from typing import Dict, List
from fastapi import HTTPException, status


class InMemoryRateLimiter:
    """
    Lightweight, thread-safe in-memory sliding window rate limiter.
    Enforces per-user (UID) rate limits on expensive AI and mutation endpoints
    without requiring Redis or external infrastructure.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._records: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        now = time.time()
        cutoff = now - self.window_seconds

        async with self._lock:
            # Clean up old timestamps for this key
            timestamps = self._records.get(key, [])
            valid_timestamps = [t for t in timestamps if t > cutoff]

            if len(valid_timestamps) >= self.max_requests:
                oldest = valid_timestamps[0]
                retry_after = int(self.window_seconds - (now - oldest)) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds}s. Please retry in {retry_after} seconds.",
                    headers={"Retry-After": str(max(1, retry_after))},
                )

            valid_timestamps.append(now)
            self._records[key] = valid_timestamps

            # Periodic cleanup of expired entries if tracking many callers
            if len(self._records) > 2000:
                self._prune(cutoff)

    def _prune(self, cutoff: float) -> None:
        keys_to_delete = [k for k, v in self._records.items() if not v or v[-1] <= cutoff]
        for k in keys_to_delete:
            del self._records[k]


# Shared rate limiters for expensive operations
ai_analysis_limiter = InMemoryRateLimiter(max_requests=25, window_seconds=60)
ai_synthesis_limiter = InMemoryRateLimiter(max_requests=35, window_seconds=60)
resume_generation_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)
ai_edit_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)
mutation_limiter = InMemoryRateLimiter(max_requests=50, window_seconds=60)
