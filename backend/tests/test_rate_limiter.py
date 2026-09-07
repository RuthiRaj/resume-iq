import pytest
import asyncio
from fastapi import HTTPException
from app.core.rate_limiter import InMemoryRateLimiter
from app.schemas.analyze import AnalyzeRequest
from app.services.resume_service import _validate_safe_id, get_candidate_resume_data
from app.core.auth import AuthenticatedUser
from pydantic import ValidationError


@pytest.mark.asyncio
async def test_rate_limiter_allows_under_limit():
    limiter = InMemoryRateLimiter(max_requests=5, window_seconds=10)
    for _ in range(5):
        await limiter.check("test_user_ok")


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    limiter = InMemoryRateLimiter(max_requests=3, window_seconds=10)
    await limiter.check("user_burst")
    await limiter.check("user_burst")
    await limiter.check("user_burst")

    with pytest.raises(HTTPException) as exc_info:
        await limiter.check("user_burst")

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_rate_limiter_isolation_between_users():
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=10)
    await limiter.check("user_1")
    await limiter.check("user_1")

    # user_2 should still be allowed
    await limiter.check("user_2")


def test_resume_id_path_traversal_validation():
    # Valid safe IDs
    assert _validate_safe_id("resume_123") == "resume_123"
    assert _validate_safe_id("my-resume-v1") == "my-resume-v1"

    # Malicious / path traversal IDs
    with pytest.raises(HTTPException) as exc1:
        _validate_safe_id("../other_user")
    assert exc1.value.status_code == 400

    with pytest.raises(HTTPException) as exc2:
        _validate_safe_id("resumes/123")
    assert exc2.value.status_code == 400

    with pytest.raises(HTTPException) as exc3:
        _validate_safe_id("res;DROP TABLE")
    assert exc3.value.status_code == 400


def test_analyze_request_schema_rejects_unsafe_id():
    # Invalid resume ID with slash/traversal
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            resumeId="../traversal",
            targetRole="Software Engineer",
            jobDescription="A" * 50,
        )

    # Valid resume ID
    req = AnalyzeRequest(
        resumeId="valid-resume-123",
        targetRole="Software Engineer",
        jobDescription="A" * 50,
    )
    assert req.resume_id == "valid-resume-123"
